"""
Tests for metadata export routes and filename generation.

NOTE - Flask -> FastAPI migration notes:
- r.json (property) -> r.json() (method) - FastAPI TestClient
- Error response key changed from "error" to "detail"
- Removed _authenticate_user mock assertions (auth via dependency injection)
"""

import json as json_utils

from manifestservice.services.s3 import (
    _generate_unique_filename_with_timestamp_and_increment,
)


def test_generate_unique_metadata_filename_basic_date_generation():
    """
    Tests that the _generate_unique_filename_with_timestamp_and_increment() function
    generates a unique filename for metadata file.
    """
    timestamp = "a-b-c"
    users_existing_metadata_files = []
    filename = _generate_unique_filename_with_timestamp_and_increment(
        timestamp, users_existing_metadata_files, file_type="metadata"
    )
    assert filename == "metadata-a-b-c.json"


def test_POST_successful_metadata_add(client, mocks):
    """
    Test the Export metadata to Workspace pathway: a metadata file is added to the bucket.
    Note that because s3 is being mocked, only an integration test can properly
    verify file creation.
    """
    test_metadata_contents = [
        {
            "external_oidc_idp": "qdr-keycloak",
            "file_retriever": "QDR",
            "file_id": "45138",
        }
    ]
    post_body = test_metadata_contents

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.post("/metadata", content=json_utils.dumps(post_body), headers=headers)

    assert r.status_code == 200
    assert mocks["get_file_contents"].call_count == 0
    assert mocks["add_metadata_to_bucket"].call_count == 1
    assert mocks["add_guid_to_bucket"].call_count == 0

    json_response = r.json()
    returned_filename = json_response["filename"]

    assert returned_filename is not None
    assert type(returned_filename) is str

    r = client.get("/metadata", headers=headers)
    assert r.status_code == 200
    assert mocks["add_metadata_to_bucket"].call_count == 1
    assert mocks["list_files_in_bucket"].call_count == 1
    assert mocks["get_file_contents"].call_count == 0

    json_response = r.json()
    metadata_files = json_response["external_file_metadata"]
    assert type(metadata_files) is list

    r = client.get("/metadata/" + returned_filename, headers=headers)
    assert r.status_code == 200
    assert mocks["add_metadata_to_bucket"].call_count == 1
    assert mocks["list_files_in_bucket"].call_count == 1
    assert mocks["get_file_contents"].call_count == 1


def test_GET_metadata(client, mocks):
    """
    Test GET /metadata
    """
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.get("/metadata", headers=headers)

    assert r.status_code == 200
    assert mocks["get_file_contents"].call_count == 0
    assert mocks["add_metadata_to_bucket"].call_count == 0
    assert mocks["list_files_in_bucket"].call_count == 1

    json_response = r.json()
    metadata_returned = json_response["external_file_metadata"]
    assert len(metadata_returned) == 1
    # From the s3 mock
    assert (
        metadata_returned[0]["filename"] == "metadata-2024-04-26T18-59-21.226440.json"
    )


def test_GET_metadata_broken_s3(client, broken_s3_mocks):
    """
    Test GET /metadata if s3 creds are broken
    """
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.get("/metadata", headers=headers)

    assert r.status_code == 500

    response = r.json()
    assert len(response.keys()) == 1
    assert response["detail"] == "Currently unable to connect to S3."
