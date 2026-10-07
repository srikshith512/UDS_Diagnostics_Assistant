"""Rule-derived test generation. Every expected response is computed by the rule engine, never by an LLM."""
from __future__ import annotations

from .engine import DEFAULT_SESSION, EXTENDED_SESSION, EcuState, fmt, parse_hex, process
from .spec import Service, Spec


def pre(session: int = DEFAULT_SESSION, unlocked: bool = False, seed_issued: bool = False) -> dict:
    return {"session": session, "unlocked": unlocked, "seed_issued": seed_issued}


def positive_request(spec: Spec, svc: Service) -> bytes:
    """A canonical valid request for a service, derived from the spec."""
    if svc.sid == 0x22:
        did = next(d for d in spec.dids.values())
        return bytes([0x22, *did.did.to_bytes(2, "big")])
    if svc.sid == 0x2E:
        did = next(d for d in spec.dids.values() if d.writable)
        return bytes([0x2E, *did.did.to_bytes(2, "big"), *did.default])
    if svc.sid == 0x31:
        rid = next(iter(spec.routines))
        return bytes([0x31, svc.subfunctions[0], *rid.to_bytes(2, "big")])
    if svc.subfunctions:
        return bytes([svc.sid, svc.subfunctions[-1] if svc.sid == 0x10 else svc.subfunctions[0]])
    return bytes([svc.sid])


def ready_state(svc: Service) -> dict:
    """Preconditions under which the canonical request is valid."""
    needs_ext = EXTENDED_SESSION in svc.sessions and (svc.security or DEFAULT_SESSION not in svc.sessions)
    return pre(EXTENDED_SESSION if needs_ext else DEFAULT_SESSION, svc.security)


def generate(spec: Spec) -> list:
    cases: list = []

    def add(sid, kind, title, p, req, criteria=None):
        res = process(spec, EcuState.initial(spec, **p), bytes(req))
        cases.append({
            "sid": sid, "kind": kind, "title": title, "pre": p,
            "request": fmt(bytes(req)), "expected": fmt(res.response),
            "criteria": criteria or (f"Response equals {fmt(res.response)}" if res.positive
                                     else f"NRC {res.nrc:02X} ({spec.nrcs.get(res.nrc, '?')}) returned"),
        })

    for svc in spec.services.values():
        sid, name = svc.sid, svc.name
        ready, pos = ready_state(svc), positive_request(spec, svc)
        add(sid, "positive", f"{name}: valid request", ready, pos)
        add(sid, "negative", f"{name}: extra byte rejected", ready, [*pos, 0x00])
        if svc.subfunctions:
            bad = next(x for x in range(0x7E, 0, -1) if x not in svc.subfunctions)
            add(sid, "negative", f"{name}: unknown sub-function", ready, [sid, bad])
        if DEFAULT_SESSION not in svc.sessions:
            add(sid, "negative", f"{name}: wrong session", pre(DEFAULT_SESSION), pos)
        if svc.security:
            add(sid, "negative", f"{name}: locked ECU", pre(EXTENDED_SESSION), pos)
        if sid == 0x22:
            add(sid, "negative", f"{name}: undefined DID", pre(), [0x22, 0xDE, 0xAD])
        if sid == 0x2E:
            ro = next(d for d in spec.dids.values() if not d.writable and d.dynamic is None)
            add(sid, "negative", f"{name}: read-only DID", pre(EXTENDED_SESSION, True), [0x2E, *ro.did.to_bytes(2, "big"), *bytes(ro.length)[:2]])
        if sid == 0x31:
            add(sid, "negative", f"{name}: undefined routine", pre(EXTENDED_SESSION, True), [0x31, svc.subfunctions[0], 0xFF, 0xFF])
        if sid == 0x27:
            key = spec.expected_key()
            add(sid, "positive", f"{name}: correct key unlocks", pre(EXTENDED_SESSION, seed_issued=True), [0x27, 0x02, *key])
            add(sid, "negative", f"{name}: wrong key", pre(EXTENDED_SESSION, seed_issued=True), [0x27, 0x02, *bytes(len(key))])
            add(sid, "negative", f"{name}: key without seed", pre(EXTENDED_SESSION), [0x27, 0x02, *key])
    unused = next(x for x in range(0xBA, 0xFF) if x not in spec.services)
    add(unused, "negative", "Unsupported service", pre(), [unused])
    return cases


def run_case(spec: Spec, case: dict, fault: str | None = None) -> dict:
    p = case["pre"]
    state = EcuState.initial(spec, p["session"], p["unlocked"], p["seed_issued"])
    actual = process(spec, state, parse_hex(case["request"]), fault).response
    return {"actual": fmt(actual), "passed": actual == parse_hex(case["expected"])}
