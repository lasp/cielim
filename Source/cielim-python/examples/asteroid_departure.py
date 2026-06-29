import os

import cv2
import numpy as np

import cielim


current_file_path = os.path.dirname(__file__)


def append_protobuf_to_file(filename, message):
    """
    Appends a serialized protobuf message to a file
    """
    serialized_data = message.SerializeToString()

    with open(filename, "ab") as f:
        f.write(serialized_data)


def scene_setup() -> cielim.Scene:
    """
    Set up the scene with the spacecraft looking directly at a sphere.
    """
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, 2000), attitude=(0, 1, 0))

    scene.set_sensor_params(exposure=4e-5)

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="sphere_normalized", mesh_brdf="Lambertian", mesh_radius=1000)

    return scene


def departure_scene(number_of_images: int):
    """
    Generate a scenario in which the camera starts close to the asteroid and is progressively moved further away.
    This can test the rendering methods and accuracy at all distances.
    """
    scene = scene_setup()

    # prep file for saving
    directory_path = current_file_path + "/images-departure"
    protobuff_file = directory_path + "/departure.bin"
    os.makedirs(directory_path, exist_ok=True)

    position_shift = np.array([0, 0, 10000])

    connector = cielim.Connector()
    launcher = cielim.Launcher()

    connector.connect(launcher.launch())
    connector.send_init_request()

    message = scene.get_scene()

    initial_position = np.array(message.spacecraft.position)

    for idx in range(number_of_images):

        new_position = initial_position + position_shift * idx

        # Move the spacecraft away
        scene.set_spacecraft_params(position=tuple(new_position))

        # Generate image

        image_name = "image-" + str(idx)

        connector.send_frame(message)
        [image, _, _] = connector.request_image_for_camera_id(1, True, False)

        cv2.imwrite(directory_path + "/" + image_name + ".png", image)
        append_protobuf_to_file(protobuff_file, message)

    connector.disconnect()
    launcher.terminate()


if __name__ == "__main__":
    number_of_images = 100
    departure_scene(number_of_images)
