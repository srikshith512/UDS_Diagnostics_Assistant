def test_health_and_spec(client):
    assert client.get("/api/health").json()["retrieval"] == "lexical"
    body = client.get("/api/spec").json()
    assert len(body["services"]) == 7 and body["sections"][0]["id"] == "§1"


def test_qa_cites_section(client):
    r = client.post("/api/qa", json={"question": "How is the security key calculated?"}).json()
    assert r["citations"][0]["id"] == "§2" and r["mode"] == "extractive"


def test_qa_not_in_spec(client):
    r = client.post("/api/qa", json={"question": "quantum banana"}).json()
    assert r["mode"] == "none" and r["citations"] == []


def test_validate_and_errors(client):
    ok = client.post("/api/validate", json={"request_hex": "10 03"}).json()
    assert ok["spec"]["positive"] and ok["matches"]
    bad = client.post("/api/validate", json={"request_hex": "2E 01 00 00 64", "session": 3, "fault": "skip_security"}).json()
    assert bad["spec"]["nrc"] == 0x33 and not bad["matches"]
    assert client.post("/api/validate", json={"request_hex": "XYZ"}).status_code == 422
    assert client.post("/api/validate", json={"request_hex": "10 03", "session": 9}).status_code == 422
    assert client.post("/api/validate", json={"request_hex": "10 03", "fault": "x"}).status_code == 422


def test_review_workflow_export_coverage_audit(client):
    assert client.post("/api/tests/generate").json()["generated"] >= 25
    assert client.get("/api/export/python").status_code == 409
    assert client.patch("/api/tests/TC-404/review", json={"status": "Approved"}).status_code == 404
    assert client.patch("/api/tests/TC-001/review", json={"status": "Bogus"}).status_code == 422
    client.patch("/api/tests/TC-001/review", json={"status": "Approved", "comment": "ok"})
    client.post("/api/tests/approve-drafts")
    assert client.post("/api/tests/run", json={}).json()["failed"] == 0
    assert client.post("/api/tests/run", json={"fault": "skip_security"}).json()["failed"] == 2
    py = client.get("/api/export/python")
    assert "def test_uds" in py.text and "attachment" in py.headers["content-disposition"]
    assert "testcase TC_001" in client.get("/api/export/capl").text
    cov = client.get("/api/coverage").json()
    assert cov["services"]["covered"] == 7 and cov["nrcs"]["missing"] == []
    actions = [a["action"] for a in client.get("/api/audit", headers={"X-Actor": "alice"}).json()]
    assert "Generated test suite" in actions and "Exported python" in actions


def test_manual_test_and_regenerate_keeps_manual(client):
    tid = client.post("/api/tests", json={"request_hex": "27 01", "session": 3}).json()["id"]
    assert tid == "TC-M01"
    client.post("/api/tests/generate")
    client.post("/api/tests/generate")
    ids = [t["id"] for t in client.get("/api/tests").json()]
    assert "TC-M01" in ids and len(ids) == len(set(ids))


def test_ingest_and_search(client):
    doc = b"# Fuel pump\n\nThe flux capacitor relay must be primed before ignition.\n"
    assert client.post("/api/spec/ingest", files={"file": ("notes.md", doc)}).json()["chunks"] == 1
    r = client.post("/api/qa", json={"question": "flux capacitor relay"}).json()
    assert r["citations"][0]["source"] == "notes.md"
    assert client.post("/api/spec/ingest", files={"file": ("x.exe", b"MZ")}).status_code == 415
    assert client.post("/api/spec/ingest", files={"file": ("x.txt", b"\xff\xfe")}).status_code == 415
    assert client.post("/api/assist/request", json={"description": "read the VIN"}).status_code == 503
