import pytest
import igsupload.config as config

@pytest.fixture(autouse=True)
def patch_config():
    config.BASE_URL = "http://test"
    config.CERT = "cert"
    config.KEY = "key"
