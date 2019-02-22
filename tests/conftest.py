import pytest

from manifest_service.api import app as service_app, app_init


@pytest.fixture(scope="session")
def app():
    # load configuration
    # service_app.config.from_object('manifest_service.test_settings')
    app_init(service_app)
    return service_app
