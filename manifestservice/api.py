import flask
import logging
import time

from .manifests import blueprint as manifests_bp
import os
import json


def create_app():
    app = flask.Flask(__name__)
    app.register_blueprint(manifests_bp, url_prefix="")

    # load configuration
    config_path = os.environ.get("MANIFEST_SERVICE_CONFIG_PATH", "config.json")

    try:
        f = open(config_path)
        config_str = f.read()
        config_dict = json.loads(config_str)
    except Exception as e:
        print(e)
        raise ValueError(
            "Unable to parse the provided config file at {}".format(config_path)
        )

    for key in config_dict:
        app.config[key] = config_dict[key]

    app.config["USER_API"] = os.environ.get("FENCE_URL") or "http://fence-service/"
    # use the USER_API URL instead of the public issuer URL to accquire JWT keys
    app.config["FORCE_ISSUER"] = True

    # If prefix is set, user folders will be stored in a directory named PREFIX
    if "prefix" in config_dict and config_dict["prefix"] != "":
        app.config["PREFIX"] = config_dict["prefix"]
    app.config["OIDC_ISSUER"] = "https://%s/user" % config_dict["hostname"]
    app.config["MANIFEST_BUCKET_NAME"] = config_dict["manifest_bucket_name"]

    required_config_variables = [
        "OIDC_ISSUER",
        "MANIFEST_BUCKET_NAME",
    ]
    if not set(required_config_variables).issubset(set(app.config.keys())):
        raise ValueError(
            "Not all required config variables were provided in {}. Missing: {}".format(
                config_path,
                str(set(required_config_variables).difference(set(app.config.keys()))),
            )
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
    app.logger.setLevel(logging.INFO)

    app.run(**kwargs)
