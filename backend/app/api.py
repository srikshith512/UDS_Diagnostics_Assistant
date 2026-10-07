"""HTTP API. Routes validate input, call the deterministic engine, persist results and write the audit log."""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, File, Header, HTTPException, Request, Response, UploadFile

from . import schemas
from .rag import qa
from .rag.llm import LlmError
from .rag.retriever import chunk_document
from .uds import export, testgen
from .uds.engine import EcuState, fmt, parse_hex, process

router = APIRouter(prefix="/api")


def _ctx(request: Request):
    s = request.app.state
    return s.spec, s.db, s.retriever, s.llm


def _actor(x_actor: str | None) -> str:
    return re.sub(r"[^\w .@-]", "", x_actor or "engineer")[:40] or "engineer"


def _hex(text: str) -> bytes:
    try:
        return parse_hex(text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _bench(spec, b: schemas.Bench) -> EcuState:
    if b.session not in spec.sessions:
        raise HTTPException(422, f"Session {b.session} is not defined. Use one of {sorted(spec.sessions)}.")
    return EcuState.initial(spec, b.session, b.unlocked, b.seed_issued)


def _view(spec, res) -> dict:
    return {"response": fmt(res.response), "positive": res.positive, "nrc": res.nrc,
            "nrc_text": spec.nrcs.get(res.nrc) if res.nrc else None, "trace": res.trace}


def _validate(spec, b, req: bytes) -> dict:
    state = _bench(spec, b)
    ref, sim = process(spec, state, req), process(spec, state, req, b.fault)
    return {"request": fmt(req), "spec": _view(spec, ref), "ecu": _view(spec, sim), "matches": ref.response == sim.response}


@router.get("/health")
def health(request: Request):
    _, _, retriever, llm = _ctx(request)
    return {"status": "ok", "retrieval": retriever.mode, "llm_available": llm.available(), "llm_model": llm.model}


@router.get("/spec")
def get_spec(request: Request):
    spec, db, _, _ = _ctx(request)
    services = [{"sid": f"{s.sid:02X}", "name": s.name, "sessions": [f"{x:02X}" for x in s.sessions], "security": s.security,
                 "example": fmt(testgen.positive_request(spec, s))} for s in spec.services.values()]
    return {"sections": spec.sections, "services": services, "nrcs": {f"{k:02X}": v for k, v in spec.nrcs.items()},
            "sessions": {f"{k:02X}": v for k, v in spec.sessions.items()}, "documents": sorted({d["name"] for d in db.list_documents()}),
            "notice": "Synthetic specification. Not ISO 14229 or OEM text."}


@router.post("/spec/ingest")
async def ingest(request: Request, file: UploadFile = File(...), x_actor: str | None = Header(None)):
    _, db, retriever, _ = _ctx(request)
    limit = request.app.state.settings.max_upload_bytes
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(413, f"File is larger than {limit // 1000} KB.")
    name = re.sub(r"[^\w.\-]", "_", file.filename or "upload.txt")[:60]
    if not name.lower().endswith((".md", ".txt")):
        raise HTTPException(415, "Only .md and .txt files are supported.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(415, "File must be UTF-8 text.") from exc
    chunks = chunk_document(name, text)
    if not chunks:
        raise HTTPException(422, "The file contains no text.")
    db.add_documents(name, chunks)
    retriever.add(chunks)
    db.audit(_actor(x_actor), "Ingested document", f"{name}: {len(chunks)} chunks")
    return {"name": name, "chunks": len(chunks)}


@router.post("/qa")
def ask(body: schemas.QuestionIn, request: Request, x_actor: str | None = Header(None)):
    _, db, retriever, llm = _ctx(request)
    result = qa.answer(body.question, retriever, llm)
    db.audit(_actor(x_actor), "Asked spec question", f"{body.question[:120]} [{result['mode']}]")
    return result


@router.post("/validate")
def validate(body: schemas.ValidateIn, request: Request):
    spec = _ctx(request)[0]
    return _validate(spec, body, _hex(body.request_hex))


@router.post("/assist/request")
def assist(body: schemas.AssistIn, request: Request, x_actor: str | None = Header(None)):
    """LLM proposes a request from plain language; the rule engine then validates it."""
    spec, db, _, llm = _ctx(request)
    catalogue = "\n".join(f"- {s.sid:02X} {s.name}, sub-functions: {','.join(f'{x:02X}' for x in s.subfunctions) or 'none'}" for s in spec.services.values())
    dids = ", ".join(f"{d.did:04X}={d.name}" for d in spec.dids.values())
    routines = ", ".join(f"{k:04X}={v}" for k, v in spec.routines.items())
    prompt = (f"Services:\n{catalogue}\nDIDs: {dids}\nRoutines: {routines}\n"
              "Write a request as hex bytes for this goal. Answer as JSON with keys request_hex and explanation.\n"
              f"Goal: {body.description}")
    try:
        data = json.loads(llm.generate(prompt, json_mode=True))
        suggestion = parse_hex(str(data["request_hex"]))
    except LlmError as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(502, "The model did not return a usable request. Try rephrasing.") from exc
    db.audit(_actor(x_actor), "Requested AI suggestion", f"{body.description[:100]} -> {fmt(suggestion)}")
    return {"suggestion": fmt(suggestion), "explanation": str(data.get("explanation", ""))[:400], "validation": _validate(spec, body, suggestion)}


@router.get("/tests")
def list_tests(request: Request):
    return _ctx(request)[1].list_tests()


@router.post("/tests/generate")
def generate_tests(request: Request, x_actor: str | None = Header(None)):
    spec, db, _, _ = _ctx(request)
    n = db.replace_generated(testgen.generate(spec))
    db.audit(_actor(x_actor), "Generated test suite", f"{n} cases from the rule engine; earlier generated cases replaced")
    return {"generated": n}


@router.post("/tests", status_code=201)
def add_test(body: schemas.ManualTestIn, request: Request, x_actor: str | None = Header(None)):
    spec, db, _, _ = _ctx(request)
    req = _hex(body.request_hex)
    if not req:
        raise HTTPException(422, "Request is empty.")
    res = process(spec, _bench(spec, body), req)
    svc = spec.services.get(req[0])
    tid = db.add_manual({"sid": req[0], "kind": "positive" if res.positive else "negative", "pre": {"session": body.session, "unlocked": body.unlocked, "seed_issued": body.seed_issued},
                         "title": body.title or f"Manual: {svc.name if svc else 'Unknown service'}", "request": fmt(req), "expected": fmt(res.response),
                         "criteria": f"Response equals {fmt(res.response)}"})
    db.audit(_actor(x_actor), "Added manual test", f"{tid}: {fmt(req)}")
    return {"id": tid}


@router.patch("/tests/{test_id}/review")
def review(test_id: str, body: schemas.ReviewIn, request: Request, x_actor: str | None = Header(None)):
    db = _ctx(request)[1]
    if not db.set_review(test_id, body.status, body.comment):
        raise HTTPException(404, f"Test case {test_id} not found.")
    db.audit(_actor(x_actor), f"Marked {body.status}", f"{test_id} {body.comment}".strip())
    return {"id": test_id, "status": body.status}


@router.post("/tests/approve-drafts")
def approve_drafts(request: Request, x_actor: str | None = Header(None)):
    db = _ctx(request)[1]
    n = db.approve_drafts()
    db.audit(_actor(x_actor), "Approved all drafts", f"{n} cases")
    return {"approved": n}


@router.post("/tests/run")
def run_tests(body: schemas.RunIn, request: Request, x_actor: str | None = Header(None)):
    spec, db, _, _ = _ctx(request)
    cases = db.list_tests()
    results = {c["id"]: testgen.run_case(spec, c, body.fault) for c in cases}
    db.save_results(results)
    failed = sum(not r["passed"] for r in results.values())
    db.audit(_actor(x_actor), "Ran tests on simulated ECU", f"{len(cases)} cases, {failed} failed, ECU variant: {body.fault or 'reference'}")
    return {"total": len(cases), "failed": failed}


@router.get("/coverage")
def get_coverage(request: Request):
    spec, db, _, _ = _ctx(request)
    return export.coverage(spec, db.list_tests("Approved"), len(db.list_tests()))


@router.get("/export/{fmt_name}")
def export_script(fmt_name: str, request: Request, x_actor: str | None = Header(None)):
    db = _ctx(request)[1]
    if fmt_name not in {"python", "capl"}:
        raise HTTPException(404, "Export format must be 'python' or 'capl'.")
    approved = db.list_tests("Approved")
    if not approved:
        raise HTTPException(409, "No approved test cases. Approve at least one test before exporting.")
    body = export.to_python(approved) if fmt_name == "python" else export.to_capl(approved)
    db.audit(_actor(x_actor), f"Exported {fmt_name}", f"{len(approved)} approved cases")
    ext = "py" if fmt_name == "python" else "can"
    return Response(body, media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="uds_tests.{ext}"'})


@router.get("/audit")
def audit_log(request: Request):
    return _ctx(request)[1].list_audit()
