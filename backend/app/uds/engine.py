"""Deterministic UDS rule engine and simulated ECU.

The same function serves two roles: with ``fault=None`` it is the *reference rule engine* that
decides what a request should return; with a fault injected it acts as a defective ECU so that
generated tests can be shown to catch real defects. The LLM never influences this module.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .spec import Spec

DEFAULT_SESSION = 0x01
EXTENDED_SESSION = 0x03
FAULTS = ("skip_security",)


def parse_hex(text: str, max_bytes: int = 4095) -> bytes:
    """Parse '22 F1 90', '0x22,0xF1,0x90' or '22F190' into bytes. Raises ValueError with a user-facing message."""
    cleaned = re.sub(r"0x|[\s,:\-]", "", text or "", flags=re.I)
    if cleaned and not re.fullmatch(r"[0-9a-fA-F]+", cleaned):
        raise ValueError("Request contains characters that are not hexadecimal.")
    if len(cleaned) % 2:
        raise ValueError("Request has an odd number of hex digits.")
    if len(cleaned) // 2 > max_bytes:
        raise ValueError(f"Request is longer than {max_bytes} bytes.")
    return bytes.fromhex(cleaned)


def fmt(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


@dataclass
class EcuState:
    session: int = DEFAULT_SESSION
    unlocked: bool = False
    seed_issued: bool = False
    values: dict = field(default_factory=dict)

    def clone(self) -> "EcuState":
        return EcuState(self.session, self.unlocked, self.seed_issued, dict(self.values))

    @classmethod
    def initial(cls, spec: Spec, session: int = DEFAULT_SESSION, unlocked: bool = False, seed_issued: bool = False) -> "EcuState":
        return cls(session, unlocked, seed_issued, {d.did: d.default for d in spec.dids.values() if d.writable})


@dataclass
class Result:
    response: bytes
    state: EcuState
    trace: list
    nrc: int | None = None

    @property
    def positive(self) -> bool:
        return bool(self.response) and self.response[0] != 0x7F


def process(spec: Spec, state: EcuState, request: bytes, fault: str | None = None) -> Result:
    if fault is not None and fault not in FAULTS:
        raise ValueError(f"Unknown fault '{fault}'.")
    st = state.clone()
    trace: list = []
    if not request:
        return Result(b"", st, ["Empty request: nothing to validate."])
    sid = request[0]

    def neg(nrc: int, why: str) -> Result:
        trace.append(f"{why} -> NRC {nrc:02X} ({spec.nrcs.get(nrc, 'unknown')})")
        return Result(bytes([0x7F, sid, nrc]), st, trace, nrc)

    def ok(resp: list, msg: str) -> Result:
        trace.append(msg)
        return Result(bytes(resp), st, trace)

    svc = spec.services.get(sid)
    if svc is None:
        return neg(0x11, f"Service {sid:02X} is not defined in the spec")
    trace.append(f"Service {sid:02X} {svc.name} is supported")

    sub = request[1] & 0x7F if len(request) > 1 else None
    if svc.subfunctions and sub is not None:
        if sub not in svc.subfunctions:
            return neg(0x12, f"Sub-function {sub:02X} is not supported")
        trace.append(f"Sub-function {sub:02X} accepted")

    lo, hi = svc.length_for(sub)
    if not lo <= len(request) <= hi:
        return neg(0x13, f"Length {len(request)} is outside the allowed {lo}" + ("" if lo == hi else f"-{hi}"))
    trace.append(f"Length {len(request)} is valid")

    if st.session not in svc.sessions:
        allowed = "/".join(f"{s:02X}" for s in svc.sessions)
        return neg(0x7F, f"Session {st.session:02X} is not allowed (needs {allowed})")
    trace.append(f"Session {st.session:02X} is allowed")

    if svc.security:
        if fault == "skip_security":
            trace.append("Security check skipped (injected fault)")
        elif not st.unlocked:
            return neg(0x33, "Service requires an unlocked ECU")
        else:
            trace.append("ECU is unlocked")

    if sid == 0x10:
        st.session, st.unlocked, st.seed_issued = sub, False, False
        return ok([0x50, sub, 0x00, 0x32, 0x01, 0xF4], f"Switched to session {sub:02X}; security locked")
    if sid == 0x11:
        st.session, st.unlocked, st.seed_issued = DEFAULT_SESSION, False, False
        return ok([0x51, sub], "ECU reset to the default session")
    if sid == 0x3E:
        return ok([0x7E, 0x00], "Tester present acknowledged")
    if sid == 0x22:
        did = spec.dids.get(int.from_bytes(request[1:3], "big"))
        if did is None:
            return neg(0x31, f"DID {request[1]:02X}{request[2]:02X} is not defined")
        data = bytes([st.session]) if did.dynamic == "session" else st.values.get(did.did, did.default)
        return ok([0x62, *request[1:3], *data], f"Read DID {did.did:04X} ({did.name})")
    if sid == 0x27:
        if sub == 0x01:
            st.seed_issued = True
            return ok([0x67, 0x01, *spec.seed], "Seed issued")
        if not st.seed_issued:
            return neg(0x24, "Key sent before a seed was requested")
        if request[2:] != spec.expected_key():
            st.seed_issued = False
            return neg(0x35, "Key does not match the seed")
        st.unlocked, st.seed_issued = True, False
        return ok([0x67, 0x02], "Key accepted; ECU unlocked")
    if sid == 0x2E:
        did = spec.dids.get(int.from_bytes(request[1:3], "big"))
        if did is None or not did.writable:
            return neg(0x31, f"DID {request[1]:02X}{request[2]:02X} is undefined or read-only")
        if len(request) - 3 != did.length:
            return neg(0x13, f"DID {did.did:04X} needs {did.length} data bytes")
        st.values[did.did] = bytes(request[3:])
        return ok([0x6E, *request[1:3]], f"Wrote DID {did.did:04X} ({did.name})")
    if sid == 0x31:
        rid = int.from_bytes(request[2:4], "big")
        if rid not in spec.routines:
            return neg(0x31, f"Routine {rid:04X} is not defined")
        return ok([0x71, sub, *request[2:4], 0x00], f"Routine {rid:04X} ({spec.routines[rid]}) started")
    return neg(0x11, f"Service {sid:02X} has no simulator implementation")
