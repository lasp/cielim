import pytest
from typing import Generator

import cielim


@pytest.fixture(scope="session")
def cielim_connection() -> Generator[cielim.Connector, None, None]:
    connector: cielim.Connector = cielim.Connector()
    launcher: cielim.Launcher = cielim.Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()
    yield connector
    connector.disconnect()
    launcher.terminate()
