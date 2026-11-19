"""
Tests for the health check endpoint.
"""

from fastapi.testclient import TestClient


def test_health_check_needs_no_token(unauthenticated_client: TestClient) -> None:
    """/_status returns "Healthy" to a request that has no token."""
    r = unauthenticated_client.get("/_status")

    assert r.status_code == 200
    assert r.json() == {"status": "Healthy"}
