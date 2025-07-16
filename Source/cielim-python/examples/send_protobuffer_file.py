from context import driver, launcher
import os
import cv2
import argparse

current_file_path = os.path.dirname(__file__)

file_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path))) + "/Content/FlybyData/bin/"
test_dir = os.path.dirname(current_file_path) + "/support-data/protobufs/"

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
    parser.add_argument(
        "-f",
        "--filename",
        default=None,
        help="Name of file to send to Cielim",
    )
    parser.add_argument(
        "-s",
        "--hide_image",
        action="store_true",
        help="Hide image",
    )
    parser.add_argument(
        "-v",
        "--video",
        nargs="?",
        const=24,
        default=None,
        help="Create video with specified fps",
    )

    args = parser.parse_args()

    launch = None

    if args.host is not None:
        connector.connect(args.host)
    else:
        launch = launcher.Launcher()
        connector.connect(launch.launch())

    if args.filename is not None:
        file_name = args.filename
    else:
        file_name = input("What is the bin file to test (name only): ")

    file_name_base = os.path.splitext(os.path.basename(file_name))[0]
    image_folder = os.path.join(current_file_path, file_name_base) + "_images"

    os.makedirs(image_folder, exist_ok=True)

    if os.path.exists(file_dir + file_name):
        file = file_dir + file_name
    else:
        file = test_dir + file_name

    file_handler = driver.MessageFileHandler(file)

    idx = 0
    image = None

    print(connector.send_init_request())

    while True:
        frame = file_handler.get_next_simulation_frame()

        if frame is None:
            break

        print(f"Generating frame {idx}...")

        response = connector.send_frame(frame)
        [image, center_of_brightness] = connector.request_image_for_camera_id(1)

        cv2.imwrite(image_folder + f"/received_image_{idx}.png", image)

        print(f"Center of Brightness: {center_of_brightness}")
        print(response)

        idx = idx + 1

        if not args.hide_image:
            WindowName = f"Image_Client_{connector.identity}"
            cv2.namedWindow(WindowName, cv2.WINDOW_NORMAL)
            cv2.imshow(WindowName, image)
            cv2.resizeWindow(WindowName, 1250, 1000)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

    connector.disconnect()

    if launch is not None:
        launch.terminate()

    if args.video is not None:
        print("Generating video...")

        all_files = os.listdir(image_folder)

        frames = []

        for f in all_files:
            if f.startswith("received_image_") and f.endswith(".png"):
                frames.append(f)

        def extract_index(filename):
            base = filename.split("_")[-1]
            index = base.split(".")[0]
            return int(index)

        sorted_frames = sorted(frames, key=extract_index)

        first_frame = cv2.imread(os.path.join(image_folder, sorted_frames[0]))
        height, width, _ = first_frame.shape
        video_out = cv2.VideoWriter(
            f"{file_name_base}.mp4", cv2.VideoWriter_fourcc(*"mp4v"), args.video, (width, height)
        )

        for frame_name in sorted_frames:
            frame = cv2.imread(os.path.join(image_folder, frame_name))
            video_out.write(frame)

        video_out.release()

    print("Done.")
