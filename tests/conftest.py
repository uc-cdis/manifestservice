"""
Fixtures for Manifest Service tests.
"""

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from manifestservice.config import Settings, get_settings
from manifestservice.dependencies import _validate_and_get_claims
from manifestservice.main import create_app

USER_CLAIMS = {"sub": "18"}


@pytest.fixture
def settings() -> Settings:
    """Settings for a test deployment with no folder prefix."""
    return Settings(
        manifest_bucket_name="test-bucket", hostname="test.example.com", prefix=""
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """The app, configured with the `settings` fixture."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return app


@pytest.fixture
def unauthenticated_client(app: FastAPI) -> Iterator[TestClient]:
    """A client for the app that validates tokens the same way production does."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """A client for the app, signed in as the user with sub "18"."""
    app.dependency_overrides[_validate_and_get_claims] = lambda: USER_CLAIMS
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mocks(mocker: MockerFixture) -> dict[str, MagicMock]:
    """
    Mock the S3 service functions that the routes call, keyed by function name.

    The user's folder lists one manifest, one cohort, and one metadata file.
    Every upload succeeds.
    """
    listing = {
        "manifests": [_file_item("manifest-1.json")],
        "cohorts": [_file_item("18e32c12-a053-4ac5-90a5-f01f70b5c2be")],
        "metadata": [_file_item("metadata-1.json")],
    }
    return_values = {
        "list_files_in_bucket": (listing, True),
        "get_file_contents": '[{"object_id": "dg.123/abc"}]',
        "add_manifest_to_bucket": ("manifest-2.json", True),
        "add_guid_to_bucket": ("5183a350-9d56-4084-8a03-6471cafeb7fe", True),
        "add_metadata_to_bucket": ("metadata-2.json", True),
    }
    return {
        name: mocker.patch(
            f"manifestservice.routers.manifests.{name}", return_value=value
        )
        for name, value in return_values.items()
    }


def _file_item(filename: str) -> dict:
    """Build one entry of a list_files_in_bucket result."""
    return {
        "filename": filename,
        "last_modified": "2026-01-01 00:00:00",
        "last_modified_timestamp": 1767225600.0,
    }
