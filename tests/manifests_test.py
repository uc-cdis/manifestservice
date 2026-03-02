"""
Tests for manifest routes and Pydantic models.

NOTE - Flask -> FastAPI migration notes:
- r.json (property) -> r.json() (method) - FastAPI TestClient
- Removed _authenticate_user mock assertions (auth via dependency injection)
- _is_valid_manifest() replaced by ManifestRecord Pydantic model validation
- Invalid manifest keys now return 422 (Pydantic) instead of 400
"""

import json as json_utils
import random

import pytest
from pydantic import ValidationError

from manifestservice.schemas import ManifestRecord
from manifestservice.services.s3 import (
    _generate_unique_filename_with_timestamp_and_increment,
)


def test_generate_unique_manifest_filename_basic_date_generation():
    """
    Tests that the _generate_unique_filename_with_timestamp_and_increment() function
    generates a unique filename containing the given timestamp, based on the files in the
    user's bucket.
    """
    timestamp = "a-b-c"
    users_existing_manifest_files = []
    filename = _generate_unique_filename_with_timestamp_and_increment(
        timestamp, users_existing_manifest_files
    )
    assert filename == "manifest-a-b-c.json"

    timestamp = "a-b-c"
    users_existing_manifest_files = ["some-other-file.txt", "another-file.json"]
    filename = _generate_unique_filename_with_timestamp_and_increment(
        timestamp, users_existing_manifest_files
    )
    assert filename == "manifest-a-b-c.json"

    # Case 1: One collision
    timestamp = "a-b-c"
    users_existing_manifest_files = ["manifest-a-b-c.json"]
    filename = _generate_unique_filename_with_timestamp_and_increment(
        timestamp, users_existing_manifest_files
    )
    assert filename == "manifest-a-b-c-1.json"

    # Case 2: Two collisions
    timestamp = "a-b-c"
    users_existing_manifest_files = ["manifest-a-b-c.json", "manifest-a-b-c-1.json"]
    filename = _generate_unique_filename_with_timestamp_and_increment(
        timestamp, users_existing_manifest_files
    )
    assert filename == "manifest-a-b-c-2.json"

    # Case 3: Three collisions. This should never ever happen but eh might as well test it.
    timestamp = "a-b-c"
    users_existing_manifest_files = [
        "manifest-a-b-c.json",
        "manifest-a-b-c-1.json",
        "manifest-a-b-c-2.json",
    ]
    filename = _generate_unique_filename_with_timestamp_and_increment(
        timestamp, users_existing_manifest_files
    )
    assert filename == "manifest-a-b-c-3.json"


def test_manifest_record_requires_object_id():
    """
    Test ManifestRecord rejects records missing object_id.
    """
    record = ManifestRecord(object_id="dg.1234/abc")
    assert record.object_id == "dg.1234/abc"

    with pytest.raises(ValidationError):
        ManifestRecord()

    with pytest.raises(ValidationError):
        ManifestRecord(foo=44)


def test_manifest_record_allows_extra_fields():
    """
    ManifestRecord preserves extra fields.
    """
    record = ManifestRecord(
        object_id="dg.1234/abc", subject_id="patient_001", project="test-project"
    )
    dumped = record.model_dump()
    assert dumped["object_id"] == "dg.1234/abc"
    assert dumped["subject_id"] == "patient_001"
    assert dumped["project"] == "test-project"
    assert len(dumped) == 3


def test_POST_handles_invalid_json(client, mocks):
    """
    Test that we get a 422 if request body is not valid JSON.
    """
    r = client.post("/", data={"a": 1}, headers={"Content-type": "application/json"})
    assert r.status_code == 422


def test_POST_handles_invalid_manifest_keys(client, mocks):
    """
    Test that we get a 422 if the manifest is missing the required key -- object_id.
    """
    test_manifest = [{"foo": 44, "bar": 88}]
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.post("/", json=test_manifest, headers=headers)
    assert r.status_code == 422

    test_manifest = [{"obj__id": 44, "subject_id": 88}]
    r = client.post("/", json=test_manifest, headers=headers)
    assert r.status_code == 422


def test_POST_successful_manifest_upload(client, mocks):
    """
    Test the full user pathway: a manifest is created, listed, and then downloaded.
    Unfortunately, we cannot verify here that the manifest is present in the listed files,
    nor that the filebody is correct, as that would require a real s3 connection.
    Instead, s3 is mocked and we assert that the correct functions are called.
    """

    random_nums = [
        random.randint(1, 101),
        random.randint(1, 101),
        random.randint(1, 101),
        random.randint(1, 101),
    ]
    test_manifest = [
        {"subject_id": str(random_nums[0]), "object_id": str(random_nums[1])},
        {"subject_id": str(random_nums[2]), "object_id": str(random_nums[3])},
    ]

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.post("/", content=json_utils.dumps(test_manifest), headers=headers)

    assert r.status_code == 200
    assert mocks["add_manifest_to_bucket"].call_count == 1
    assert mocks["get_file_contents"].call_count == 0

    json_response = r.json()
    new_filename = json_response["filename"]

    assert new_filename is not None
    assert type(new_filename) is str

    r = client.get("/", headers=headers)
    assert r.status_code == 200
    assert mocks["add_manifest_to_bucket"].call_count == 1
    assert mocks["list_files_in_bucket"].call_count == 1
    assert mocks["get_file_contents"].call_count == 0

    json_response = r.json()
    manifest_files = json_response["manifests"]
    assert type(manifest_files) is list

    r = client.get("/file/" + new_filename, headers=headers)
    assert r.status_code == 200
    assert mocks["add_manifest_to_bucket"].call_count == 1
    assert mocks["list_files_in_bucket"].call_count == 1
    assert mocks["get_file_contents"].call_count == 1
