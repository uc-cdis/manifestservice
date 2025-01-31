import json
import logging
import os

import flask

from .manifests import blueprint as manifests_bp

TRUSTED_CONFIG_PATH_PREFIXES = [os.getcwd(), "/var/gen3"]


def validate_config_path(config_path):
    """Get paths with trusted prefixes"""
    for trusted_path in TRUSTED_CONFIG_PATH_PREFIXES:
        if (
            os.path.commonpath((os.path.realpath(config_path), trusted_path))
            == trusted_path
        ):
            return
    raise ValueError(f"Illegal config file path provided as {config_path}")


def create_app():
    """Create app"""
    app = flask.Flask(__name__)
    app.register_blueprint(manifests_bp, url_prefix="")

    # load configuration
    config_path = os.environ.get("MANIFEST_SERVICE_CONFIG_PATH", "config.json")

    try:
        validate_config_path(config_path)
        with open(config_path) as config_file:
            config_str = config_file.read()
            config_dict = json.loads(config_str)
    except Exception as err:
        print(err)
        raise ValueError(f"Unable to parse the provided config file at {config_path}")

    for key in config_dict:
        app.config[key] = config_dict[key]

    app.config["USER_API"] = os.environ.get("FENCE_URL") or "http://fence-service/"
    # use the USER_API URL instead of the public issuer URL to accquire JWT keys
    app.config["FORCE_ISSUER"] = True

    # If prefix is set, user folders will be stored in a directory named PREFIX
    if "prefix" in config_dict and config_dict["prefix"] != "":
        app.config["PREFIX"] = config_dict["prefix"]
    app.config["OIDC_ISSUER"] = f"https://{config_dict['hostname']}/user"
    app.config["MANIFEST_BUCKET_NAME"] = config_dict["manifest_bucket_name"]

    required_config_variables = [
        "OIDC_ISSUER",
        "MANIFEST_BUCKET_NAME",
    ]
    if not set(required_config_variables).issubset(set(app.config.keys())):
        missing_variables = set(required_config_variables).difference(
            set(app.config.keys())
        )
        raise ValueError(
            f"Not all required config variables were provided in {config_path}."
            + f" Missing: {str(missing_variables)}"
        )

    return app


app = create_app()


@app.route("/_status", methods=["GET"])
def health_check():
    """
    Health check endpoint
    ---
    tags:
      - system
    responses:
        200:
            description: Healthy
        default:
            description: Unhealthy
    """
    return "Healthy", 200


def run_for_development(**kwargs):
    """Run the service locally"""
    app.logger.setLevel(logging.INFO)

    app.run(**kwargs)
