"""
Tests for the cohort routes and the CohortCreateRequest model.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from manifestservice.schemas import CohortCreateRequest

GUID = "5183a350-9d56-4084-8a03-6471cafeb7fe"


class TestCohortCreateRequest:
    """Tests for the CohortCreateRequest request model."""

    @pytest.mark.parametrize(
        "guid",
        [
            GUID,
            GUID.upper(),
            "dg.1234/" + GUID,
            "dg.mytest/" + GUID,
            "DG.4DFC/" + GUID.upper(),
        ],
    )
    def test_accepts_guid(self, guid: str) -> None:
        """A UUID with an optional one-segment prefix is accepted, in any case."""
        assert CohortCreateRequest(guid=guid).guid == guid

    @pytest.mark.parametrize(
        "guid",
        [
            "",
            "12345",
            "not-a-guid",
            "junk" + GUID,
            "a/b/" + GUID,
            "../" + GUID,
            "/" + GUID,
            "../../other-user/cohorts/" + GUID,
        ],
    )
    def test_rejects_guid(self, guid: str) -> None:
        """Anything but a UUID with an optional one-segment prefix is rejected."""
        with pytest.raises(ValidationError):
            CohortCreateRequest(guid=guid)


class TestListCohorts:
    """Tests for GET /cohorts."""

    def test_returns_cohort_files(
        self, client: TestClient, mocks: dict[str, MagicMock]
    ) -> None:
        """The cohort files in the user's folder are returned."""
        listing, _ = mocks["list_files_in_bucket"].return_value

        r = client.get("/cohorts")

        assert r.status_code == 200
        assert r.json() == {"cohorts": listing["cohorts"]}
        mocks["list_files_in_bucket"].assert_called_once_with("test-bucket", "user-18")


class TestAddCohort:
    """Tests for POST /cohorts and PUT /cohorts."""

    @pytest.mark.parametrize("method", ["POST", "PUT"])
    def test_stores_guid_and_returns_it(
        self, client: TestClient, mocks: dict[str, MagicMock], method: str
    ) -> None:
        """The GUID is stored, and the stored name is returned."""
        r = client.request(method, "/cohorts", json={"guid": GUID})

        assert r.status_code == 200
        assert r.json() == {"filename": mocks["add_guid_to_bucket"].return_value[0]}
        assert mocks["add_guid_to_bucket"].call_args.args[1] == GUID

    def test_invalid_guid_returns_422(
        self, client: TestClient, mocks: dict[str, MagicMock]
    ) -> None:
        """An invalid GUID is rejected and not stored."""
        r = client.post("/cohorts", json={"guid": "not-a-valid-guid"})

        assert r.status_code == 422
        mocks["add_guid_to_bucket"].assert_not_called()
