import json as json_utils

from manifestservice import manifests


def test_generate_unique_metadata_filename_basic_date_generation():
    """
    Tests that the _generate_unique_filename_with_timestamp_and_increment() function
    generates a unique filename for metadata file.
    """
    timestamp = "a-b-c"
    users_existing_metadata_files = []
    # pylint: disable=protected-access
    filename = manifests._generate_unique_filename_with_timestamp_and_increment(
        timestamp, users_existing_metadata_files, file_type="metadata"
    )
    # pylint: enable=protected-access
    assert filename == "metadata-a-b-c.json"


def test_post_successful_metadata_add(client, mocks):
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
    response = client.post(
        "/metadata", data=json_utils.dumps(post_body), headers=headers
    )

    assert response.status_code == 200
    assert mocks["_authenticate_user"].call_count == 1
    assert mocks["_get_file_contents"].call_count == 0
    assert mocks["_add_metadata_to_bucket"].call_count == 1
    assert mocks["_add_guid_to_bucket"].call_count == 0

    json = response.json
    returned_filename = json["filename"]

    assert returned_filename is not None
    assert isinstance(returned_filename, str)

    response = client.get("/metadata", headers=headers)
    assert response.status_code == 200
    assert mocks["_authenticate_user"].call_count == 2
    assert mocks["_add_metadata_to_bucket"].call_count == 1
    assert mocks["_list_files_in_bucket"].call_count == 1
    assert mocks["_get_file_contents"].call_count == 0

    json = response.json
    metadata_files = json["external_file_metadata"]
    assert isinstance(metadata_files, list)

    response = client.get("/metadata/" + returned_filename, headers=headers)
    assert response.status_code == 200
    assert mocks["_authenticate_user"].call_count == 3
    assert mocks["_add_metadata_to_bucket"].call_count == 1
    assert mocks["_list_files_in_bucket"].call_count == 1
    assert mocks["_get_file_contents"].call_count == 1


def test_get_metadata(client, mocks):
    """
    Test GET /metadata
    """

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    response = client.get("/metadata", headers=headers)

    assert response.status_code == 200
    assert mocks["_authenticate_user"].call_count == 1
    assert mocks["_get_file_contents"].call_count == 0
    assert mocks["_add_metadata_to_bucket"].call_count == 0
    assert mocks["_list_files_in_bucket"].call_count == 1

    json = response.json
    metadata_returned = json["external_file_metadata"]
    assert len(metadata_returned) == 1
    # From the s3 mock
    assert (
        metadata_returned[0]["filename"] == "metadata-2024-04-26T18-59-21.226440.json"
    )


def test_get_metadata_broken_s3(client, broken_s3_mocks):
    """
    Test GET /metadata if s3 creds are broken
    """

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    response = client.get("/metadata", headers=headers)

    assert response.status_code == 500
    assert broken_s3_mocks["_authenticate_user"].call_count == 1

    response = response.json
    assert len(response.keys()) == 1
    assert response["error"] == "Currently unable to connect to s3."
