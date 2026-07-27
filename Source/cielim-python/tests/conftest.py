import os

import pytest
from typing import Generator

import cielim


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "showcase: opt-in test that renders and saves a page-ready feature-demo image "
        "(runs only when the showcase_dir env var is set).",
    )


def pytest_collection_modifyitems(config, items):
    """Skip @pytest.mark.showcase tests unless the showcase_dir env var points somewhere to save to."""
    if os.environ.get("showcase_dir"):
        return
    skip = pytest.mark.skip(reason="showcase image test; set showcase_dir env var to run")
    for item in items:
        if "showcase" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def cielim_connection() -> Generator[cielim.Connector, None, None]:
    connector: cielim.Connector = cielim.Connector()
    launcher: cielim.Launcher = cielim.Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()
    yield connector
    connector.disconnect()
    launcher.terminate()
