import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ["RVI_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["RVI_EVIDENCE_DIR"] = f"{_tmp}/evidence"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
