import pytest

from manifestservice.api import app as service_app

@pytest.fixture(scope="session")
def app():
    # load configuration
    # service_app.config.from_object('manifestservice.test_settings')
    #app_init(service_app)
    return service_app

