"""
Manifest, Cohort, and Metadata routes for Manifest Service.

NOTE - Flask -> FastAPI migration notes:
- @blueprint.route("/", methods=["GET"]) -> @router.get("/")
- flask.jsonify(dict), status_code -> return dict (FastAPI auto-serializes)
- Request body flask.request.json -> request body parameter with type hint (TODO - could use Pydantic)
- Manual _authenticate_user() call -> CurrentUserClaims dependency injected
- flask.current_app.config -> settings parameter injected by FastAPI
- BREAKING CHANGES - HTTP exceptions replace (jsonify(error), status_code)
    - 500 will now return "detail" not "error"
    - 400 will be 422 for some input validation errors
    - 403 now covered by authutils "detail": Bad bearer token
"""

import html
import re
from typing import Any

from cdislogging import get_logger
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from ..dependencies import CurrentUserClaims, SettingsDep, get_user_folder_name
from ..services.s3 import (
    list_files_in_bucket,
    get_file_contents,
    add_manifest_to_bucket,
    add_guid_to_bucket,
    add_metadata_to_bucket,
)

logger = get_logger("manifestservice_logger", log_level="info")

router = APIRouter(tags=["manifests"])


@router.get("/")
def get_manifests(
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> dict:
    """
    Returns a list of filenames corresponding to the user's manifests.

    We find the appropriate folder ("prefix") in the bucket by asking Fence for
    info about the user's access token.
    """
    folder_name = get_user_folder_name(claims, settings)

    result, ok = list_files_in_bucket(settings.manifest_bucket_name, folder_name)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Currently unable to connect to S3."
        )

    return {"manifests": result["manifests"]}


@router.get("/file/{file_name}")
def get_manifest_file(
    file_name: str,
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> PlainTextResponse:
    """
    Returns the requested manifest file from the user's folder.

    The argument is the filename of the manifest you want to download,
    of the form "manifest-timestamp.json". The user folder prefix is
    encapsulated from the caller -- just provide the basepath.
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


@router.put("/")
@router.post("/")
def put_manifest(
    manifest_json: list[dict[str, Any]],
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> dict:
    """
    Add manifest to S3 bucket.

    The manifest format must be a list of objects, where each object contains
    at least an "object_id" key.
    """
    required_keys = ["object_id"]
    if not _is_valid_manifest(manifest_json, required_keys):
        raise HTTPException(
            status_code=400,
            detail=(
                "Manifest format is invalid. Please POST a list of key-value pairs, "
                f"like [{{'k': v}}, ...]. Required keys are: {' '.join(required_keys)}"
            ),
        )

    result, ok = add_manifest_to_bucket(claims, manifest_json, settings)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Currently unable to connect to S3."
        )

    return {"filename": result}


@router.get("/cohorts")
def get_cohorts(
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> dict:
    """
    Returns a list of filenames (GUIDs) corresponding to the user's exported PFBs.

    We find the appropriate folder ("prefix") in the bucket by asking Fence for
    info about the user's access token.
    """
    folder_name = get_user_folder_name(claims, settings)

    result, ok = list_files_in_bucket(settings.manifest_bucket_name, folder_name)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Currently unable to connect to S3."
        )

    return {"cohorts": result["cohorts"]}


@router.put("/cohorts")
@router.post("/cohorts")
def put_pfb_guid(
    body: dict,
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> dict:
    """
    Add PFB GUID to S3 bucket.

    Creates a new file named with the value of the GUID for the PFB
    in the user's cohorts/ folder.

    Request body: {"guid": "5183a350-9d56-4084-8a03-6471cafeb7fe"}
    """
    guid = body.get("guid")
    if not _is_valid_guid(guid):
        raise HTTPException(
            status_code=400,
            detail=f"The provided GUID: {guid} is invalid.",
        )

    result, ok = add_guid_to_bucket(claims, guid, settings)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Currently unable to connect to S3."
        )

    return {"filename": result}


@router.get("/metadata")
def get_metadata(
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> dict:
    """
    List all exported metadata objects associated with user.
    """
    folder_name = get_user_folder_name(claims, settings)

    result, ok = list_files_in_bucket(settings.manifest_bucket_name, folder_name)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Currently unable to connect to S3."
        )

    return {"external_file_metadata": result["metadata"]}


@router.get("/metadata/{file_name}")
def get_metadata_file(
    file_name: str,
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> PlainTextResponse:
    """
    Retrieve a specific exported metadata file.
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


@router.put("/metadata")
@router.post("/metadata")
def put_metadata(
    metadata_body: list[dict[str, Any]],
    claims: CurrentUserClaims,
    settings: SettingsDep,
) -> dict:
    """
    Create an exported metadata object.
    """
    result, ok = add_metadata_to_bucket(claims, metadata_body, settings)
    if not ok:
        raise HTTPException(
            status_code=500, detail="Currently unable to connect to S3."
        )

    return {"filename": result}


def _is_valid_manifest(manifest_json: list[dict], required_keys: list[str]) -> bool:
    """
    Returns True if the manifest_json is a list of the form [{'k': v}, ...],
    where each member dictionary contains all required keys.
    """
    for record in manifest_json:
        if not set(required_keys).issubset(record.keys()):
            return False
    return True


def _is_valid_guid(guid: str | None) -> bool:
    """
    Check if input value is a valid GUID.

    Valid GUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    (with optional prefix before the UUID portion)
    """
    if guid is None:
        return False
    regex = re.compile(
        r"^.*[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$",
        re.I,
    )
    return bool(regex.match(str(guid)))
