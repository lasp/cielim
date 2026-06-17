import pytest

import cielim


@pytest.fixture(scope="session")
def cielim_connection():
    connector = cielim.Connector()
    launcher = cielim.Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()
    yield connector
    connector.disconnect()
    launcher.terminate()
