"""
S3 service functions for Manifest Service.

This module contains all S3 operations extracted from the Flask blueprint.
Functions are kept as module-level functions (not a class) to maintain
simplicity and match the original Flask implementation pattern.

NOTE - Flask -> FastAPI migration notes:
- Removed flask.current_app.config references, now uses Settings passed as parameter
- Removed current_token global, now uses claims dict passed as parameter
- Uses get_user_folder_name() from dependencies instead of _get_folder_name_from_token()
"""

import json
import ntpath
from datetime import datetime
from typing import Any

import boto3
from cdislogging import get_logger

from ..config import Settings
from ..dependencies import get_user_folder_name

logger = get_logger("manifestservice_logger", log_level="info")


def list_files_in_bucket(bucket_name: str, folder: str) -> tuple[dict[str, list], bool]:
    """
    Lists the files in an s3 bucket for a given folder.

    Args:
        bucket_name: Name of the S3 bucket
        folder: User's folder prefix (e.g., "user-123" or "prefix/user-123")

    Returns:
        Tuple of (result_dict, success_bool).
        result_dict is of the form:
        {
            "manifests:" [
                # For files in the root of the user folder
                { "filename": <filename>, "last_modified": <timestamp> }, ...
            ],
            "cohorts": [
                # For files in the cohorts/ folder
                { "filename": <filename>, "last_modified": <timestamp> }, ...
            ],
            "metadata": [
                # For files in the exported-metadata/ folder
                { "filename": <filename>, "last_modified": <timestamp> }, ...
            ],
        }
    """
    session = boto3.Session(region_name="us-east-1")
    s3 = session.resource("s3")

    manifests = []
    guids = []
    metadata = []
    bucket = s3.Bucket(bucket_name)

    try:
        bucket_objects = bucket.objects.filter(Prefix=folder + "/")
        for object_summary in bucket_objects:
            file_marker = {
                "last_modified": object_summary.last_modified.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "last_modified_timestamp": datetime.timestamp(
                    object_summary.last_modified
                ),
            }
            if "cohorts/" in object_summary.key:
                file_marker["filename"] = object_summary.key.split("cohorts/")[1]
                guids.append(file_marker)
            elif "metadata/" in object_summary.key:
                file_marker["filename"] = object_summary.key.split("metadata/")[1]
                metadata.append(file_marker)
            else:
                file_marker["filename"] = ntpath.basename(object_summary.key)
                manifests.append(file_marker)
    except Exception as e:
        logger.error(
            f'Failed to list files in bucket "{bucket_name}" folder "{folder}": {e}'
        )
        return str(e), False

    manifests_sorted = sorted(manifests, key=lambda i: i["last_modified_timestamp"])
    guids_sorted = sorted(guids, key=lambda i: i["last_modified_timestamp"])
    metadata_sorted = sorted(metadata, key=lambda i: i["last_modified_timestamp"])

    rv = {
        "manifests": manifests_sorted,
        "cohorts": guids_sorted,
        "metadata": metadata_sorted,
    }
    return rv, True


def get_file_contents(bucket_name: str, folder: str, filename: str) -> str:
    """
    Returns the body of a requested file as a string.

    Args:
        bucket_name: Name of the S3 bucket
        folder: User's folder
        filename: Name of the file to retrieve

    Returns:
        File contents as a string
    """
    client = boto3.client(
        "s3",
    )
    obj = client.get_object(Bucket=bucket_name, Key=folder + "/" + filename)
    as_bytes = obj["Body"].read()
    as_string = as_bytes.decode("utf-8")
    return as_string.replace("'", '"')


def add_manifest_to_bucket(
    claims: dict,
    manifest_json: list[dict],
    settings: Settings,
) -> tuple[str | None, bool]:
    """
    Puts the manifest_json into a file and uploads it to S3.

    Args:
        claims: JWT claims dict containing user info
        manifest_json: List of manifest items to store
        settings: Application settings

    Returns:
        Tuple of (filename, success_bool). filename is the generated filename on success.
    """
    session = boto3.Session(region_name="us-east-1")
    s3 = session.resource("s3")

    folder_name = get_user_folder_name(claims, settings)
    bucket_name = settings.manifest_bucket_name

    result, ok = list_files_in_bucket(bucket_name, folder_name)
    if not ok:
        return result, False

    filename = _generate_unique_filename(result["manifests"])
    filepath_in_bucket = folder_name + "/" + filename

    try:
        obj = s3.Object(bucket_name, filepath_in_bucket)
        obj.put(Body=bytes(json.dumps(manifest_json).encode("UTF-8")))
    except Exception as e:
        logger.error(f"Failed to add manifest to bucket: {e}")
        return str(e), False

    return filename, True


def add_guid_to_bucket(
    claims: dict,
    guid: str,
    settings: Settings,
) -> tuple[str | None, bool]:
    """
    Creates a new file in the user's cohorts/ folder with the GUID as filename.

    Args:
        claims: JWT claims dict containing user info
        guid: The PFB GUID to store
        settings: Application settings

    Returns:
        Tuple of (guid, success_bool)
    """
    session = boto3.Session(region_name="us-east-1")
    s3 = session.resource("s3")

    folder_name = get_user_folder_name(claims, settings)
    bucket_name = settings.manifest_bucket_name

    existing_files, ok = list_files_in_bucket(bucket_name, folder_name)
    if not ok:
        return None, False

    # NOTE: in the flask version, this check always failed and overwrote every time
    # bug didn't break anything, just unnecesary overwrite
    if guid in [f["filename"] for f in existing_files["cohorts"]]:
        return guid, True

    filepath_in_bucket = folder_name + "/cohorts/" + guid
    try:
        obj = s3.Object(bucket_name, filepath_in_bucket)
        obj.put(Body=str.encode(""))
    except Exception as e:
        return str(e), False

    return guid, True


def add_metadata_to_bucket(
    claims: dict,
    metadata_body: list[dict[str, Any]],
    settings: Settings,
) -> tuple[str | None, bool]:
    """
    Creates a new metadata file in the user's exported-metadata/ folder.

    Args:
        claims: JWT claims dict containing user info
        metadata_body: Metadata to store
        settings: Application settings

    Returns:
        Tuple of (filename, success_bool)
    """
    session = boto3.Session(region_name="us-east-1")
    s3 = session.resource("s3")

    folder_name = get_user_folder_name(claims, settings)
    bucket_name = settings.manifest_bucket_name

    result, ok = list_files_in_bucket(bucket_name, folder_name)
    if not ok:
        return None, False

    filename = _generate_unique_filename(result["metadata"], file_type="metadata")
    filepath_in_bucket = folder_name + "/exported-metadata/" + filename

    try:
        obj = s3.Object(bucket_name, filepath_in_bucket)
        obj.put(Body=bytes(json.dumps(metadata_body).encode("UTF-8")))
    except Exception as e:
        return str(e), False

    return filename, True


def _generate_unique_filename(
    existing_files: list[dict], file_type: str = "manifest"
) -> str:
    """
    Returns a filename of the form {type}-<timestamp>-<optional-increment>.json
    that is unique among the files in the user's folder.

    Args:
        existing_files: List of existing file dicts with "filename" key
        file_type: e.g. "manifest" or "metadata"

    Returns:
        Unique filename string
    """
    timestamp = datetime.now().isoformat()
    existing_filenames = [f["filename"] for f in existing_files]
    return _generate_unique_filename_with_timestamp_and_increment(
        timestamp, existing_filenames, file_type
    )


def _generate_unique_filename_with_timestamp_and_increment(
    timestamp: str, existing_filenames: list[str], file_type: str = "manifest"
) -> str:
    """
    Helper function that generates a unique filename with timestamp.

    Adds an increment suffix if there's a collision (unlikely but possible).

    Args:
        timestamp: ISO format timestamp string
        existing_filenames: List of existing filename strings
        file_type: e.g. "manifest" or "metadata"

    Returns:
        Unique filename string
    """
    filename_prefix = "manifest-" if file_type == "manifest" else "metadata-"
    filename_without_extension = filename_prefix + timestamp.replace(":", "-")
    extension = ".json"

    filename = filename_without_extension + extension
    i = 1
    while filename in existing_filenames:
        filename = filename_without_extension + "-" + str(i) + extension
        i += 1

    return filename
