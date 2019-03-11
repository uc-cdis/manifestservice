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

    app.config["OIDC_ISSUER"] = "https://%s/user" % config_dict["hostname"]
    app.config["MANIFEST_BUCKET_NAME"] = config_dict["manifest_bucket_name"]

    app.config["AWS_ACCESS_KEY_ID"] = config_dict["aws_access_key_id"].strip()
    app.config["AWS_SECRET_ACCESS_KEY"] = config_dict["aws_secret_access_key"].strip()

    os.environ["AWS_ACCESS_KEY_ID"] = config_dict["aws_access_key_id"].strip()
    os.environ["AWS_SECRET_ACCESS_KEY"] = config_dict["aws_secret_access_key"].strip()

    required_config_variables = [
        "AWS_SECRET_ACCESS_KEY",
        "AWS_ACCESS_KEY_ID",
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
