"""Tests for /v1/notifications:send and related endpoints."""

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

VALID_PAYLOAD = {
    "channel": "email",
    "recipient": "test@example.com",
    "message": "Hello from integration test",
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestSendNotification:
    def test_send_returns_202(self, client):
        r = client.post("/v1/notifications:send", json=VALID_PAYLOAD)
        assert r.status_code == 202
        data = r.json()
        assert data["status"] == "queued"
        assert "message_id" in data

    def test_send_with_idempotency_key(self, client):
        payload = {**VALID_PAYLOAD, "idempotency_key": "test-idem-unique-001"}
        r = client.post("/v1/notifications:send", json=payload)
        assert r.status_code == 202
        first_id = r.json()["message_id"]

        r2 = client.post("/v1/notifications:send", json=payload)
        assert r2.status_code == 202
        assert r2.json()["message_id"] == first_id

    def test_send_missing_channel(self, client):
        r = client.post("/v1/notifications:send", json={"recipient": "a@b.com", "message": "hi"})
        assert r.status_code == 422

    def test_send_empty_recipient(self, client):
        r = client.post("/v1/notifications:send", json={"channel": "email", "recipient": "", "message": "hi"})
        assert r.status_code == 422

    def test_send_empty_message(self, client):
        r = client.post(
            "/v1/notifications:send", json={"channel": "email", "recipient": "a@b.com", "message": ""}
        )
        assert r.status_code == 422

    def test_send_message_too_long(self, client):
        payload = {**VALID_PAYLOAD, "message": "x" * 5001}
        r = client.post("/v1/notifications:send", json=payload)
        assert r.status_code == 422

    def test_send_invalid_channel(self, client):
        payload = {**VALID_PAYLOAD, "channel": "carrier_pigeon"}
        r = client.post("/v1/notifications:send", json=payload)
        assert r.status_code == 422

    def test_request_id_header_propagated(self, client):
        r = client.post(
            "/v1/notifications:send",
            json=VALID_PAYLOAD,
            headers={"x-request-id": "trace-abc-123"},
        )
        assert r.status_code == 202
        assert r.headers.get("x-request-id") == "trace-abc-123"

    def test_send_sms_channel_accepted(self, client):
        payload = {**VALID_PAYLOAD, "channel": "sms", "recipient": "+15551234567"}
        r = client.post("/v1/notifications:send", json=payload)
        assert r.status_code == 202


class TestFailureSimulation:
    def test_toggle_provider_failure(self, client):
        r = client.post("/internal/simulate/provider-failure?enable=true")
        assert r.status_code == 200
        assert r.json()["enabled"] is True

        r = client.post("/internal/simulate/provider-failure?enable=false")
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    def test_toggle_slow_delivery(self, client):
        r = client.post("/internal/simulate/slow-delivery?enable=true")
        assert r.status_code == 200
        assert r.json()["enabled"] is True

        r = client.post("/internal/simulate/slow-delivery?enable=false")
        assert r.status_code == 200
        assert r.json()["enabled"] is False


class TestQueueEndpoints:
    def test_queue_depth(self, client):
        r = client.get("/v1/queue/depth")
        assert r.status_code == 200
        assert "queue_depth" in r.json()

    def test_dlq_messages(self, client):
        r = client.get("/v1/queue/dlq")
        assert r.status_code == 200
        assert "dlq_messages" in r.json()

    def test_recent_notifications(self, client):
        r = client.get("/v1/notifications/recent")
        assert r.status_code == 200


class TestDemoEndpoints:
    def test_demo_seed(self, client):
        r = client.post("/demo/seed")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "seeded"
        assert data["count"] == 5
        assert len(data["messages"]) == 5

    def test_demo_send_test(self, client):
        r = client.post("/demo/send-test?recipient=test@demo.com&message=Hello+test")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "queued"
        assert data["recipient"] == "test@demo.com"
        assert "message_id" in data

    def test_demo_activity(self, client):
        r = client.get("/demo/activity")
        assert r.status_code == 200
        data = r.json()
        assert "activity" in data
        assert "count" in data
