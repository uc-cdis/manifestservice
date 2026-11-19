"""
Tests for S3 service functions.
"""

import io
import json
from collections.abc import Callable
from datetime import datetime
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError
from pytest_mock import MockerFixture

from manifestservice.config import Settings
from manifestservice.services.s3 import (
    list_files_in_bucket,
    get_file_contents,
    add_manifest_to_bucket,
    add_guid_to_bucket,
    add_metadata_to_bucket,
    _generate_unique_filename_with_timestamp_and_increment,
)

TEST_CLAIMS = {"sub": "42"}
GUID = "5183a350-9d56-4084-8a03-6471cafeb7fe"

ADD_TO_BUCKET_CASES = [
    pytest.param(add_manifest_to_bucket, [{"object_id": "dg.123/abc"}], id="manifest"),
    pytest.param(add_guid_to_bucket, GUID, id="guid"),
    pytest.param(add_metadata_to_bucket, [{"key": "value"}], id="metadata"),
]


@pytest.fixture
def s3(mocker: MockerFixture) -> SimpleNamespace:
    """
    Mock boto3 inside the S3 service.

    The bucket is empty unless a test sets `listing.return_value`. Tests
    configure `listing` (bucket listing), `put` (upload), and `get_object`
    (download), and read the uploaded object's bucket and key from `Object`.
    """
    boto3 = mocker.patch("manifestservice.services.s3.boto3")
    resource = boto3.Session.return_value.resource.return_value
    listing = resource.Bucket.return_value.objects.filter
    listing.return_value = []
    return SimpleNamespace(
        listing=listing,
        Object=resource.Object,
        put=resource.Object.return_value.put,
        get_object=boto3.client.return_value.get_object,
    )


class TestGenerateUniqueFilename:
    """Tests for unique file name generation."""

    @pytest.mark.parametrize(
        "existing, file_type, expected",
        [
            ([], "manifest", "manifest-10-30.json"),
            (["other.txt", "other.json"], "manifest", "manifest-10-30.json"),
            (["manifest-10-30.json"], "manifest", "manifest-10-30-1.json"),
            (
                ["manifest-10-30.json", "manifest-10-30-1.json"],
                "manifest",
                "manifest-10-30-2.json",
            ),
            ([], "metadata", "metadata-10-30.json"),
        ],
        ids=[
            "no-files",
            "unrelated-files",
            "one-collision",
            "two-collisions",
            "metadata",
        ],
    )
    def test_returns_unused_name(
        self, existing: list[str], file_type: str, expected: str
    ) -> None:
        """The name is {type}-{timestamp}.json with ":" as "-", plus "-N" if taken."""
        filename = _generate_unique_filename_with_timestamp_and_increment(
            "10:30", existing, file_type
        )

        assert filename == expected


class TestListFilesInBucket:
    """Tests for list_files_in_bucket."""

    def test_categorizes_files(self, s3: SimpleNamespace) -> None:
        """Files are grouped by folder, and cohort GUIDs keep their prefix."""
        s3.listing.return_value = [
            _s3_object("user-42/manifest-2026.json"),
            _s3_object("user-42/cohorts/some-guid"),
            _s3_object("user-42/cohorts/dg.mytest/prefixed-guid"),
            _s3_object("user-42/exported-metadata/metadata-2026.json"),
        ]

        result, ok = list_files_in_bucket("test-bucket", "user-42")

        assert ok is True
        assert {
            kind: [f["filename"] for f in files] for kind, files in result.items()
        } == {
            "manifests": ["manifest-2026.json"],
            "cohorts": ["some-guid", "dg.mytest/prefixed-guid"],
            "metadata": ["metadata-2026.json"],
        }

    def test_listing_error_returns_none_and_false(self, s3: SimpleNamespace) -> None:
        """An S3 error during listing returns (None, False)."""
        s3.listing.side_effect = Exception("Connection refused")

        assert list_files_in_bucket("test-bucket", "user-42") == (None, False)

    def test_empty_bucket_returns_empty_lists(self, s3: SimpleNamespace) -> None:
        """An empty folder returns an empty list for each category."""
        assert list_files_in_bucket("test-bucket", "user-42") == (
            {"manifests": [], "cohorts": [], "metadata": []},
            True,
        )

    def test_sorts_by_last_modified(self, s3: SimpleNamespace) -> None:
        """Files in a category are ordered oldest first."""
        s3.listing.return_value = [
            _s3_object("user-42/b.json", datetime(2026, 3, 1)),
            _s3_object("user-42/a.json", datetime(2026, 1, 1)),
            _s3_object("user-42/c.json", datetime(2026, 2, 1)),
        ]

        result, ok = list_files_in_bucket("test-bucket", "user-42")

        assert ok is True
        assert [m["filename"] for m in result["manifests"]] == [
            "a.json",
            "c.json",
            "b.json",
        ]


class TestGetFileContents:
    """Tests for get_file_contents."""

    @pytest.mark.parametrize(
        "body",
        [b'[{"object_id": "abc"}]', b"[{'object_id': 'abc'}]"],
        ids=["double-quotes", "single-quotes"],
    )
    def test_returns_body_with_double_quotes(
        self, s3: SimpleNamespace, body: bytes
    ) -> None:
        """The body is returned as a string, with single quotes changed to double."""
        s3.get_object.return_value = {"Body": io.BytesIO(body)}

        content = get_file_contents("test-bucket", "user-42", "manifest.json")

        assert content == '[{"object_id": "abc"}]'

    def test_missing_file_returns_none(self, s3: SimpleNamespace) -> None:
        """A file that does not exist in the bucket returns None."""
        s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )

        assert get_file_contents("test-bucket", "user-42", "missing.json") is None

    @pytest.mark.parametrize("error_code", ["NoSuchBucket", "AccessDenied"])
    def test_other_s3_errors_are_raised(
        self, s3: SimpleNamespace, error_code: str
    ) -> None:
        """S3 errors other than a missing file are raised to the caller."""
        s3.get_object.side_effect = ClientError(
            {"Error": {"Code": error_code}}, "GetObject"
        )

        with pytest.raises(ClientError):
            get_file_contents("test-bucket", "user-42", "manifest.json")


class TestAddToBucket:
    """Tests for the add_*_to_bucket upload functions."""

    def test_manifest_is_uploaded_to_user_folder(
        self, s3: SimpleNamespace, settings: Settings
    ) -> None:
        """A manifest is stored as JSON in a new manifest-*.json in the user folder."""
        manifest = [{"object_id": "dg.123/abc"}]

        filename, ok = add_manifest_to_bucket(TEST_CLAIMS, manifest, settings)

        assert ok is True
        assert filename.startswith("manifest-") and filename.endswith(".json")
        s3.Object.assert_called_once_with("test-bucket", f"user-42/{filename}")
        s3.put.assert_called_once_with(Body=json.dumps(manifest).encode())

    def test_metadata_is_uploaded_to_exported_metadata_folder(
        self, s3: SimpleNamespace, settings: Settings
    ) -> None:
        """Metadata is stored as JSON in a new metadata-*.json in exported-metadata/."""
        metadata = [{"key": "value"}]

        filename, ok = add_metadata_to_bucket(TEST_CLAIMS, metadata, settings)

        assert ok is True
        assert filename.startswith("metadata-") and filename.endswith(".json")
        s3.Object.assert_called_once_with(
            "test-bucket", f"user-42/exported-metadata/{filename}"
        )
        s3.put.assert_called_once_with(Body=json.dumps(metadata).encode())

    def test_guid_is_uploaded_to_cohorts_folder(
        self, s3: SimpleNamespace, settings: Settings
    ) -> None:
        """A new GUID is stored as an empty file named after it in cohorts/."""
        assert add_guid_to_bucket(TEST_CLAIMS, GUID, settings) == (GUID, True)
        s3.Object.assert_called_once_with("test-bucket", f"user-42/cohorts/{GUID}")
        s3.put.assert_called_once_with(Body=b"")

    def test_existing_guid_is_not_uploaded_again(
        self, s3: SimpleNamespace, settings: Settings
    ) -> None:
        """A GUID already in the cohorts folder is returned without an upload."""
        s3.listing.return_value = [_s3_object(f"user-42/cohorts/{GUID}")]

        assert add_guid_to_bucket(TEST_CLAIMS, GUID, settings) == (GUID, True)
        s3.put.assert_not_called()

    @pytest.mark.parametrize("add_to_bucket, body", ADD_TO_BUCKET_CASES)
    def test_listing_error_returns_none_and_false(
        self,
        s3: SimpleNamespace,
        settings: Settings,
        add_to_bucket: Callable[..., tuple[str | None, bool]],
        body: list[dict] | str,
    ) -> None:
        """An S3 error while listing the existing files returns (None, False)."""
        s3.listing.side_effect = Exception("No access")

        assert add_to_bucket(TEST_CLAIMS, body, settings) == (None, False)

    @pytest.mark.parametrize("add_to_bucket, body", ADD_TO_BUCKET_CASES)
    def test_upload_error_returns_false(
        self,
        s3: SimpleNamespace,
        settings: Settings,
        add_to_bucket: Callable[..., tuple[str | None, bool]],
        body: list[dict] | str,
    ) -> None:
        """An S3 error during the upload returns False."""
        s3.put.side_effect = Exception("Access denied")

        _, ok = add_to_bucket(TEST_CLAIMS, body, settings)

        assert ok is False


def _s3_object(
    key: str, last_modified: datetime = datetime(2026, 1, 1)
) -> SimpleNamespace:
    """Build a stand-in for a boto3 ObjectSummary."""
    return SimpleNamespace(key=key, last_modified=last_modified)
