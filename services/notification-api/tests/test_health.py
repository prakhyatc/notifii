from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

os.environ["QUEUE_BACKEND"] = "memory"
os.environ["IDEMPOTENCY_BACKEND"] = "memory"
os.environ["EMAIL_PROVIDER"] = "console"

import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "notifications_received_total" in r.text


def test_metrics_json(client):
    r = client.get("/metrics/json")
    assert r.status_code == 200
    data = r.json()
    assert "notifications_received_total" in data


def test_internal_config(client):
    r = client.get("/internal/config")
    assert r.status_code == 200
    data = r.json()
    assert data["queue_backend"] == "memory"
    assert data["email_provider"] == "console"
