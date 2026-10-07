# UDS Diagnostics Assistant

A web application that helps test engineers build and validate UDS (ISO 14229-style) diagnostic requests, generate
positive and negative test cases, run them against a simulated ECU, and export automation scripts for Python (pytest)
and CAPL. It is based on *Case Study 5* of the Automotive Engineering AI reference document.

> **Synthetic data only.** The ECU specification in `backend/data/ecu_spec.json` is invented for demonstration. It is
> not ISO 14229 or OEM text, and the app never talks to a real vehicle.

## Design principle: the model drafts, the rules decide

| Concern | Handled by |
| --- | --- |
| Understanding questions, summarising, suggesting a request from plain language | Local LLM through Ollama (optional) |
| Whether a request is valid, and what the ECU must answer | Deterministic Python rule engine (`backend/app/uds/engine.py`) |
| Expected results of every generated test | The rule engine, never the LLM |
| Final acceptance of any test | A human reviewer, recorded in the audit log |

If the LLM is offline the app still works: Q&A returns extracted spec passages with citations, and every other feature
is independent of the model. An answer is only marked *grounded* if it cites sources that retrieval actually returned.

## Features

- **Ask the spec**: cited answers over the spec and your own `.md`/`.txt` uploads (ChromaDB + BGE embeddings, with an
  automatic lexical fallback).
- **Request builder**: type hex or describe a goal; see the predicted response, the NRC reason, and a step-by-step rule
  trace. The simulated ECU answers the same request, and any deviation is flagged.
- **Test cases**: generate 30+ cases covering every service, session, security state and NRC. Approve or reject each one.
- **Fault injection**: switch the ECU variant to "skips security check" and re-run the suite to watch it catch the defect.
- **Export and coverage**: pytest and CAPL scripts from approved tests, plus coverage of services, NRCs and sessions.
- **Audit log**: every question, generation, review, run and export, stored in SQLite with the actor.

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec ollama ollama pull qwen2.5:3b   # optional: enables LLM answers and suggestions
```

Open <http://localhost:8080>. The first start downloads the embedding model (about 130 MB) when vector retrieval is on.
For a small, fast image, set `INSTALL_RAG=0` and `RETRIEVAL=lexical` in `.env`. To reuse Ollama already running on your
machine, set `OLLAMA_URL=http://host.docker.internal:11434` and remove the `ollama` service.

## Local development

```bash
make install
make dev-backend      # http://localhost:8000  (API docs at /docs)
make dev-frontend     # http://localhost:5173  (proxies /api to the backend)
make test
```

Optional extras: `pip install -r backend/requirements-rag.txt` for vector retrieval, and `ollama pull qwen2.5:3b` for the LLM.

## Architecture

```
React (Vite) ──/api──▶ FastAPI ─┬─ rule engine + simulated ECU   (uds/engine.py, spec-driven)
                                ├─ test generator, exporter       (uds/testgen.py, uds/export.py)
                                ├─ retrieval: ChromaDB | lexical  (rag/retriever.py)
                                ├─ Ollama client + grounded Q&A   (rag/llm.py, rag/qa.py)
                                └─ SQLite: tests, reviews, audit  (db.py)
```

```
backend/
  app/uds/      spec loader, rule engine, test generation, export
  app/rag/      retrieval, LLM client, grounded Q&A
  app/api.py    HTTP routes     app/db.py  persistence     app/main.py  app factory
  data/ecu_spec.json            the synthetic specification (edit it to change the rules)
  tests/                        35 pytest tests (engine, generator, API)
frontend/src/   React app (one component per page)
```

## API

| Method and path | Purpose |
| --- | --- |
| `GET /api/health` | Retrieval mode and LLM availability |
| `GET /api/spec` | Sections, services with example requests, NRCs, ingested documents |
| `POST /api/qa` | Cited answer to a question |
| `POST /api/spec/ingest` | Upload a `.md` or `.txt` document (max 1 MB) |
| `POST /api/validate` | Predicted and simulated response with rule trace |
| `POST /api/assist/request` | LLM suggests a request; the rule engine validates it |
| `GET/POST /api/tests`, `POST /api/tests/generate` | List, add, generate |
| `PATCH /api/tests/{id}/review` | Approve or reject with a comment |
| `POST /api/tests/approve-drafts`, `POST /api/tests/run` | Bulk approve, execute on the simulated ECU |
| `GET /api/coverage`, `GET /api/export/{python\|capl}` | Coverage and scripts (approved tests only) |
| `GET /api/audit` | Audit trail |

## Adapting it

- **Change the ECU**: edit `backend/data/ecu_spec.json` (services, sessions, DIDs, routines, NRCs, documentation
  sections). New service behaviour goes in `process()` in `engine.py`, with a test in `tests/test_engine.py`.
- **Use another LLM**: set `LLM_MODEL`, or replace `OllamaClient` in `rag/llm.py` with a class exposing `available()` and `generate()`.
- **Real standards or OEM text**: only ingest documents you are licensed to use, and keep the deployment inside your network.

## Security and limits

- Uploaded text is treated as untrusted: the prompt tells the model to ignore instructions inside it, and answers that
  do not cite retrieved sources are flagged as unverified.
- Uploads are limited to UTF-8 `.md`/`.txt`, 1 MB. Hex input, sessions, status values and fault names are validated.
- There is no login. Run it on a trusted network or put it behind your own authentication proxy; the `X-Actor` audit
  name is self-reported and not an identity.
- Generated tests and scripts are drafts. Review them before running on any bench.
