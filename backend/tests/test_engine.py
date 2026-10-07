import pytest

from app.uds.engine import EcuState, parse_hex, process
from app.uds.testgen import generate, run_case


def run(spec, req, **kw):
    fault = kw.pop("fault", None)
    return process(spec, EcuState.initial(spec, **kw), parse_hex(req), fault)


@pytest.mark.parametrize("req,kw,resp", [
    ("10 03", {}, "50 03 00 32 01 F4"),
    ("3E 00", {}, "7E 00"),
    ("22 F1 86", {"session": 3}, "62 F1 86 03"),
    ("27 01", {"session": 3}, "67 01 12 34"),
    ("27 02 B7 91", {"session": 3, "seed_issued": True}, "67 02"),
    ("2E 01 00 12 34", {"session": 3, "unlocked": True}, "6E 01 00"),
    ("31 01 02 03", {"session": 3, "unlocked": True}, "71 01 02 03 00"),
])
def test_positive(spec, req, kw, resp):
    assert run(spec, req, **kw).response.hex(" ").upper() == resp


@pytest.mark.parametrize("req,kw,nrc", [
    ("BA", {}, 0x11), ("10 7E", {}, 0x12), ("10 03 00", {}, 0x13), ("10", {}, 0x13),
    ("27 02 B7 91", {"session": 3}, 0x24), ("22 DE AD", {}, 0x31), ("2E F1 90 00 01", {"session": 3, "unlocked": True}, 0x31),
    ("2E 01 00 00 64", {"session": 3}, 0x33), ("27 02 00 00", {"session": 3, "seed_issued": True}, 0x35), ("27 01", {}, 0x7F),
])
def test_negative(spec, req, kw, nrc):
    r = run(spec, req, **kw)
    assert r.nrc == nrc and r.response[0] == 0x7F


def test_check_order_session_before_security(spec):
    assert run(spec, "2E 01 00 00 64").nrc == 0x7F  # wrong session wins over locked


def test_session_change_relocks(spec):
    r = run(spec, "10 03", session=3, unlocked=True)
    assert r.state.session == 3 and not r.state.unlocked


def test_write_persists_and_state_is_not_mutated(spec):
    state = EcuState.initial(spec, 3, True)
    r = process(spec, state, parse_hex("2E 01 00 AA BB"))
    assert r.state.values[0x0100] == b"\xAA\xBB" and state.values[0x0100] == b"\x00\x64"


def test_unknown_fault_rejected(spec):
    with pytest.raises(ValueError):
        run(spec, "3E 00", fault="nope")


@pytest.mark.parametrize("text,ok", [("22F190", True), ("0x22, 0xF1,0x90", True), ("", True), ("22 F", False), ("ZZ", False)])
def test_parse_hex(text, ok):
    if ok:
        assert isinstance(parse_hex(text), bytes)
    else:
        with pytest.raises(ValueError):
            parse_hex(text)


def test_generated_suite_passes_reference_and_catches_fault(spec):
    cases = generate(spec)
    assert len(cases) >= 25 and {c["kind"] for c in cases} == {"positive", "negative"}
    assert all(run_case(spec, c)["passed"] for c in cases)
    failing = [c["title"] for c in cases if not run_case(spec, c, "skip_security")["passed"]]
    assert failing and all("locked ECU" in t for t in failing)


def test_suite_covers_every_nrc_and_service(spec):
    cases = generate(spec)
    assert {c["sid"] for c in cases} >= set(spec.services)
    assert {int(c["expected"].split()[2], 16) for c in cases if c["expected"].startswith("7F")} == set(spec.nrcs)
