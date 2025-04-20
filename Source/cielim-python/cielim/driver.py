import struct

import cv2
import delimited_protobuf
import numpy as np
import zmq
import random

import cielimMessage_pb2 as cielimMessage


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

    def _send_ping(self):
        _ = self.request_socket.send_string("PING")
        return self.request_socket.recv_multipart()[0].decode("utf-8")

    def send_init_request(self):
        _ = self.request_socket.send_string("INIT_SCENE")
        return self.request_socket.recv_multipart()[0].decode("utf-8")

    def send_frame(self, sim_frame: cielimMessage.CielimMessage):
        _ = self.request_socket.send_multipart([b"SIM_UPDATE", b"", b"", sim_frame.SerializePartialToString()])
        return self.request_socket.recv_multipart()[0].decode("utf-8")

    def request_image_for_camera_id(self, camera_id: int, should_return_image: bool = True):
        _ = self.request_socket.send_multipart(
            [b"REQUEST_IMAGE", str.encode(str(camera_id)), str.encode(str(int(should_return_image)))]
        )

        [image_data, image_data_size, cob_x, cob_y] = self.request_socket.recv_multipart()

        image = None
        if should_return_image:
            buf = np.asarray(bytearray(image_data), dtype="uint8")
            image = cv2.imdecode(buf, cv2.IMREAD_COLOR)

        cob = None
        if cob_x != b"" and cob_y != b"":
            cob = np.array([struct.unpack("d", cob_x)[0], struct.unpack("d", cob_y)[0]])

        return [image, cob]

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
        return delimited_protobuf.read(self.file_handle, cielimMessage.CielimMessage)
