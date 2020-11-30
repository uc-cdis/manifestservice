import boto3
import pytest

from manifestservice.api import create_app


@pytest.fixture
def app(mocker):
    app = create_app()
    return app


@pytest.fixture
def mocks(mocker):
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
    all_mocks = {}

    all_mocks["current_token"] = mocker.patch(
        "manifestservice.manifests.current_token", return_value=test_user
    )

    all_mocks["_authenticate_user"] = mocker.patch(
        "manifestservice.manifests._authenticate_user", return_value=(None, 200)
    )

    all_mocks["_list_files_in_bucket"] = mocker.patch(
        "manifestservice.manifests._list_files_in_bucket",
        return_value=(
            {
                "manifests": [
                    {"filename": "manifest-a-b-c.json"},
                ],
                "cohorts": [{"filename": "18e32c12-a053-4ac5-90a5-f01f70b5c2be"}],
            },
            True,
        ),
    )

    all_mocks["_add_manifest_to_bucket"] = mocker.patch(
        "manifestservice.manifests._add_manifest_to_bucket",
        return_value=("manifest-xxx.json", True),
    )

    all_mocks["_get_file_contents"] = mocker.patch(
        "manifestservice.manifests._get_file_contents", return_value=""
    )

    all_mocks["_add_GUID_to_bucket"] = mocker.patch(
        "manifestservice.manifests._add_GUID_to_bucket",
        return_value=("a-guid-value", True),
    )

    return all_mocks


@pytest.fixture
def broken_s3_mocks(mocker):
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
    all_mocks = {}

    all_mocks["current_token"] = mocker.patch(
        "manifestservice.manifests.current_token", return_value=test_user
    )

    all_mocks["_authenticate_user"] = mocker.patch(
        "manifestservice.manifests._authenticate_user", return_value=(None, 200)
    )

    broken_s3_connection = boto3.Session("a", "b", "c")

    all_mocks["boto3"] = mocker.patch(
        "manifestservice.manifests.boto3.Session", return_value=broken_s3_connection
    )

    return all_mocks
