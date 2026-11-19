"""
Tests for the metadata export routes.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


class TestListMetadata:
    """Tests for GET /metadata."""

    def test_returns_metadata_files(
        self, client: TestClient, mocks: dict[str, MagicMock]
    ) -> None:
        """The metadata files in the user's folder are returned."""
        listing, _ = mocks["list_files_in_bucket"].return_value

        r = client.get("/metadata")

        assert r.status_code == 200
        assert r.json() == {"external_file_metadata": listing["metadata"]}
        mocks["list_files_in_bucket"].assert_called_once_with("test-bucket", "user-18")


class TestGetMetadataFile:
    """Tests for GET /metadata/{file_name}."""

    def test_returns_file_contents(
        self, client: TestClient, mocks: dict[str, MagicMock]
    ) -> None:
        """The named file in the user's exported-metadata folder is returned as text."""
        r = client.get("/metadata/metadata-1.json")

        assert r.status_code == 200
        assert r.text == mocks["get_file_contents"].return_value
        mocks["get_file_contents"].assert_called_once_with(
            "test-bucket", "user-18/exported-metadata", "metadata-1.json"
        )


class TestCreateMetadata:
    """Tests for POST /metadata and PUT /metadata."""

    @pytest.mark.parametrize("method", ["POST", "PUT"])
    def test_stores_metadata_and_returns_filename(
        self, client: TestClient, mocks: dict[str, MagicMock], method: str
    ) -> None:
        """The metadata is stored, and the new file name is returned."""
        metadata = [
            {
                "external_oidc_idp": "qdr-keycloak",
                "file_retriever": "QDR",
                "file_id": "45138",
            }
        ]

        r = client.request(method, "/metadata", json=metadata)

        assert r.status_code == 200
        assert r.json() == {"filename": mocks["add_metadata_to_bucket"].return_value[0]}
        assert mocks["add_metadata_to_bucket"].call_args.args[1] == metadata

    def test_body_that_is_not_a_list_returns_422(
        self, client: TestClient, mocks: dict[str, MagicMock]
    ) -> None:
        """A body that is not a list of objects is rejected and not stored."""
        r = client.post("/metadata", json={"file_id": "45138"})

        assert r.status_code == 422
        mocks["add_metadata_to_bucket"].assert_not_called()
