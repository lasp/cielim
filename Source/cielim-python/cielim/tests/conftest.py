import context
from driver import *
from launcher import *
import pytest

@pytest.fixture(scope="session")
def cielim_connection():
    connector = Connector()
    launcher = Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()
    yield connector
    connector.disconnect()
    launcher.terminate()
