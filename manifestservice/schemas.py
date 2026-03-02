"""
Pydantic models for Manifest Service request/response validation.

NOTE - Flask -> FastAPI migration notes:
- In Flask, responses were plain dicts serialized via flask.jsonify().
- In FastAPI, we use Pydantic models to validate and serialize responses.
  Also used to generate OpenAPI docs.
- Request body models `ManifestRecord` and `CohortCreateRequest` replace
  `_is_valid_manifest` and `_is_valid_guid`.
- Invalid input returns 422 instead of 400.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FileItem(BaseModel):
    """A single file entry as returned by S3 listing."""

    filename: str = Field(..., examples=["manifest-2024-01-15T10-30-00.json"])
    last_modified: str | None = Field(
        default=None,
        examples=["2024-01-15 10:30:00"],
    )
    last_modified_timestamp: float | None = Field(default=None)


class FilenameResponse(BaseModel):
    """Response returned when a file is created (PUT/POST endpoints)."""

    filename: str = Field(..., examples=["manifest-2024-01-15T10-30-00.json"])


class HealthCheckResponse(BaseModel):
    """Response for the /_status health check endpoint."""

    status: str = Field(..., examples=["Healthy"])


class ManifestListResponse(BaseModel):
    """Response for GET / — list of user's manifest files."""

    manifests: list[FileItem]


class ManifestRecord(BaseModel):
    """
    A single record within a manifest upload.

    Each record must contain at least an `object_id` key.
    Additional keys (subject_id, etc.) are preserved via extra="allow".
    """

    model_config = ConfigDict(extra="allow")

    object_id: str = Field(
        ...,
        description="DRS object identifier",
        examples=["dg.1234/abc-def-123"],
    )


class CohortListResponse(BaseModel):
    """Response for GET /cohorts — list of user's cohort GUIDs."""

    cohorts: list[FileItem]


class CohortCreateRequest(BaseModel):
    """
    Request body for PUT/POST /cohorts.

    Replaces the manual `_is_valid_guid()` validation helper.
    The GUID is validated via a field_validator to match UUID format
    (with optional prefix).
    """

    guid: str = Field(
        ...,
        description="PFB GUID to store as a cohort",
        examples=["5183a350-9d56-4084-8a03-6471cafeb7fe"],
    )

    @field_validator("guid")
    @classmethod
    def validate_guid(cls, v: str) -> str:
        pattern = re.compile(
            r"^.*[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-"
            r"[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$",
            re.I,
        )
        if not pattern.match(str(v)):
            raise ValueError(f"The provided GUID: {v} is invalid.")
        return v


class MetadataListResponse(BaseModel):
    """Response for GET /metadata — list of exported metadata files."""

    external_file_metadata: list[FileItem]
