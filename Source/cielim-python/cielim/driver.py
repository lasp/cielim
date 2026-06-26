import struct

import cv2
import delimited_protobuf
import numpy as np
import zmq
import random

import cielimMessage_pb2 as cielimMessage
import imageDiagnostics_pb2 as imageDiagnostics


class Connector:
    def __init__(self):
        self.address = ""
        self.context = None
        self.request_socket = None
        self.identity = ""

    def connect(self, address: str = "tcp://localhost:5556"):
        # Ensure each connector has different ID
        self.identity = "CielimConnector" + "".join(random.choices("0123456789", k=5))

        self.context = zmq.Context()
        self.request_socket = self.context.socket(zmq.REQ)
        self.request_socket.set(zmq.SocketOption.CONNECT_TIMEOUT, 10)
        self.request_socket.setsockopt_string(zmq.IDENTITY, self.identity)

        self.address = address
        self.request_socket.connect(address)
        print(self._send_ping())
        print(self._send_ping())

    """
    Similar to normal blocking recv_multipart but if message received is a
    PING (indicating a heartbeat request), we respond with PONG immediately
    and then continue waiting until data is received.
    """

    def safe_recv_multipart(self):
        while True:
            multipart_message = self.request_socket.recv_multipart()

            if multipart_message[0] == b"PING":
                self.request_socket.send_string("PONG")
                continue

            return multipart_message

    def _send_ping(self):
        _ = self.request_socket.send_string("PING")
        return self.safe_recv_multipart()[0].decode("utf-8")

    def send_init_request(self):
        _ = self.request_socket.send_string("INIT_SCENE")
        return self.safe_recv_multipart()[0].decode("utf-8")

    def send_frame(self, sim_frame: cielimMessage.CielimMessage):
        _ = self.request_socket.send_multipart([b"SIM_UPDATE", sim_frame.SerializePartialToString()])
        return self.safe_recv_multipart()[0].decode("utf-8")

    def request_image_for_camera_id(
        self,
        camera_id: int,
        should_return_image: bool = True,
        should_return_diagnostics: bool = True,
        format_raw: bool = False,
    ):
        _ = self.request_socket.send_multipart(
            [
                b"REQUEST_IMAGE",
                str.encode(str(camera_id)),
                str.encode(str(int(should_return_image))),
                str.encode(str(int(should_return_diagnostics))),
            ]
        )

        [image_data, image_data_size, diagnostics_serialized] = self.safe_recv_multipart()

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
        self.request_socket.disconnect(self.address)
        self.context.destroy()


def create_simulation_frame():
    return protobuf_data


class MessageFileHandler:
    def __init__(self, file_name: str):
        self.file_name = file_name
        self.file_handle = open(file_name, "rb")

    def _read_simulation_frame_at_time(self, sim_time: float):
        proceed = True
        while proceed:
            message = delimited_protobuf.read(self.file_handle, cielimMessage.CielimMessage)
            if cielimMessage.currentTime.simTimeElapsed >= sim_time:
                proceed = False
                return message

    def get_simulation_frame_at_time(self, sim_time: float):
        message = self._read_simulation_frame_at_time(sim_time)
        self.file_handle.seek(0)
        return message

    def jump_to_simulation_frame_at_time(self, sim_time: float):
        return self._read_simulation_frame_at_time(sim_time)

    def get_next_simulation_frame(self):
        try:
            return delimited_protobuf.read(self.file_handle, cielimMessage.CielimMessage)
        except:
            print("Protobuf failed to decode.")
            return None
