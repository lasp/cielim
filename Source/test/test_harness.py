import delimited_protobuf
import cv2
import numpy as np
import os
import struct
import sys
import time
import typing
import base64
import zmq

import cielimMessage_pb2

class Connector:
    def __init__(self):
        self.address = ""
        self.context = None
        self.request_socket = None

    def connect(self, address: str = "tcp://localhost:5556"):
        self.context = zmq.Context()
        self.request_socket = self.context.socket(zmq.REQ)
        self.request_socket.set(zmq.SocketOption.CONNECT_TIMEOUT, 10)

        self.address = address
        self.request_socket.connect(address)
        self._send_ping()
        self._send_ping()

    def _send_ping(self):
        self.request_socket.send_string("PING")
        result = self.request_socket.recv_string()
        print(result)
    
    def send_init_request(self):
        self.request_socket.send_string("INIT_SCENE")
        init_result = self.request_socket.recv_string()
        print(init_result)

    def send_frame(self, sim_frame: cielimMessage_pb2.CielimMessage):
        result = self.request_socket.send_multipart([b"SIM_UPDATE", b"", b"", sim_frame.SerializePartialToString()])
        print(result)
        response_message_parts = self.request_socket.recv()
        print(response_message_parts)

    def request_image_for_camera_id(self, camera_id: int, should_return_image: bool = True):
        self.request_socket.send_multipart(
            [b"REQUEST_IMAGE", str.encode(str(camera_id)), str.encode(str(int(should_return_image)))]
        )
        [cob_x, cob_y, image_data_size, image_data] = self.request_socket.recv_multipart()
        image = None
        if should_return_image:
            buf = np.asarray(bytearray(image_data), dtype="uint8")
            image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
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
            message = delimited_protobuf.read(self.file_handle, cielimMessage_pb2.CielimMessage)
            if message.currentTime.simTimeElapsed >= sim_time:
                proceed = False
                return message

    def get_simulation_frame_at_time(self, sim_time: float):
        message = self._read_simulation_frame_at_time(sim_time)
        self.file_handle.seek(0)
        return message

    def jump_to_simulation_frame_at_time(self, sim_time: float):
        return self._read_simulation_frame_at_time(sim_time)

    def get_next_simulation_frame(self):
        return delimited_protobuf.read(self.file_handle, cielimMessage_pb2.CielimMessage)
