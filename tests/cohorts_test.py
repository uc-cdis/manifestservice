# pylint: disable=unused-argument

import json as json_utils

from manifestservice.manifests import _list_files_in_bucket


def test_POST_successful_GUID_add(client, mocks):
    """
        Test the Export PFB to Workspace pathway: a cohort is added to the bucket.
    Note that because s3 is being mocked, only an integration test can properly
    verify file creation.
    """
    test_guid = "5183a350-9d56-4084-8a03-6471cafeb7fe"
    post_body = {"guid": test_guid}

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.post("/cohorts", data=json_utils.dumps(post_body), headers=headers)

    assert r.status_code == 200
    assert mocks["_authenticate_user"].call_count == 1
    assert mocks["_get_file_contents"].call_count == 0
    assert mocks["_add_manifest_to_bucket"].call_count == 0
    assert mocks["_add_GUID_to_bucket"].call_count == 1

    json = r.json
    new_guid = json["filename"]

    assert new_guid is not None
    assert type(new_guid) is str


def test_GET_cohorts(client, mocks):
    """
    Test GET /cohorts
    """
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    r = client.get("/cohorts", headers=headers)

    assert r.status_code == 200
    assert mocks["_authenticate_user"].call_count == 1
    assert mocks["_get_file_contents"].call_count == 0
    assert mocks["_add_manifest_to_bucket"].call_count == 0
    assert mocks["_add_GUID_to_bucket"].call_count == 0
    assert mocks["_list_files_in_bucket"].call_count == 1

    json = r.json
    cohorts_returned = json["cohorts"]
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
    assert broken_s3_mocks["_authenticate_user"].call_count == 1

    response = r.json
    assert len(response.keys()) == 1
    assert response["error"] == "Currently unable to connect to s3."


def test_list_files_in_bucket(client, mocked_bucket):
    """
    Test that prefixes are not removed from GUIDs when listing cohorts
    in buckets
    """
    result, ok = _list_files_in_bucket("fake_bucket_name", "fake_folder")
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
