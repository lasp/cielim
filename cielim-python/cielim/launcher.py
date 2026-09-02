from __future__ import annotations

import atexit
import os
import signal
import socket
import subprocess
import sys
from sys import platform
from pathlib import Path

_default_app_path = os.path.join(str(Path(__file__).resolve().parent.parent.parent.parent), "Binaries")

# Global application path variables
if platform == "darwin":  # If on Mac
    _default_app_path = os.path.join(_default_app_path, "Mac/cielim.app/Contents/MacOS/cielim")
elif platform == "linux":  # If on Linux
    _default_app_path = os.path.join(_default_app_path, "Linux/cielim")
elif platform == "win32":  # If on Windows
    _default_app_path = os.path.join(_default_app_path, "Win64/cielim.exe")
else:
    raise Exception("Unsupported platform, cannot determine Cielim application path.")


class ZmqNetworkProtocol(object):
    """
    Base class to manage zmq network transport, ip, port and zmq address string.

    Attributes:
        port(int): TCP port number or ipc port name.
        transport_type(string): The transport type.
    """

    def __init__(self, port: int = 0, transport_type: str = "tcp"):
        self._transport_type = transport_type
        self.port = port

    def get_bind_address(self) -> str:
        """This method should be overriden by the inheriting class"""
        raise NotImplementedError("as_bind_address must be implemented by subclasses")

    def get_connect_address(self) -> str:
        """This method should be overriden by the inheriting class"""
        raise NotImplementedError("as_connect_address must be implemented by subclasses")


class ZmqTcpProtocol(ZmqNetworkProtocol):
    """
    A class to manage zmq TCP network transport.

    Attributes:
        host_name(string): IP address.
        port(int): TCP port number.
    """

    def __init__(self, host_name: str = "127.0.0.1", port: int = 0):
        super(ZmqTcpProtocol, self).__init__(port, "tcp")
        self.ip_address = host_name
        self.port = port

    def get_connect_address(self):
        return f"{self._transport_type}://{self.ip_address}:{self.port}"

    def get_bind_address(self):
        address = f"{self._transport_type}://{self.ip_address}"
        if self.port:
            address += f":{self.port}"
        return address

    @classmethod
    def from_address_string(cls, address: str) -> "ZmqTcpProtocol":
        try:
            transport, rest = address.split("://", 1)  # Split transport protocol and the rest of the address

            if transport != "tcp":
                raise ValueError(f"Expected 'tcp' transport, got '{transport}'")

            ip_address, port_str = rest.rsplit(":", 1)
            return cls(ip_address, int(port_str))

        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid TCP address string: '{address}'") from e


class Launcher:
    """
    A class to launch Cielim instances.

    Attributes:
        app_path(string): Path to Cielim application executable. If not provided, will attempt to use default path based on operating system.
    """

    def __init__(self, app_path: str = _default_app_path):
        if not os.path.isfile(app_path):
            raise FileNotFoundError(f"App not found: {app_path}")

        self.app_path = app_path
        self._process = None

        self._cleaned_up = False

        # Register terminate function to run on shutdown
        atexit.register(self.terminate)

        # Register handle function to shutdown interpreter on signal
        signal.signal(signal.SIGTERM, Launcher._handle_signal)
        signal.signal(signal.SIGINT, Launcher._handle_signal)

    def __enter__(self):
        return self

    @staticmethod
    def get_next_free_port() -> int:
        """
        Find next freely available port on the system.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("", 0))
            return sock.getsockname()[1]

    def launch(self):
        """
        Launch new Cielim process.
        """
        if self._process and self._process.poll() is None:
            raise RuntimeError("Launcher already has a running process, call terminate() first.")

        port = self.get_next_free_port()  # Port that will be used to connect to specific Cielim instance

        end_point = ZmqTcpProtocol(port=port)  # Just use tcp for now
        connection_address = end_point.get_connect_address()

        try:
            cielim_process = subprocess.Popen(
                [
                    self.app_path,
                    "/Game/Maps/Lvl_Visualization",
                    "-RenderOffscreen",
                    "-directComm",
                    connection_address,
                ],
                cwd=os.path.dirname(self.app_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            self._process = cielim_process
            self._cleaned_up = False

            print(f"Cielim spawned with pid: {cielim_process.pid} on port: {end_point.port}")
            return connection_address
        except FileNotFoundError:
            raise FileNotFoundError(f"Cielim application failed to launch at: {self.app_path}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.terminate()

    def __del__(self):
        self.terminate()

    def terminate(self):
        # Check we haven't already cleaned up
        if self._cleaned_up:
            return

        # Only terminate if the process exists and is still running
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

            self._process = None
            self._cleaned_up = True

    @staticmethod
    def _handle_signal(signum, frame):
        print(f"Received signal {signum}, shutting down...")
        sys.exit(0)  # Shutdown interpreter
