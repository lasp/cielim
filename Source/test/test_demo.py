import cv2
from test_harness import *

if __name__ == "__main__":
    connector = Connector()
    connector.connect("tcp://127.0.0.1:5556")

    file_name = "../../../cielim/Content/FlybyData/bin/protofile_proxOps.bin"
    file_handler = MessageFileHandler(file_name)

    connector.send_frame(file_handler.get_simulation_frame_at_time(3494500000000.0))
    connector.send_frame(file_handler.get_simulation_frame_at_time(0.0))

    connector.send_frame(file_handler.jump_to_simulation_frame_at_time(3494500000000.0))
    connector.send_frame(file_handler.get_next_simulation_frame())
    
    message = None
    while message is not None:
        message = file_handler.get_next_simulation_frame()
        connector.send_frame(message)

    image = connector.request_image_for_camera_id(1)
    cv2.imwrite("received_image.png", image)

    cv2.namedWindow("window_name", cv2.WINDOW_NORMAL)
    cv2.imshow("window_name", image)
    cv2.resizeWindow("window_name", 640, 480)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    connector.disconnect()
