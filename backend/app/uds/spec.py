"""Typed loader for the synthetic ECU specification (the single source of truth for all rules)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


def _h(value: str) -> int:
    return int(value, 16)


@dataclass(frozen=True)
class Service:
    sid: int
    name: str
    sessions: tuple
    subfunctions: tuple = ()
    length: tuple = (1, 4095)
    length_by_sub: dict = field(default_factory=dict)
    security: bool = False

    def length_for(self, sub: int | None) -> tuple:
        return self.length_by_sub.get(sub, self.length) if sub is not None else self.length


@dataclass(frozen=True)
class Did:
    did: int
    name: str
    length: int
    default: bytes = b""
    writable: bool = False
    dynamic: str | None = None


@dataclass(frozen=True)
class Spec:
    sessions: dict
    services: dict
    dids: dict
    routines: dict
    nrcs: dict
    sections: list
    seed: bytes
    key_xor: int

    def expected_key(self) -> bytes:
        return bytes(b ^ self.key_xor for b in self.seed)


def load_spec(path: str | Path) -> Spec:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    services = {}
    for sid, s in raw["services"].items():
        services[_h(sid)] = Service(
            sid=_h(sid),
            name=s["name"],
            sessions=tuple(_h(x) for x in s["sessions"]),
            subfunctions=tuple(_h(x) for x in s.get("subfunctions", [])),
            length=tuple(s.get("length", (1, 4095))),
            length_by_sub={_h(k): tuple(v) for k, v in s.get("length_by_subfunction", {}).items()},
            security=bool(s.get("security", False)),
        )
    dids = {
        _h(k): Did(_h(k), v["name"], v["length"], bytes.fromhex(v.get("default", "")), v.get("writable", False), v.get("dynamic"))
        for k, v in raw["dids"].items()
    }
    return Spec(
        sessions={_h(k): v for k, v in raw["sessions"].items()},
        services=services,
        dids=dids,
        routines={_h(k): v["name"] for k, v in raw["routines"].items()},
        nrcs={_h(k): v for k, v in raw["nrcs"].items()},
        sections=raw["sections"],
        seed=bytes.fromhex(raw["security"]["seed"]),
        key_xor=_h(raw["security"]["xor"]),
    )
