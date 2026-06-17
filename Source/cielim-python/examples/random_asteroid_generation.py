import json
import os
import time

import cv2
import numpy as np
from numpy import ndarray

import cielim
from cielim import orbital_motion, scene
from cielim import rigid_body_kinematics as rbk

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


def scene_setup() -> cielim.CielimMessage:
    """
    Setup basic scene: populate default values in protobuffer
    """
    protobuf_message = cielim.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "2000269"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.velocity.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]

    body.model.shapeModel = "bennu_normalized"
    body.model.meanRadius = 58232 * 1e3

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, 0]]  # This gets randomized
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    protobuf_message.camera.sensorModel.exposureTime = 5e-4
    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [20 * np.pi / 180, 15 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [1, 1, 1]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [2000, 1500]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -1000000]]
    [protobuf_message.spacecraft.velocity.append(item) for item in [0, 1000, 0]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message


def random_asteroid_generation(number_of_images: int):
    """
    Generate a random set of asteroid images with varying lighting conditions, size, shape, etc.
    Save diagnistic data alongside each image for post-processing.
    """
    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup())

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

        message = scene_frame.get_scene()
        # Set a random shape model
        shape_model = np.random.choice(models)
        radius = np.random.normal(mean_radius, std_radius)
        message.celestialBodies[0].model.ClearField("shapeModel")
        message.celestialBodies[0].model.ClearField("meanRadius")
        message.celestialBodies[0].model.shapeModel = shape_model
        message.celestialBodies[0].model.meanRadius = radius

        # Set random axial distortionas
        distortions = np.random.normal(1, std_principal_axis_scales, size=3)
        message.celestialBodies[0].model.ClearField("principalAxisDistortion")
        [message.celestialBodies[0].model.principalAxisDistortion.append(item) for item in distortions]

        # Set a random lighting
        sun_position = np.random.uniform(-1, 1, size=3)
        sun_heading = sun_position / np.linalg.norm(sun_position)
        message.celestialBodies[1].ClearField("position")
        [message.celestialBodies[1].position.append(item) for item in sun_heading * 1.496e11]

        scene_frame.set_existing_message(message)

        # Set a random orbital elements
        elements = orbital_motion.ClassicOrbitalElements()
        elements.semi_major_axis = np.random.normal(2000e3, 400e3)
        elements.eccentricity = np.random.uniform(0, 0.5)
        elements.inclination = np.random.uniform(-np.pi / 2, np.pi / 2)
        elements.ascending_node = np.random.uniform(-np.pi / 2, np.pi / 2)
        elements.argument_periapsis = np.random.uniform(-np.pi / 2, np.pi / 2)
        elements.true_anomaly = np.random.uniform(-np.pi / 2, np.pi / 2)
        scene_frame.set_orbital_elements(elements, 0.014146 * 1e9)

        # Point to target
        scene_frame.look_at_target("2000269")

        message = scene_frame.get_scene()

        mean_position = np.array(message.spacecraft.position)
        position_error = np.random.normal(0, std_position_error, size=3)
        true_position = mean_position + position_error

        message.spacecraft.ClearField("position")
        [message.spacecraft.position.append(item) for item in true_position]
        scene_frame.set_existing_message(message)

        # Generate image
        image_name = "image-" + str(idx)
        connector.send_init_request()  # re-initialize shape model
        connector.send_frame(scene_frame.get_scene())
        [image, center_of_brightness, _] = connector.request_image_for_camera_id(1)
        if center_of_brightness is not None:
            cv2.imwrite(directory_path + "/" + image_name + ".png", image)

            # Save randomized data to file
            dcm_BN = rbk.mrp_to_dcm(message.spacecraft.attitude)
            dcm_CB = rbk.mrp_to_dcm(message.camera.bodyFrameToCameraMrp)
            true_position_heading = np.array(true_position) / np.linalg.norm(true_position)
            mean_position_heading = np.array(mean_position) / np.linalg.norm(mean_position)
            com_pixel = vector_to_pixel(-np.dot(dcm_CB, np.dot(dcm_BN, true_position_heading)), message.camera)

            data = {}
            data["image"] = image_name
            data["center_of_brightness"] = list(center_of_brightness)
            data["center_of_mass"] = com_pixel[:2].tolist()
            data["asteroid_mean_radius"] = mean_radius
            data["camera_ifov"] = message.camera.lensModel.fieldOfView[0] / message.camera.sensorModel.resolution[0]
            data["asteroid_std_radius"] = std_radius
            data["asteroid_std_streching"] = std_principal_axis_scales
            data["true_position_N"] = true_position.tolist()
            data["mean_position_N"] = mean_position.tolist()
            data["position_std"] = std_position_error
            data["sigma_BN"] = [x for x in message.spacecraft.attitude]
            data["sigma_CB"] = [x for x in message.camera.bodyFrameToCameraMrp]
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
