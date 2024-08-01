import cv2
from test_harness import *

if __name__ == "__main__":
    connector = Connector()
    connector.connect("tcp://127.0.0.1:5556")

    file_name = "../../../cielim/Content/FlybyData/bin/protofile_proxOps.bin"
    file_handler = MessageFileHandler(file_name)

    connector.send_frame(file_handler.get_simulation_frame_at_time(3494500000000.0))

    connector.send_frame(file_handler.get_next_simulation_frame())

    image = connector.request_image_for_camera_id(1)
    cv2.imwrite("received_image.png", image)

    connector.disconnect()
