from __future__ import annotations

import os
import random
import socket
import subprocess
from sys import platform

# TODO : Modify the path to the viz here
if platform == "darwin":
    appPath = os.path.dirname(__file__) + "/../../../Binaries/Mac/cielim.app/Contents/MacOS/cielim"  # If on Mac
elif platform == "win32":
    appPath = os.path.dirname(__file__) + "/../../../Binaries/Win64/cielim"  # If on Mac


class ZmqNetworkProtocol(object):
    """
    Base class to manage zmq network transport, ip, port and zmq address string

    Parameters
    ----------
    port : int
        tcp port number or ipc port name
    transport_type : string
        the transport type
    """

    def __init__(self, port=0, transport_type="tcp"):
        self._transport_type = transport_type
        self.port = port

    def as_bind_address(self):
        """This method should be overriden by the inheriting class"""
        pass

    def as_connect_address(self):
        """This method should be overriden by the inheriting class"""
        pass


class ZmqTcpProtocol(ZmqNetworkProtocol):
    """
    A class to manage zmq TCP network transport

    Parameters
    ----------
    host_name : string
        ip address
    port : int
        tcp port number
    """

    def __init__(self, host_name="127.0.0.1", port=0):
        super(ZmqTcpProtocol, self).__init__(port, "tcp")
        self.ip_address = host_name
        self.port = port

    def as_connect_address(self):
        return "{0}://{1}:{2}".format(self._transport_type, self.ip_address, str(self.port))

    def as_bind_address(self):
        address = "{0}://{1}".format(self._transport_type, self.ip_address)
        if self.port:
            address += ":" + str(self.port)
        return address

    @classmethod
    def from_address_string(cls: ZmqTcpProtocol, address: str) -> ZmqTcpProtocol:
        parts = address.split(":")
        ip_address = parts[1].lstrip("/")
        port = int(parts[2])
        return cls(ip_address, port)


def get_next_free_port():
    max_port = 65535
    min_port = 1024
    # Use pid as port number but if it falls outside the bounds of allowable port numbers then choose one at random.
    port = os.getpid()
    if port < min_port or port > max_port:
        port = random.randint(min_port, max_port)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    attempts = 0
    while attempts <= max_port - min_port:
        try:
            sock.bind(("", port))
            return port
        except OSError:
            port = random.randint(min_port, max_port)
            attempts += 1
    raise IOError("no free ports")


def run(port=5556):
    end_point = ZmqTcpProtocol(port=port)
    try:
        cielim_process = subprocess.Popen([appPath, "/Game/Maps/Lvl_Visualization", "-RenderOffscreen", "-directComm",
                                           end_point.as_connect_address(), ], stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL, )
        print("Cielim spawned with pid: {0} on port: {1}".format(str(cielim_process.pid), end_point.port))
        return cielim_process
    except FileNotFoundError:
        print("Cielim application not found")
        return None


def terminate(cielim_process):
    if cielim_process is None:
        print("cielim application is not launched")
    else:
        cielim_process.kill()
