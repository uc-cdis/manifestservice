import pytest
import requests
import json as json_utils
import random
from manifestservice import manifests

from manifestservice.api import create_app

mocks = {}


@pytest.fixture
def app(mocker):
    test_user = {
        "context": {
            "user": {
                "policies": [
                    "data_upload",
                    "programs.test-read-storage",
                    "programs.test-read",
                ],
                "google": {"proxy_group": None},
                "is_admin": True,
                "name": "example@uchicago.edu",
                "projects": {
                    "test": [
                        "read-storage",
                        "read",
                        "create",
                        "write-storage",
                        "upload",
                        "update",
                        "delete",
                    ]
                },
            }
        },
        "aud": ["data", "user", "fence", "openid"],
        "sub": "18",
    }

    mocks["current_token"] = mocker.patch(
        "manifestservice.manifests.current_token", return_value=test_user
    )

    mocks["_authenticate_user"] = mocker.patch(
        "manifestservice.manifests._authenticate_user", return_value=(None, 200)
    )


    
    def broken_s3_connection(region_name, aws_access_key_id, aws_secret_access_key):
        raise Exception("AWS Creds missing")

    mocks["boto3"] = mocker.patch(
        "manifestservice.manifests.boto3.Session",
        broken_s3_connection
    )

    app = create_app()
    return app


def test_GET_cohorts(client):
    """
	Test GET /cohorts if s3 creds are broken
	"""

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.get("/cohorts", headers=headers)

    assert r.status_code == 500
    assert mocks["_authenticate_user"].call_count == 1

    response = r.json
    assert len(response.keys()) == 1
    # From the s3 mock
    assert response.keys()[0] == "error"
    assert response["error"] == "Currently unable to connect to s3."