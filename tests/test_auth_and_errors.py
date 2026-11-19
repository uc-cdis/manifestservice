"""
Tests for authentication, the user folder name, and error responses.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from manifestservice.config import Settings
from manifestservice.dependencies import get_user_folder_name
from manifestservice.errors import register_error_handlers

LIST_REQUESTS = [
    pytest.param("GET", "/", None, id="GET /"),
    pytest.param("GET", "/cohorts", None, id="GET /cohorts"),
    pytest.param("GET", "/metadata", None, id="GET /metadata"),
]
FILE_REQUESTS = [
    pytest.param("GET", "/file/manifest-1.json", None, id="GET /file/{name}"),
    pytest.param("GET", "/metadata/metadata-1.json", None, id="GET /metadata/{name}"),
]
CREATE_REQUESTS = [
    pytest.param(method, path, body, id=f"{method} {path}")
    for method in ("POST", "PUT")
    for path, body in [
        ("/", [{"object_id": "dg.123/abc"}]),
        ("/cohorts", {"guid": "5183a350-9d56-4084-8a03-6471cafeb7fe"}),
        ("/metadata", [{"key": "value"}]),
    ]
]


class TestGetUserFolderName:
    """Tests for get_user_folder_name."""

    @pytest.mark.parametrize(
        "prefix, expected",
        [("", "user-42"), (None, "user-42"), ("my-prefix", "my-prefix/user-42")],
        ids=["empty-prefix", "no-prefix", "prefix"],
    )
    def test_folder_name(
        self, settings: Settings, prefix: str | None, expected: str
    ) -> None:
        """The folder is "user-{sub}", inside the prefix folder if a prefix is set."""
        settings = settings.model_copy(update={"prefix": prefix})

        assert get_user_folder_name({"sub": "42"}, settings) == expected


@pytest.mark.usefixtures("mocks")
class TestAuthentication:
    """Tests for token validation on the routes."""

    @pytest.mark.parametrize(
        "method, path, body", LIST_REQUESTS + FILE_REQUESTS + CREATE_REQUESTS
    )
    def test_request_without_token_returns_401(
        self,
        unauthenticated_client: TestClient,
        method: str,
        path: str,
        body: object,
    ) -> None:
        """Every route rejects a request that has no token."""
        r = unauthenticated_client.request(method, path, json=body)

        assert r.status_code == 401

    def test_malformed_token_returns_403(
        self, unauthenticated_client: TestClient
    ) -> None:
        """A bearer token that is not a JWT is rejected."""
        r = unauthenticated_client.get(
            "/", headers={"Authorization": "Bearer not-a-jwt"}
        )

        assert r.status_code == 403


class TestErrorResponses:
    """Tests for error status codes and response bodies."""

    def test_unhandled_exception_returns_500_without_details(self) -> None:
        """An unhandled exception returns 500 without its message in the response."""
        app = FastAPI()
        register_error_handlers(app)

        @app.get("/explode")
        def explode() -> None:
            raise RuntimeError("secret internal details here")

        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/explode")

        assert r.status_code == 500
        assert "secret internal details" not in r.text

    @pytest.mark.parametrize("method, path, body", LIST_REQUESTS + CREATE_REQUESTS)
    def test_s3_failure_returns_500(
        self,
        client: TestClient,
        mocks: dict[str, MagicMock],
        method: str,
        path: str,
        body: object,
    ) -> None:
        """If the S3 call fails, the route returns 500 with only a "detail" key."""
        for name in (
            "list_files_in_bucket",
            "add_manifest_to_bucket",
            "add_guid_to_bucket",
            "add_metadata_to_bucket",
        ):
            mocks[name].return_value = (None, False)

        r = client.request(method, path, json=body)

        assert r.status_code == 500
        assert set(r.json()) == {"detail"}

    @pytest.mark.parametrize("route", ["/file/", "/metadata/"])
    def test_missing_file_returns_404(
        self, client: TestClient, mocks: dict[str, MagicMock], route: str
    ) -> None:
        """A request for a file that does not exist in the bucket returns 404."""
        mocks["get_file_contents"].return_value = None

        assert client.get(route + "missing.json").status_code == 404

    @pytest.mark.usefixtures("mocks")
    @pytest.mark.parametrize("route", ["/file/", "/metadata/"])
    @pytest.mark.parametrize("file_name", ["myFilejson", "manifest.notjson"])
    def test_file_name_without_json_extension_returns_400(
        self, client: TestClient, route: str, file_name: str
    ) -> None:
        """A file name that does not end in ".json" is rejected."""
        assert client.get(route + file_name).status_code == 400
