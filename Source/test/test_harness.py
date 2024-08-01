import delimited_protobuf
import cv2
import numpy as np
import os
import sys
import time
import typing
import base64
import zmq
sys.path.append(os.path.join(os.path.dirname(__file__), "vizProtobuffer"))
import vizMessage_pb2


class Connector:
    def __init__(self):
        self.address = ''
        self.context = zmq.Context()
        self.request_socket = self.context.socket(zmq.REQ)
        self.request_socket.set(zmq.SocketOption.CONNECT_TIMEOUT, 10)

    def connect(self, address: str = "tcp://localhost:5556"):
        self.address = address
        self.request_socket.connect(address)
        self._send_ping()
        self._send_ping()

    def _send_ping(self):
        self.request_socket.send_string("PING")
        result = self.request_socket.recv_string()
        print(result)

    def send_frame(self, sim_frame: vizMessage_pb2.VizMessage):
        result = self.request_socket.send_multipart([b'SIM_UPDATE', b'', b'', sim_frame.SerializePartialToString()])
        print(result)
        response_message_parts = self.request_socket.recv()
        print(response_message_parts)

    def request_image_for_camera_id(self, camera_id: int):
        camera_image_request = "REQUEST_IMAGE_" + str(camera_id)
        self.request_socket.send_string(camera_image_request)
        [image_bytes_size_msg, image_data_msg] = self.request_socket.recv_multipart()
        buf = np.asarray(bytearray(image_data_msg), dtype="uint8")
        image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return image

    def disconnect(self):
        self.request_socket.disconnect(self.address)
        self.context.destroy()


def create_simulation_frame():
    return protobuf_data


class MessageFileHandler:
    def __init__(self, file_name: str):
        self.file_name = file_name
        self.file_handle = open(file_name, "rb")

    def get_simulation_frame_at_time(self, sim_time: float):
        proceed = True
        while proceed:
            message = delimited_protobuf.read(self.file_handle, vizMessage_pb2.VizMessage)
            if message.currentTime.simTimeElapsed >= sim_time:
                proceed = False
                print(message.currentTime.simTimeElapsed)
                return message

    def get_next_simulation_frame(self):
        return delimited_protobuf.read(self.file_handle, vizMessage_pb2.VizMessage)
