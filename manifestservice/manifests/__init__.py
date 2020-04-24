import flask
import boto3
from flask import current_app as app
import requests
import ntpath
from datetime import date, datetime
from authutils.token.validate import current_token, validate_request, set_current_token
from authutils import user as authutils_user
from cdislogging import get_logger

logger = get_logger("manifestservice_logger", log_level="info")

blueprint = flask.Blueprint("manifests", __name__)


@blueprint.route("/", methods=["GET"])
def get_manifests():
    """
    Returns a list of filenames corresponding to the user's manifests.
    We find the appropriate folder ("prefix") in the bucket by asking Fence for 
    info about the user's access token.
    ---
    responses:
        200:
            description: Success
        403:
            description: Unauthorized
    """

    err, code = _authenticate_user()
    if err is not None:
        return err, code

    folder_name = _get_folder_name_from_token(current_token)

    result, ok = _list_files_in_bucket(
        flask.current_app.config.get("MANIFEST_BUCKET_NAME"), folder_name
    )
    if not ok:
        json_to_return = {"error": "Currently unable to connect to s3."}
        return flask.jsonify(json_to_return), 500

    json_to_return = {"manifests": result}

    return flask.jsonify(json_to_return), 200


@blueprint.route("/file/<file_name>", methods=["GET"])
def get_manifest_file(file_name):
    """
    Returns the requested manifest file from the user's folder.
    The argument is the filename of the manifest you want to downloaded,
    of the form "manifest-timestamp".json. The user folder prefix is encapsulated from
    the caller -- just provide the basepath.
    ---    
    responses:
        200:
            description: Success
        403:
            description: Unauthorized
        400:
            description: Bad request format
    """

    err, code = _authenticate_user()
    if err is not None:
        return err, code

    if not file_name.endswith("json"):
        json_to_return = {
            "error": "Incorrect usage. You can only use this pathway to request files of type JSON."
        }
        return flask.jsonify(json_to_return), 400

    folder_name = _get_folder_name_from_token(current_token)

    return _get_file_contents(
        flask.current_app.config.get("MANIFEST_BUCKET_NAME"), folder_name, file_name
    )


@blueprint.route("/", methods=["PUT", "POST"])
def put_manifest():
    """
    Add manifest to s3 bucket. See the README for the format of this file.
    ---
    responses:
        200:
            description: Success
        403:
            description: Unauthorized
        400:
            description: Bad manifest format
    """

    err, code = _authenticate_user()
    if err is not None:
        return err, code

    if not flask.request.json:
        return flask.jsonify({"error": "Please provide valid JSON."}), 400

    manifest_json = flask.request.json
    required_keys = ["object_id"]
    is_valid = is_valid_manifest(manifest_json, required_keys)
    if not is_valid:
        return (
            flask.jsonify(
                {
                    "error": "Manifest format is invalid. Please POST a list of key-value pairs, like [{'k' : v}, ...] Required keys are: "
                    + " ".join(required_keys)
                }
            ),
            400,
        )

    result, ok = _add_manifest_to_bucket(current_token, manifest_json)
    if not ok:
        json_to_return = {"error": "Currently unable to connect to s3."}
        return flask.jsonify(json_to_return), 500

    ret = {"filename": result}

    return flask.jsonify(ret), 200


def _add_manifest_to_bucket(current_token, manifest_json):
    """
    Puts the manifest_json string into a file and uploads it to s3. 
    Generates and returns the name of the new file.
    """
    session = boto3.Session(
        region_name="us-east-1",
        aws_access_key_id=app.config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=app.config["AWS_SECRET_ACCESS_KEY"],
    )
    s3 = session.resource("s3")

    folder_name = _get_folder_name_from_token(current_token)

    result, ok = _list_files_in_bucket(
        flask.current_app.config.get("MANIFEST_BUCKET_NAME"), folder_name
    )
    if not ok:
        return result, False

    filename = _generate_unique_manifest_filename(
        folder_name, flask.current_app.config.get("MANIFEST_BUCKET_NAME"), result
    )
    manifest_as_bytes = str.encode(str(flask.request.json))
    filepath_in_bucket = folder_name + "/" + filename

    try:
        obj = s3.Object(
            flask.current_app.config.get("MANIFEST_BUCKET_NAME"), filepath_in_bucket
        )
        response = obj.put(Body=manifest_as_bytes)
    except Exception as e:
        logger.error("Failed to add manifest to bucket: {}".format(e))
        return str(e), False

    return filename, True


def _get_folder_name_from_token(user_info):
    """
    Returns the name of the user's manifest folder (their "prefix").
    It takes a "user_info" dict, which is the response that Fence returns at /user/user
    The convention we'll use here is that a user's folder name will be "user-x" where x is 
    their ID (integer).

    According to the revproxy's helpers.js, it looks like the user_id is stored in a variable called "sub". Hm. 
    """
    result = "user-" + str(user_info["sub"])
    if "PREFIX" in app.config:
        result = app.config["PREFIX"] + "/user-" + str(user_info["sub"])
    return result


def _does_the_user_have_read_access_on_at_least_one_project(project_access_dict):
    """
    Returns True if the user has both read and read-storage access on at least one project, 
    False otherwise.
    """
    privileges = list(project_access_dict.values())

    for auth_set in privileges:
        if "read" in auth_set and "read-storage" in auth_set:
            return True

    return False


def is_valid_manifest(manifest_json, required_keys):
    """
    Returns True if the manifest.json is a list of the form [{'k' : v}, ...], 
    where each member dictionary contains an object_id key.
    Otherwise, returns False
    """
    for record in manifest_json:
        record_keys = record.keys()
        if not set(required_keys).issubset(record_keys):
            return False

    return True


def _generate_unique_manifest_filename(
    folder_name, manifest_bucket_name, users_existing_manifest_files
):
    """
    Returns a filename of the form manifest-<timestamp>-<optional-increment>.json that is
    unique among the files in the user's manifest folder.
    """
    timestamp = datetime.now().isoformat()
    existing_filenames = map(lambda x: x["filename"], users_existing_manifest_files)
    filename = _generate_unique_filename_with_timestamp_and_increment(
        timestamp, existing_filenames
    )
    return filename


def _generate_unique_filename_with_timestamp_and_increment(
    timestamp, users_existing_manifest_files
):
    """
    A helper function for _generate_unique_manifest_filename(), which facilitates unit testing.
    Adds an increment to the filename if there happens to be another timestamped file with the same name
    (unlikely, but good to check). 
    """
    filename_without_extension = "manifest-" + timestamp.replace(":", "-")
    extension = ".json"

    filename = filename_without_extension + extension
    i = 1
    while filename in users_existing_manifest_files:
        filename = filename_without_extension + extension
        if filename in users_existing_manifest_files:
            filename = filename_without_extension + "-" + str(i) + extension
        i += 1

    return filename


def _list_files_in_bucket(bucket_name, folder):
    """
    Lists the files in an s3 bucket. Returns a list of filenames.
    """
    session = boto3.Session(
        region_name="us-east-1",
        aws_access_key_id=app.config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=app.config["AWS_SECRET_ACCESS_KEY"],
    )
    s3 = session.resource("s3")

    rv = []
    bucket = s3.Bucket(bucket_name)

    try:
        bucket_objects = bucket.objects.filter(Prefix=folder + "/")
        for object_summary in bucket_objects:
            manifest_summary = {
                "filename": ntpath.basename(object_summary.key),
                "last_modified": object_summary.last_modified.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
            rv.append(manifest_summary)
    except Exception as e:
        logger.error(
            'Failed to list files in bucket "{}" folder "{}": {}'.format(
                bucket_name, folder, e
            )
        )
        return str(e), False

    return rv, True


def _get_file_contents(bucket_name, folder, filename):
    """
    Returns the body of a requested file as a string. 
    """
    client = boto3.client(
        "s3",
        aws_access_key_id=app.config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=app.config["AWS_SECRET_ACCESS_KEY"],
    )
    obj = client.get_object(Bucket=bucket_name, Key=folder + "/" + filename)
    as_bytes = obj["Body"].read()
    as_string = as_bytes.decode("utf-8")
    return as_string.replace("'", '"')


def _authenticate_user():
    """
    If the user's access token is invalid, they get a 403.
    If the user lacks read access on at least one project, they get a 403.
    """
    try:
        set_current_token(validate_request(aud={"user"}))
    except Exception as e:
        logger.error(e)
        json_to_return = {"error": "Please log in."}
        return flask.jsonify(json_to_return), 403

    try:
        auth_successful = _does_the_user_have_read_access_on_at_least_one_project(
            authutils_user.current_user.projects
        )
    except Exception as e:
        logger.error(e)
        json_to_return = {
            "error": "You must have read access on at least one project in order to use this feature."
        }
        return flask.jsonify(json_to_return), 403

    return None, None
