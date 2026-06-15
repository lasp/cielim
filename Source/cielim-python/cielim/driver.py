import random

import cv2
import delimited_protobuf
import numpy as np
import zmq

from . import cielimMessage_pb2 as cielimMessage
from . import imageDiagnostics_pb2 as imageDiagnostics


class Connector:
    """
    A class to manage connections to Cielim and send/receive messages.
    """

    def __init__(self):
        self.address = ""
        self.context = None
        self.request_socket = None
        self.identity = ""

    def connect(self, address: str = "tcp://localhost:5556", socket_timeout_ms: int = 10000):
        # Ensure each connector has different ID
        self.identity = "CielimConnector" + "".join(random.choices("0123456789", k=5))

        self.context = zmq.Context()
        self.request_socket = self.context.socket(zmq.REQ)
        self.request_socket.set(zmq.SocketOption.CONNECT_TIMEOUT, 10)
        # self.request_socket.set(zmq.SocketOption.RCVTIMEO, socket_timeout_ms)
        self.request_socket.setsockopt_string(zmq.IDENTITY, self.identity)

        self.address = address
        self.request_socket.connect(address)

        # Send a ping to ensure connection is established before sending any data
        print(f"Sending ping to Cielim at {address}...")
        print(self.send_ping())

    def _safe_recv_multipart(self):
        """
        Similar to normal blocking recv_multipart but if message received is a PING (indicating a heartbeat request), we respond with PONG immediately and then continue waiting until data is received.
        """
        if self.request_socket is None:
            raise Exception("Socket not connected, cannot receive messages.")

        while True:
            try:
                multipart_message = self.request_socket.recv_multipart()
            except zmq.error.Again:
                raise Exception("Socket timed out waiting for message.")

            if multipart_message[0] == b"PING":
                self.request_socket.send_string("PONG")
                continue

            return multipart_message

    def send_ping(self):
        if self.request_socket is None:
            raise Exception("Socket not connected, cannot send ping.")

        _ = self.request_socket.send_string("PING")

        return self._safe_recv_multipart()[0].decode("utf-8")

    def send_init_request(self):
        if self.request_socket is None:
            raise Exception("Socket not connected, cannot send init request.")

        _ = self.request_socket.send_string("INIT_SCENE")

        return self._safe_recv_multipart()[0].decode("utf-8")

    def send_frame(self, sim_frame: cielimMessage.CielimMessage):
        if self.request_socket is None:
            raise Exception("Socket not connected, cannot send frame.")

        _ = self.request_socket.send_multipart([b"SIM_UPDATE", sim_frame.SerializePartialToString()])

        return self._safe_recv_multipart()[0].decode("utf-8")

    def request_image_for_camera_id(
        self,
        camera_id: int,
        should_return_image: bool = True,
        should_return_diagnostics: bool = True,
        format_raw: bool = False,
    ):
        if self.request_socket is None:
            raise Exception("Socket not connected, cannot request image.")

        _ = self.request_socket.send_multipart(
            [
                b"REQUEST_IMAGE",
                str.encode(str(camera_id)),
                str.encode(str(int(should_return_image))),
                str.encode(str(int(should_return_diagnostics))),
            ]
        )

        [image_data, image_data_size, diagnostics_serialized] = self._safe_recv_multipart()

        image = None
        if should_return_image:
            buf = np.asarray(bytearray(image_data), dtype="uint8")  # Convert bytes to numpy array

            if format_raw:
                image = buf
            else:
                image = cv2.imdecode(buf, cv2.IMREAD_COLOR)  # Format PNG image data for viewing with OpenCV (BGRA)

        diagnostics = imageDiagnostics.DiagnosticData()
        diagnostics.ParseFromString(diagnostics_serialized)

        cob = (diagnostics.cob_x, diagnostics.cob_y)

        coverage = diagnostics.coverage

        return [image, cob, coverage]

    def disconnect(self):
        if self.request_socket is not None:
            self.request_socket.disconnect(self.address)

        if self.context is not None:
            self.context.destroy()


class CielimMessageFileHandler:
    """
    A class to handle CielimMessage bin files and reading.
    """

    def __init__(self, file_name: str):
        self.file_name = file_name
        self.file_handle = open(file_name, "rb")

    def jump_to_simulation_frame_at_time(self, sim_time: float):
        """
        Jumps to first message in file at or after the requested sim time and returns that message.
        """
        while True:
            message = delimited_protobuf.read(self.file_handle, cielimMessage.CielimMessage)

            if message is None:
                raise Exception("Reached end of file without finding a message with sim time >= requested time.")

            if message.currentTime.simTimeElapsed >= sim_time:
                return message

    def get_simulation_frame_at_time(self, sim_time: float):
        """
        Get first message in file at or after the requested sim time and reset file reader to start of file.
        """
        message = self.jump_to_simulation_frame_at_time(sim_time)
        self.file_handle.seek(0)  # Reset file reader to beginning of file after finding requested message
        return message

    def get_next_simulation_frame(self):
        try:
            return delimited_protobuf.read(self.file_handle, cielimMessage.CielimMessage)
        except Exception as e:
            print(f"Protobuf failed to decode: {e}")
            return None
