"""
Manifest, Cohort, and Metadata routes for Manifest Service.

NOTE - Flask -> FastAPI migration notes:
- @blueprint.route("/", methods=["GET"]) -> @router.get("/")
- flask.jsonify(dict), status_code -> return dict (FastAPI auto-serializes)
- Request body validated via Pydantic models (ManifestRecord, CohortCreateRequest)
- Manual _authenticate_user() call -> CurrentUserClaims dependency injected
- flask.current_app.config -> settings parameter injected by FastAPI
- BREAKING CHANGES - HTTP exceptions replace (jsonify(error), status_code)
    - 500 will now return "detail" not "error"
    - 400 will be 422 for input validation errors
    - 403 now covered by authutils "detail": Bad bearer token
"""

import html
from typing import Any

from cdislogging import get_logger
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from ..dependencies import CurrentUserClaims, SettingsDep, get_user_folder_name
from ..schemas import (
    CohortCreateRequest,
    CohortListResponse,
    FilenameResponse,
    ManifestListResponse,
    ManifestRecord,
    MetadataListResponse,
)
from ..services.s3 import (
    list_files_in_bucket,
    get_file_contents,
    add_manifest_to_bucket,
    add_guid_to_bucket,
    add_metadata_to_bucket,
)

logger = get_logger("manifestservice_logger", log_level="info")

router = APIRouter()


@router.get("/", tags=["manifests"], summary="List user's manifests")
def get_manifests(
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> ManifestListResponse:
    """
    Returns a list of filenames corresponding to the user's manifests.

    The appropriate folder is determined from the user's JWT claims (sub field).
    """
    folder_name = get_user_folder_name(claims, settings)

    result, ok = list_files_in_bucket(settings.manifest_bucket_name, folder_name)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Currently unable to connect to S3."
        )

    return ManifestListResponse(manifests=result["manifests"])


@router.get(
    "/file/{file_name}",
    tags=["manifests"],
    summary="Get manifest file contents",
)
def get_manifest_file(
    file_name: str,
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> PlainTextResponse:
    """
    Returns the requested manifest file from the user's folder.

    The file_name argument should be of the form "manifest-timestamp.json".
    The user folder prefix is determined from JWT claims.
    """
    file_name = html.escape(file_name)
    if not file_name.endswith("json"):
        raise HTTPException(
            status_code=400,
            detail="Incorrect usage. You can only use this pathway to request files of type JSON.",
        )

    folder_name = get_user_folder_name(claims, settings)

    content = get_file_contents(settings.manifest_bucket_name, folder_name, file_name)
    return PlainTextResponse(content=content)


@router.put("/", tags=["manifests"], summary="Add manifest to S3 bucket")
@router.post("/", tags=["manifests"], summary="Add manifest to S3 bucket")
def put_manifest(
    manifest_json: list[ManifestRecord],
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> FilenameResponse:
    """
    Add manifest to S3 bucket.

    The manifest format must be a list of objects, where each object contains
    at least an "object_id" key.

    Example request body:
    ```json
    [{"object_id": "dg.1234/abc-def-123", "subject_id": "patient_001"}]
    ```
    """
    manifest_dicts = [record.model_dump() for record in manifest_json]

    result, ok = add_manifest_to_bucket(claims, manifest_dicts, settings)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Currently unable to connect to S3."
        )

    return FilenameResponse(filename=result)


@router.get("/cohorts", tags=["cohorts"], summary="List user's cohorts")
def get_cohorts(
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> CohortListResponse:
    """
    Returns a list of GUIDs corresponding to the user's exported PFBs.

    The appropriate folder is determined from the user's JWT claims (sub field).
    """
    folder_name = get_user_folder_name(claims, settings)

    result, ok = list_files_in_bucket(settings.manifest_bucket_name, folder_name)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Currently unable to connect to S3."
        )

    return CohortListResponse(cohorts=result["cohorts"])


@router.put("/cohorts", tags=["cohorts"], summary="Add PFB GUID to S3 bucket")
@router.post("/cohorts", tags=["cohorts"], summary="Add PFB GUID to S3 bucket")
def put_pfb_guid(
    body: CohortCreateRequest,
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> FilenameResponse:
    """
    Add PFB GUID to S3 bucket.

    Creates a file named with the GUID value in the user's cohorts/ folder.

    Example request body:
    ```json
    {"guid": "5183a350-9d56-4084-8a03-6471cafeb7fe"}
    ```
    """
    result, ok = add_guid_to_bucket(claims, body.guid, settings)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Currently unable to connect to S3."
        )

    return FilenameResponse(filename=result)


@router.get("/metadata", tags=["metadata"], summary="List user's metadata files")
def get_metadata(
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> MetadataListResponse:
    """
    List all exported metadata files associated with user.
    """
    folder_name = get_user_folder_name(claims, settings)

    result, ok = list_files_in_bucket(settings.manifest_bucket_name, folder_name)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Currently unable to connect to S3."
        )

    return MetadataListResponse(external_file_metadata=result["metadata"])


@router.get(
    "/metadata/{file_name}",
    tags=["metadata"],
    summary="Get metadata file contents",
)
def get_metadata_file(
    file_name: str,
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> PlainTextResponse:
    """
    Retrieve a specific exported metadata file by filename.
    """
    file_name = html.escape(file_name)
    if not file_name.endswith("json"):
        raise HTTPException(
            status_code=400,
            detail="Incorrect usage. You can only use this pathway to request files of type JSON.",
        )

    folder_name = get_user_folder_name(claims, settings) + "/exported-metadata"

    content = get_file_contents(settings.manifest_bucket_name, folder_name, file_name)
    return PlainTextResponse(content=content)


@router.put("/metadata", tags=["metadata"], summary="Create metadata export file")
@router.post("/metadata", tags=["metadata"], summary="Create metadata export file")
def put_metadata(
    metadata_body: list[dict[str, Any]],
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> FilenameResponse:
    """
    Create an exported metadata file.
    """
    result, ok = add_metadata_to_bucket(claims, metadata_body, settings)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Currently unable to connect to S3."
        )

    return FilenameResponse(filename=result)
