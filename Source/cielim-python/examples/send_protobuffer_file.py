from context import driver, launcher
import os
import cv2
import argparse

if __name__ == "__main__":
    connector = driver.Connector()

    parser = argparse.ArgumentParser(
        description="Send protobuf to Cielim using either a new Cielim or already running Cielim process"
    )
    parser.add_argument(
        "-e",
        "--host",
        nargs="?",
        const="tcp://localhost:5556",
        default=None,
        help="Use existing Cielim process via specified host; default is localhost",
    )

    args = parser.parse_args()

    launch = None

    if args.host is not None:
        connector.connect(args.host)
    else:
        launch = launcher.Launcher()
        connector.connect(launch.launch())

    file_dir = os.path.dirname(__file__) + "/../../../Content/FlybyData/bin/"
    file_name = input("What is the bin file to test (name only): ")

    file_handler = driver.MessageFileHandler(file_dir + file_name)

    idx = 0
    image = None

    print(connector.send_init_request())

    while True:
        frame = file_handler.get_next_simulation_frame()

        if frame is None:
            break

        print(connector.send_frame(frame))
        [image, center_of_brightness] = connector.request_image_for_camera_id(1)

        cv2.imwrite("received_image_" + str(idx) + ".png", image)

        idx = idx + 1

    cv2.namedWindow("window_name", cv2.WINDOW_NORMAL)
    cv2.imshow("window_name", image)
    cv2.resizeWindow("window_name", 640, 480)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    connector.disconnect()

    if launch is not None:
        launch.terminate()
