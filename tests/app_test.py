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

    mocks["_list_files_in_bucket"] = mocker.patch(
        "manifestservice.manifests._list_files_in_bucket",
        return_value=({
            "manifests": [
                {"filename": "manifest-a-b-c.json"},
            ],
            "cohorts": [
                {"filename": "18e32c12-a053-4ac5-90a5-f01f70b5c2be"}
            ]
            }, True),
    )

    mocks["_add_manifest_to_bucket"] = mocker.patch(
        "manifestservice.manifests._add_manifest_to_bucket",
        return_value=("manifest-xxx.json", True),
    )

    mocks["_get_file_contents"] = mocker.patch(
        "manifestservice.manifests._get_file_contents", return_value=""
    )

    app = create_app()
    return app


def test_generate_unique_manifest_filename_basic_date_generation():
    """
	Tests that the _generate_unique_filename_with_timestamp_and_increment() function
	generates a unique filename containing the given timestamp, based on the files in the
	user's bucket. 
	"""
    timestamp = "a-b-c"
    users_existing_manifest_files = []
    filename = manifests._generate_unique_filename_with_timestamp_and_increment(
        timestamp, users_existing_manifest_files
    )
    assert filename == "manifest-a-b-c.json"

    timestamp = "a-b-c"
    users_existing_manifest_files = ["some-other-file.txt", "another-file.json"]
    filename = manifests._generate_unique_filename_with_timestamp_and_increment(
        timestamp, users_existing_manifest_files
    )
    assert filename == "manifest-a-b-c.json"

    # Case 1: One collision
    timestamp = "a-b-c"
    users_existing_manifest_files = ["manifest-a-b-c.json"]
    filename = manifests._generate_unique_filename_with_timestamp_and_increment(
        timestamp, users_existing_manifest_files
    )
    assert filename == "manifest-a-b-c-1.json"

    # Case 2: Two collisions
    timestamp = "a-b-c"
    users_existing_manifest_files = ["manifest-a-b-c.json", "manifest-a-b-c-1.json"]
    filename = manifests._generate_unique_filename_with_timestamp_and_increment(
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
    filename = manifests._generate_unique_filename_with_timestamp_and_increment(
        timestamp, users_existing_manifest_files
    )
    assert filename == "manifest-a-b-c-3.json"


def test__does_the_user_have_read_access_on_at_least_one_project():
    """
	Tests that the function _does_the_user_have_read_access_on_at_least_one_project()
	provides the correct value for different arborist user_info inputs.
	"""
    project_access_dict = {}
    rv = manifests._does_the_user_have_read_access_on_at_least_one_project(
        project_access_dict
    )
    assert rv is False

    project_access_dict = {"test": ["read-storage", "write-storage", "read"], "DEV": []}
    rv = manifests._does_the_user_have_read_access_on_at_least_one_project(
        project_access_dict
    )
    assert rv is True

    project_access_dict = {
        "test": ["write-storage", "read"],
        "abc123": ["something", "something-else"],
    }
    rv = manifests._does_the_user_have_read_access_on_at_least_one_project(
        project_access_dict
    )
    assert rv is False

    # You need both read and read-storage to use this service.
    project_access_dict = {
        "jenkins": ["read"],
        "abc123": ["something", "something-else"],
    }
    rv = manifests._does_the_user_have_read_access_on_at_least_one_project(
        project_access_dict
    )
    assert rv is False


def test_is_valid_manifest():
    """
	Tests that the function is_valid_manifest() correctly determines
	if the input manifest string is valid.
	"""
    required_keys = ["object_id"]
    test_manifest = [{"foo": 44}]
    is_valid = manifests.is_valid_manifest(test_manifest, required_keys)
    assert is_valid is False

    test_manifest = [{"foo": 44, "bar": 88}]
    is_valid = manifests.is_valid_manifest(test_manifest, required_keys)
    assert is_valid is False

    test_manifest = [{"foo": 44, "object_id": 88}]
    is_valid = manifests.is_valid_manifest(test_manifest, required_keys)
    assert is_valid is True

    test_manifest = [{"subject_id": 44, "object_id": 88}]
    is_valid = manifests.is_valid_manifest(test_manifest, required_keys)
    assert is_valid is True

    test_manifest = [{"object_id": 88}]
    is_valid = manifests.is_valid_manifest(test_manifest, required_keys)
    assert is_valid is True


def test_POST_handles_invalid_json(client):
    """
	Test that we get a 400 if flask.request.json is not filled in.
	"""
    r = client.post("/", data={"a": 1})
    assert r.status_code == 400


def test_POST_handles_invalid_manifest_keys(client):
    """
	Test that we get a 400 if the manifest is missing the required key -- object_id.
	"""
    test_manifest = [{"foo": 44, "bar": 88}]
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.post("/", json=test_manifest, headers=headers)
    assert r.status_code == 400

    test_manifest = [{"obj__id": 44, "subject_id": 88}]
    r = client.post("/", json=test_manifest, headers=headers)
    assert r.status_code == 400


def test_POST_successful_manifest_upload(client):
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
        {"subject_id": random_nums[0], "object_id": random_nums[1]},
        {"subject_id": random_nums[2], "object_id": random_nums[3]},
    ]

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.post("/", data=json_utils.dumps(test_manifest), headers=headers)

    assert r.status_code == 200
    assert mocks["_authenticate_user"].call_count == 1
    assert mocks["_add_manifest_to_bucket"].call_count == 1
    assert mocks["_get_file_contents"].call_count == 0

    json = r.json
    new_filename = json["filename"]

    assert new_filename is not None
    assert type(new_filename) is str

    r = client.get("/", headers=headers)
    assert r.status_code == 200
    assert mocks["_authenticate_user"].call_count == 2
    assert mocks["_add_manifest_to_bucket"].call_count == 1
    assert mocks["_list_files_in_bucket"].call_count == 1
    assert mocks["_get_file_contents"].call_count == 0

    json = r.json
    manifest_files = json["manifests"]
    assert type(manifest_files) is list

    r = client.get("/file/" + new_filename, headers=headers)
    assert r.status_code == 200
    assert mocks["_authenticate_user"].call_count == 3
    assert mocks["_add_manifest_to_bucket"].call_count == 1
    assert mocks["_list_files_in_bucket"].call_count == 1
    assert mocks["_get_file_contents"].call_count == 1

def test_POST_successful_GUID_add(client):
    """
	Test the Export PFB to Workspace pathway: a cohort is added to the bucket.
    Note that because s3 is being mocked, only an integration test can properly 
    verify file creation.
	"""

    test_guid = "5183a350-9d56-4084-8a03-6471cafeb7fe"

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.post("/cohorts", data=json_utils.dumps(test_manifest), headers=headers)

    assert r.status_code == 200
    assert mocks["_authenticate_user"].call_count == 1
    assert mocks["put_pfb_guid"].call_count == 1
    assert mocks["_get_file_contents"].call_count == 0
    assert mocks["get_manifests"].call_count == 0
    assert mocks["_add_manifest_to_bucket"].call_count == 0

    json = r.json
    new_guid = json["filename"]

    assert new_guid is not None
    assert type(new_filename) is str