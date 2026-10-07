import pytest
from fastapi.testclient import TestClient

from app.config import ROOT, Settings
from app.main import create_app
from app.uds.spec import load_spec


@pytest.fixture(scope="session")
def spec():
    return load_spec(ROOT / "data" / "ecu_spec.json")


@pytest.fixture()
def client(tmp_path):
    settings = Settings(db_path=str(tmp_path / "t.db"), chroma_dir=str(tmp_path / "c"), retrieval="lexical", llm_enabled=False)
    with TestClient(create_app(settings)) as c:
        yield c
