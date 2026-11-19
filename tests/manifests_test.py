"""
Tests for the manifest routes and the ManifestRecord model.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from manifestservice.schemas import ManifestRecord


class TestManifestRecord:
    """Tests for the ManifestRecord request model."""

    def test_keeps_extra_fields(self) -> None:
        """Fields other than object_id are kept in the record."""
        record = {"object_id": "dg.1234/abc", "subject_id": "patient_001"}

        assert ManifestRecord(**record).model_dump() == record

    @pytest.mark.parametrize(
        "record", [{}, {"foo": 44}], ids=["empty", "other-fields-only"]
    )
    def test_requires_object_id(self, record: dict) -> None:
        """A record without object_id is rejected."""
        with pytest.raises(ValidationError):
            ManifestRecord(**record)


class TestListManifests:
    """Tests for GET /."""

    def test_returns_manifest_files(
        self, client: TestClient, mocks: dict[str, MagicMock]
    ) -> None:
        """The manifest files in the user's folder are returned."""
        listing, _ = mocks["list_files_in_bucket"].return_value

        r = client.get("/")

        assert r.status_code == 200
        assert r.json() == {"manifests": listing["manifests"]}
        mocks["list_files_in_bucket"].assert_called_once_with("test-bucket", "user-18")


class TestGetManifestFile:
    """Tests for GET /file/{file_name}."""

    def test_returns_file_contents(
        self, client: TestClient, mocks: dict[str, MagicMock]
    ) -> None:
        """The named file in the user's folder is returned as text."""
        r = client.get("/file/manifest-1.json")

        assert r.status_code == 200
        assert r.text == mocks["get_file_contents"].return_value
        mocks["get_file_contents"].assert_called_once_with(
            "test-bucket", "user-18", "manifest-1.json"
        )


class TestCreateManifest:
    """Tests for POST / and PUT /."""

    @pytest.mark.parametrize("method", ["POST", "PUT"])
    def test_stores_manifest_and_returns_filename(
        self, client: TestClient, mocks: dict[str, MagicMock], method: str
    ) -> None:
        """The records are stored with extra fields, and the file name is returned."""
        manifest = [
            {"object_id": "dg.123/abc", "subject_id": "patient_001"},
            {"object_id": "dg.123/def"},
        ]

        r = client.request(method, "/", json=manifest)

        assert r.status_code == 200
        assert r.json() == {"filename": mocks["add_manifest_to_bucket"].return_value[0]}
        assert mocks["add_manifest_to_bucket"].call_args.args[1] == manifest

    @pytest.mark.parametrize(
        "body",
        [
            [{"foo": 44, "bar": 88}],
            [{"obj__id": 44, "subject_id": 88}],
            {"object_id": "dg.123/abc"},
        ],
        ids=["no-object-id", "misspelled-object-id", "not-a-list"],
    )
    def test_invalid_manifest_returns_422(
        self, client: TestClient, mocks: dict[str, MagicMock], body: object
    ) -> None:
        """A body that is not a list of records with object_id is rejected."""
        r = client.post("/", json=body)

        assert r.status_code == 422
        mocks["add_manifest_to_bucket"].assert_not_called()

    @pytest.mark.usefixtures("mocks")
    def test_body_that_is_not_json_returns_422(self, client: TestClient) -> None:
        """A request body that is not valid JSON is rejected."""
        r = client.post(
            "/", content="not json", headers={"Content-Type": "application/json"}
        )

        assert r.status_code == 422
