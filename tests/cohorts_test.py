"""
Tests for cohort/PFB routes, S3 list function, and CohortCreateRequest model.

NOTE - Flask -> FastAPI migration notes:
- r.json (property) -> r.json() (method) - FastAPI TestClient
- Error response key changed from "error" to "detail"
- Removed _authenticate_user mock assertions (auth via dependency injection)
- _is_valid_guid() replaced by CohortCreateRequest Pydantic model validation
- Invalid GUID now returns 422 (Pydantic) instead of 400
"""

import json as json_utils

import pytest
from pydantic import ValidationError

from manifestservice.schemas import CohortCreateRequest
from manifestservice.services.s3 import list_files_in_bucket


def test_POST_successful_GUID_add(client, mocks):
    """
    Test the Export PFB to Workspace pathway: a cohort is added to the bucket.
    Note that because s3 is being mocked, only an integration test can properly
    verify file creation.
    """
    test_guid = "5183a350-9d56-4084-8a03-6471cafeb7fe"
    post_body = {"guid": test_guid}

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.post("/cohorts", content=json_utils.dumps(post_body), headers=headers)

    assert r.status_code == 200
    assert mocks["get_file_contents"].call_count == 0
    assert mocks["add_manifest_to_bucket"].call_count == 0
    assert mocks["add_guid_to_bucket"].call_count == 1

    json_response = r.json()
    new_guid = json_response["filename"]

    assert new_guid is not None
    assert type(new_guid) is str


def test_GET_cohorts(client, mocks):
    """
    Test GET /cohorts
    """
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.get("/cohorts", headers=headers)

    assert r.status_code == 200
    assert mocks["get_file_contents"].call_count == 0
    assert mocks["add_manifest_to_bucket"].call_count == 0
    assert mocks["add_guid_to_bucket"].call_count == 0
    assert mocks["list_files_in_bucket"].call_count == 1

    json_response = r.json()
    cohorts_returned = json_response["cohorts"]
    assert len(cohorts_returned) == 1
    # From the s3 mock
    assert cohorts_returned[0]["filename"] == "18e32c12-a053-4ac5-90a5-f01f70b5c2be"


def test_GET_cohorts_broken_s3(client, broken_s3_mocks):
    """
    Test GET /cohorts if s3 creds are broken
    """
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.get("/cohorts", headers=headers)

    assert r.status_code == 500

    response = r.json()
    assert len(response.keys()) == 1
    assert response["detail"] == "Currently unable to connect to S3."


def test_list_files_in_bucket(client, mocked_bucket):
    """
    Test that prefixes are not removed from GUIDs when listing cohorts
    in buckets

    Note: This test mocks at the boto3 level to test the actual S3 service
    function. It doesn't go through the HTTP routes.
    """
    result, ok = list_files_in_bucket("fake_bucket_name", "fake_folder")
    assert ok, result

    manifests = result["manifests"]
    assert len(manifests) == 1
    assert manifests[0]["filename"] == "my-manifest.json"

    cohorts = result["cohorts"]
    assert len(cohorts) == 2
    for cohort in cohorts:
        if "without-prefix" in cohort["filename"]:
            assert cohort["filename"] == "guid-without-prefix"
        else:
            assert cohort["filename"] == "dg.mytest/guid-with-prefix"


def test_cohort_create_request_validates_guid():
    """
    Tests that CohortCreateRequest rejects invalid GUID formats.
    """
    # Valid GUIDs
    CohortCreateRequest(guid="5183a350-9d56-4084-8a03-6471cafeb7fe")
    CohortCreateRequest(guid="dg.1234/5183a350-9d56-4084-8a03-6471cafeb7fe")

    # Invalid GUIDs
    with pytest.raises(ValidationError):
        CohortCreateRequest(guid="not-a-guid")

    with pytest.raises(ValidationError):
        CohortCreateRequest(guid="")

    with pytest.raises(ValidationError):
        CohortCreateRequest(guid="12345")


def test_POST_invalid_guid_returns_422(client, mocks):
    """
    Test that posting an invalid GUID returns 422.
    """
    post_body = {"guid": "not-a-valid-guid"}
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.post("/cohorts", content=json_utils.dumps(post_body), headers=headers)
    assert r.status_code == 422
    assert mocks["add_guid_to_bucket"].call_count == 0
