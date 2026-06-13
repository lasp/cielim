import pytest

import context
from cielim.driver import *
from cielim.launcher import *


@pytest.fixture(scope="session")
def cielim_connection():
    connector = Connector()
    launcher = Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()
    yield connector
    connector.disconnect()
    launcher.terminate()
