# coding: utf-8

from fastapi.testclient import TestClient


from openapi_server.models.error_response import ErrorResponse  # noqa: F401
from openapi_server.models.send_notification_request import SendNotificationRequest  # noqa: F401
from openapi_server.models.send_notification_response import SendNotificationResponse  # noqa: F401


def test_send_notification(client: TestClient):
    """Test case for send_notification

    Enqueue a notification request
    """
    send_notification_request = {"channel":"email","recipient":"recipient","idempotency_key":"idempotency_key","message":"message"}

    headers = {
    }
    # uncomment below to make a request
    #response = client.request(
    #    "POST",
    #    "/v1/notifications:send",
    #    headers=headers,
    #    json=send_notification_request,
    #)

    # uncomment below to assert the status code of the HTTP response
    #assert response.status_code == 200

