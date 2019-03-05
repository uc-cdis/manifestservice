import flask
import logging
import time

from . import auth
from . import dev_settings
from .errors import AuthZError, JWTError
from .admin_endpoints import blueprint as admin_bp
from .manifests import blueprint as manifests_bp

def create_app():
    app = flask.Flask(__name__)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(manifests_bp, url_prefix="")

    # load configuration
    app.config.from_object("manifest_service.dev_settings")

    # try:
    #     app_init(app)
    # except:
    #     app.logger.exception("Couldn't initialize application, continuing anyway")

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


# def app_init(app):
#     app.logger.info("Initializing app")
#     start = time.time()

#     # do the necessary here!

#     end = int(round(time.time() - start))
#     app.logger.info("Initialization complete in {} sec".format(end))


def run_for_development(**kwargs):
    app.logger.setLevel(logging.INFO)
    
    app.run(**kwargs)
