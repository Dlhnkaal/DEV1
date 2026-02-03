import pytest
import sys 
import os
import fastapi
from fastapi.testclient import TestClient
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import app


@pytest.fixture
def app_client() -> TestClient:
    return TestClient(app)


