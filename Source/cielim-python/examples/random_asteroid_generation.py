import json
import os
import time

import cv2
import numpy as np
from numpy import ndarray

import cielim
from cielim.utils import orbital_motion
from cielim.utils import rigid_body_kinematics as rbk
from cielim.utils import scene_dynamics

current_file_path = os.path.dirname(__file__)


def vector_to_pixel(vector_C: ndarray, camera: cielim.cielimProto.CameraModel) -> ndarray:
    """
    Computes the pixel location of a vector in the camera frame on the detector
    """
    center_pixel = [camera.sensorModel.resolution[0] / 2, camera.sensorModel.resolution[1] / 2]

    p_x = 2 * np.tan(camera.lensModel.fieldOfView[0] / 2)
    p_y = 2 * np.tan(camera.lensModel.fieldOfView[1] / 2)
    d_x = camera.sensorModel.resolution[0] / p_x
    d_y = camera.sensorModel.resolution[1] / p_y
    alpha = 0
    calibration_matrix = np.array(
        [
            [d_x, alpha, center_pixel[0]],
            [0.0, d_y, center_pixel[1]],
            [0.0, 0.0, 1.0],
        ]
    )

    return np.dot(calibration_matrix, vector_C)


def scene_setup() -> cielim.Scene:
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, -1000000), velocity=(0, 1000, 0))

    scene.set_lens_params(fov=(20 * np.pi / 180, 15 * np.pi / 180))

    scene.set_sensor_params(resolution=(2000, 1500), exposure=5e-4)

    index = scene.add_celestial_body("2000269")

    scene.set_celestial_body_params(
        index, mesh_shape="bennu_normalized", mesh_brdf="Lambertian", mesh_radius=58232 * 1e3
    )

    return scene


def random_asteroid_generation(number_of_images: int):
    """
    Generate a random set of asteroid images with varying lighting conditions, size, shape, etc.
    Save diagnistic data alongside each image for post-processing.
    """
    scene = scene_setup()

    # prep file for saving
    directory_path = current_file_path + "/images-com-cob"
    os.makedirs(directory_path, exist_ok=True)

    connector = cielim.Connector()
    launch = cielim.Launcher()
    connector.connect(launch.launch())
    connector.send_init_request()

    models = [
        "sphere_normalized",
        "vesta_normalized",
        "bennu_normalized",
        "itokawa_normalized",
        "eros_normalized",
        "67p_normalized",
    ]
    mean_radius = 25e3
    std_radius = 5e3
    std_principal_axis_scales = 0.2
    std_position_error = 1e4
    start = time.time()

    for idx in range(number_of_images):

        # Set a random shape model for asteroid

        shape_model = np.random.choice(models)
        radius = np.random.normal(mean_radius, std_radius)

        scene.set_celestial_body_params(1, mesh_shape=shape_model, mesh_radius=radius)

        # Set random axial distortionas

        distortions = np.random.normal(1, std_principal_axis_scales, size=3)

        scene.set_celestial_body_params(1, mesh_distortions=tuple(distortions))

        # Set a random lighting

        sun_position = np.random.uniform(-1, 1, size=3)
        sun_heading = sun_position / np.linalg.norm(sun_position)

        scene.set_celestial_body_params(0, position=tuple(1.496e11 * sun_heading))

        # Set a random orbital elements
        elements = orbital_motion.ClassicOrbitalElements()
        elements.semi_major_axis = np.random.normal(2000e3, 400e3)
        elements.eccentricity = np.random.uniform(0, 0.5)
        elements.inclination = np.random.uniform(-np.pi / 2, np.pi / 2)
        elements.ascending_node = np.random.uniform(-np.pi / 2, np.pi / 2)
        elements.argument_periapsis = np.random.uniform(-np.pi / 2, np.pi / 2)
        elements.true_anomaly = np.random.uniform(-np.pi / 2, np.pi / 2)

        scene_dynamics.set_orbital_elements(scene, elements, 0.014146 * 1e9)

        # Point to target
        scene_dynamics.look_at_target(scene, "2000269")

        mean_position = np.array(scene.get_scene().spacecraft.position)
        position_error = np.random.normal(0, std_position_error, size=3)
        true_position = mean_position + position_error

        scene.set_spacecraft_params(position=tuple(true_position))

        # Generate image
        image_name = "image-" + str(idx)
        connector.send_init_request()  # re-initialize shape model
        connector.send_frame(scene.get_scene())
        [image, center_of_brightness, _] = connector.request_image_for_camera_id(1)

        if center_of_brightness is not None:
            cv2.imwrite(directory_path + "/" + image_name + ".png", image)

            # Save randomized data to file
            dcm_BN = rbk.mrp_to_dcm(np.array(scene.get_scene().spacecraft.attitude))
            dcm_CB = rbk.mrp_to_dcm(np.array(scene.get_scene().camera.bodyFrameToCameraMrp))
            true_position_heading = np.array(true_position) / np.linalg.norm(true_position)
            mean_position_heading = np.array(mean_position) / np.linalg.norm(mean_position)
            com_pixel = vector_to_pixel(
                -np.dot(dcm_CB, np.dot(dcm_BN, true_position_heading)), scene.get_scene().camera
            )

            data = {}
            data["image"] = image_name
            data["center_of_brightness"] = list(center_of_brightness)
            data["center_of_mass"] = com_pixel[:2].tolist()
            data["asteroid_mean_radius"] = mean_radius
            data["camera_ifov"] = (
                scene.get_scene().camera.lensModel.fieldOfView[0] / scene.get_scene().camera.sensorModel.resolution[0]
            )
            data["asteroid_std_radius"] = std_radius
            data["asteroid_std_streching"] = std_principal_axis_scales
            data["true_position_N"] = true_position.tolist()
            data["mean_position_N"] = mean_position.tolist()
            data["position_std"] = std_position_error
            data["sigma_BN"] = [x for x in scene.get_scene().spacecraft.attitude]
            data["sigma_CB"] = [x for x in scene.get_scene().camera.bodyFrameToCameraMrp]
            data["phase_angle"] = np.arccos(np.dot(sun_heading, mean_position_heading))
            data["sun_heading_C"] = np.dot(np.dot(dcm_CB, dcm_BN), sun_heading).tolist()
            data["sun_heading_N"] = sun_heading.tolist()

            with open(directory_path + "/" + image_name + ".json", "w") as fp:
                json.dump(data, fp)
            fp.close()

    end = time.time()
    print("Generated " + str(number_of_images) + " images in " + str(end - start) + " seconds.")
    connector.disconnect()
    launch.terminate()


if __name__ == "__main__":
    number_of_images = 1000
    random_asteroid_generation(number_of_images)
