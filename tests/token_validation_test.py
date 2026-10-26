"""
Tests that access tokens are validated end to end through authutils before any route is served.

Nothing here mocks authutils: tokens are signed with a throwaway RSA key and served from a local
issuer, so the OIDC discovery, JWKS fetch, signature check and claim checks all run for real.
That is what catches an authutils upgrade that changes how a token is accepted or rejected.

AWS is mocked, since these tests are about who gets in, not what is stored.
"""

import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from unittest.mock import MagicMock, patch

import flask
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from flask.testing import FlaskClient
from jwt.algorithms import RSAAlgorithm

from manifestservice import manifests

KEY_ID = "test-key"
AUDIENCE = "gen3"
BUCKET_NAME = "test-bucket"
SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
# Not served by the issuer, so a token it signs fails signature verification.
UNKNOWN_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# Every route in the blueprint, as (HTTP method, path). Each one starts by authenticating.
ROUTES = [
    ("GET", "/manifests/"),
    ("GET", "/manifests/file/manifest.json"),
    ("PUT", "/manifests/"),
    ("POST", "/manifests/"),
    ("GET", "/manifests/cohorts"),
    ("PUT", "/manifests/cohorts"),
    ("POST", "/manifests/cohorts"),
    ("GET", "/manifests/metadata"),
    ("GET", "/manifests/metadata/metadata.json"),
    ("PUT", "/manifests/metadata"),
    ("POST", "/manifests/metadata"),
]


@pytest.fixture(scope="module")
def issuer() -> Iterator[str]:
    """
    Serve OIDC discovery and a JWKS for SIGNING_KEY from a local issuer.

    Bound to a free port, so each run gets an issuer URL nothing else has used. authutils caches
    public keys per issuer for the life of the process, and a fresh URL keeps that cache from
    carrying over between runs in the same worker.

    Yields:
        str: The issuer URL, as it appears in a token's `iss` claim.
    """
    jwk = json.loads(RSAAlgorithm.to_jwk(SIGNING_KEY.public_key()))
    jwk.update(kid=KEY_ID, alg="RS256", use="sig")
    server = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    issuer_url = f"http://127.0.0.1:{server.server_port}/user"

    class IssuerHandler(BaseHTTPRequestHandler):
        """Answers the two requests authutils makes to find an issuer's keys."""

        def do_GET(self) -> None:  # pylint: disable=invalid-name
            """
            Return the discovery document or the key set, depending on the path.

            The name is fixed by BaseHTTPRequestHandler, which dispatches GET requests to `do_GET`.
            """
            if self.path.endswith("/.well-known/openid-configuration"):
                body = {"issuer": issuer_url, "jwks_uri": f"{issuer_url}/jwt/keys"}
            else:
                body = {"keys": [jwk]}
            payload = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(
            self, format: str, *args: Any
        ) -> None:  # noqa: A002 - overridden signature
            """Keep request lines out of the test output."""

    server.RequestHandlerClass = IssuerHandler
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield issuer_url
    server.shutdown()
    server.server_close()


@pytest.fixture
def client(issuer: str) -> FlaskClient:
    """A test client for a minimal app that serves just the manifests blueprint."""
    app = flask.Flask(__name__)
    app.config.update(
        TESTING=True,
        # The audience a token must carry, as read by _authenticate_user.
        AUTHZ_AUDIENCE=AUDIENCE,
        MANIFEST_BUCKET_NAME=BUCKET_NAME,
        # authutils only trusts issuers named in OIDC_ISSUER, USER_API or BASE_URL.
        OIDC_ISSUER=issuer,
    )
    app.register_blueprint(manifests.blueprint, url_prefix="/manifests")
    return app.test_client()


@pytest.fixture(autouse=True)
def no_aws() -> Iterator[MagicMock]:
    """Make sure no test can reach AWS. A request that gets past auth fails loudly instead."""
    with patch.object(manifests, "boto3") as boto3_mock:
        boto3_mock.Session.side_effect = AssertionError("AWS must not be reached")
        boto3_mock.client.side_effect = AssertionError("AWS must not be reached")
        yield boto3_mock


@pytest.fixture
def list_files() -> Iterator[MagicMock]:
    """Stand in for the bucket listing, returning an empty folder."""
    empty_folder = {"manifests": [], "cohorts": [], "metadata": []}
    with patch.object(
        manifests, "_list_files_in_bucket", return_value=(empty_folder, True)
    ) as mock:
        yield mock


def make_token(issuer: str, key: rsa.RSAPrivateKey = SIGNING_KEY, **claims: Any) -> str:
    """
    Build an encoded bearer token shaped like a Gen3 access token.

    Args:
        issuer (str): Value for the `iss` claim.
        key (rsa.RSAPrivateKey): Key to sign with.
        **claims (Any): Claims to add or override.

    Returns:
        str: The encoded token.
    """
    now = int(time.time())
    payload = {
        "iss": issuer,
        "sub": "42",
        "aud": [AUDIENCE],
        "scope": ["user", "openid"],
        "pur": "access",
        "iat": now,
        "exp": now + 300,
        "jti": "test-jti",
        "context": {"user": {"name": "test-user"}},
    }
    payload.update(claims)
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": KEY_ID})


def bearer(token: str) -> dict[str, str]:
    """Headers carrying `token` as a bearer token."""
    return {"Authorization": f"Bearer {token}"}


def test_valid_token_is_accepted(
    client: FlaskClient, issuer: str, list_files: MagicMock
) -> None:
    """A valid access token gets through, and the user's folder comes from its `sub` claim."""
    response = client.get("/manifests/", headers=bearer(make_token(issuer)))

    assert response.status_code == 200
    assert response.get_json() == {"manifests": []}
    list_files.assert_called_once_with(BUCKET_NAME, "user-42")


@pytest.mark.parametrize(
    ("case", "overrides"),
    [
        ("wrong purpose", {"pur": "refresh"}),
        ("missing scope", {"scope": ["openid"]}),
        ("wrong audience", {"aud": ["not-gen3"]}),
        ("expired", {"iat": int(time.time()) - 600, "exp": int(time.time()) - 300}),
        ("unknown signing key", {"key": UNKNOWN_KEY}),
    ],
)
def test_invalid_token_is_rejected(
    client: FlaskClient,
    issuer: str,
    list_files: MagicMock,
    case: str,
    overrides: dict[str, Any],
) -> None:
    """A token failing any one validation check is refused, and nothing is read from the bucket."""
    response = client.get(
        "/manifests/", headers=bearer(make_token(issuer, **overrides))
    )

    assert response.status_code == 403, case
    assert response.get_json() == {"error": "Please log in."}
    list_files.assert_not_called()


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_every_route_rejects_a_missing_token(
    client: FlaskClient, list_files: MagicMock, method: str, path: str
) -> None:
    """No route can be used without credentials."""
    response = client.open(path, method=method, json={})

    assert response.status_code == 403
    assert response.get_json() == {"error": "Please log in."}
    list_files.assert_not_called()


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_every_route_rejects_an_invalid_token(
    client: FlaskClient, issuer: str, list_files: MagicMock, method: str, path: str
) -> None:
    """No route accepts a token that fails validation."""
    token = make_token(issuer, key=UNKNOWN_KEY)

    response = client.open(path, method=method, headers=bearer(token), json={})

    assert response.status_code == 403
    assert response.get_json() == {"error": "Please log in."}
    list_files.assert_not_called()
