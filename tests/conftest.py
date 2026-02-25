"""
Fixtures for Manifest Service tests.
"""

from datetime import datetime
import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from manifestservice.main import create_app
from manifestservice.config import Settings, get_settings, clear_settings_cache
from manifestservice.dependencies import _validate_and_get_claims


TEST_USER_CLAIMS = {
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


def test_claims():
    """
    Test JWT claims
    """
    return TEST_USER_CLAIMS


def test_settings():
    """
    Test settings to run without needing config.json in the test env.
    """
    return Settings(
        manifest_bucket_name="test-bucket",
        hostname="test.example.com",
        prefix="",
        oidc_issuer="https://test.example.com/user",
    )


@pytest.fixture
def client():
    """
    FastAPI test client.
    """
    clear_settings_cache()
    app = create_app()

    # dependency ovverides
    # https://fastapi.tiangolo.com/advanced/testing-dependencies/#use-the-app-dependency-overrides-attribute
    app.dependency_overrides[get_settings] = test_settings
    app.dependency_overrides[_validate_and_get_claims] = test_claims

    with TestClient(app) as c:
        yield c

    # Cleanup
    app.dependency_overrides.clear()
    clear_settings_cache()


@pytest.fixture
def mocks(mocker):
    """
    Mock S3 functions.
    """
    all_mocks = {}

    all_mocks["list_files_in_bucket"] = mocker.patch(
        "manifestservice.routers.manifests.list_files_in_bucket",
        return_value=(
            {
                "manifests": [
                    {"filename": "manifest-a-b-c.json"},
                ],
                "cohorts": [{"filename": "18e32c12-a053-4ac5-90a5-f01f70b5c2be"}],
                "metadata": [{"filename": "metadata-2024-04-26T18-59-21.226440.json"}],
            },
            True,
        ),
    )

    all_mocks["add_manifest_to_bucket"] = mocker.patch(
        "manifestservice.routers.manifests.add_manifest_to_bucket",
        return_value=("manifest-xxx.json", True),
    )

    all_mocks["get_file_contents"] = mocker.patch(
        "manifestservice.routers.manifests.get_file_contents", return_value=""
    )

    all_mocks["add_guid_to_bucket"] = mocker.patch(
        "manifestservice.routers.manifests.add_guid_to_bucket",
        return_value=("a-guid-value", True),
    )

    all_mocks["add_metadata_to_bucket"] = mocker.patch(
        "manifestservice.routers.manifests.add_metadata_to_bucket",
        return_value=("manifest-xxx.json", True),
    )

    return all_mocks


@pytest.fixture
def broken_s3_mocks(mocker):
    """
    Mock S3 connection failure for error handling tests.

    Migration note:
    - Mock the S3 functions to return (None, False) to simulate connection failure
    - Old way mocked boto3.Session
    """
    all_mocks = {}

    all_mocks["list_files_in_bucket"] = mocker.patch(
        "manifestservice.routers.manifests.list_files_in_bucket",
        return_value=(None, False),
    )

    return all_mocks


@pytest.fixture
def mocked_bucket():
    """
    Mock S3 bucket iteration for testing list_files_in_bucket directly.

    This fixture mocks at the boto3 level for testing the actual S3 service
    functions.
    """

    class MockedS3Object:
        def __init__(self, key):
            self.key = key
            self.last_modified = datetime.now()

    mock = MagicMock()
    mock.return_value = iter(
        [
            MockedS3Object(key="username/my-manifest.json"),
            MockedS3Object(key="username/cohorts/guid-without-prefix"),
            MockedS3Object(key="username/cohorts/dg.mytest/guid-with-prefix"),
        ]
    )

    patcher = patch("boto3.resources.collection.ResourceCollection.__iter__", mock)
    patcher.start()

    yield mock

    patcher.stop()
