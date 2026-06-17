import json
import os

import cv2
import numpy as np

import cielim
from cielim import rigid_body_kinematics as rbk
from cielim import scene, variable_map

current_file_path = os.path.dirname(__file__)


""" Populate abstract variables of the VariableMap class in order to instruct it on how to read Corto data """


class CortoReader(variable_map.VariableMap):
    def __init__(self):
        super().__init__()
        self.num_runs = 0
        self.num_components = 0
        self.time = []
        self.raw_data = {}
        self.raw_parameters = {}
        self.runs = []

    def read_simulation_data(self):
        """
        Read the simulation data from messages and pack into data dictionary
        """
        self.read_geometry_data()
        self.read_scene_data()

    def get_number_of_simulations(self):
        """
        Provide the number of simulations that are in the data
        """
        self.num_images = len(self.geometry_dict["body"]["position"])
        return self.num_images

    def get_simulation_time(self):
        pass

    def set_geometry_directory(self, path: str):
        """
        Path to geometry data
        """
        self.geometry_path = path

    def set_scene_directory(self, path: str):
        """
        Path to scene data
        """
        self.scene_path = path

    def read_geometry_data(self):
        """
        Read the geometry data from json and pack into data dictionary
        """
        with open(self.data_directory + self.geometry_path, "r") as file:
            self.geometry_dict = json.loads(file.read())

    def read_scene_data(self):
        """
        Read the scene data from json and pack into data dictionary
        """
        with open(self.data_directory + self.scene_path, "r") as file:
            self.scene_dict = json.loads(file.read())

    def get_simulation_variables(self, cielim_variable_name, run_number):
        """
        Extract a variable from a specific run
        Note: if the variable is not in the mapping dictionary, raise a KeyError
        """
        try:
            key = list(filter(lambda key: self.variable_map[key] == cielim_variable_name, self.variable_map))[0]
        except:
            raise KeyError(cielim_variable_name + " was not in the map")

        components = key.split(".")

        if components[0] in self.geometry_dict:
            data = self.geometry_dict[components[0]][components[1]]
        else:
            raise KeyError(str(components) + " was not in the map")

        return data[run_number]

    def get_simulation_parameters(self, cielim_parameter_name):
        """
        Extract a variable from a specific run
        Note: if the variable is not in the mapping dictionary, raise a KeyError
        """
        try:
            key = list(filter(lambda key: self.variable_map[key] == cielim_parameter_name, self.variable_map))[0]
        except:
            raise KeyError(cielim_parameter_name + " was not in the map")

        components = key.split(".")

        if components[0] in self.scene_dict:
            data = self.scene_dict[components[0]][components[1]]
        else:
            raise KeyError(str(components) + " was not in the map")

        return data


""" Default scene setup """


def scene_setup():
    protobuf_message = cielim.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "bennu"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.velocity.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]

    body.model.shapeModel = "bennu_normalized"
    body.model.meanRadius = 246
    body.model.refModel.brdfModel = "Regolith"

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -10000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    protobuf_message.camera.sensorModel.exposureTime = 1
    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [30 * np.pi / 180, 20 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [1, 1, 1]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [2000, 1500]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -1000000]]
    [protobuf_message.spacecraft.velocity.append(item) for item in [0, 1000, 0]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message


""" Example script to read and save images from a Corto scenario """


def corto_scenario():
    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup())

    reader = CortoReader()
    data_path = os.path.dirname(current_file_path) + "/support-data/corto-bennu-inputs/"
    reader.set_data_directory(data_path)
    reader.set_scene_directory("scene/scene.json")
    reader.set_geometry_directory("geometry/geometry.json")

    reader.read_geometry_data()
    reader.read_scene_data()

    reader.add_variable_mapping("body.orientation", "asteroid.attitude")
    reader.add_variable_mapping("body.position", "asteroid.position")
    reader.add_variable_mapping("camera.orientation", "spacecraft.attitude")
    reader.add_variable_mapping("camera.position", "spacecraft.position")
    reader.add_variable_mapping("sun.position", "sun.position")

    reader.add_variable_mapping("camera_settings.fov", "camera.lensModel.fieldOfView")
    reader.add_variable_mapping("camera_settings.res_x", "camera.sensorModel.resolution_x")
    reader.add_variable_mapping("camera_settings.res_y", "camera.sensorModel.resolution_y")
    reader.add_variable_mapping("camera_settings.film_exposure", "camera.sensorModel.exposureTime")
    # prep file for saving
    directory_path = current_file_path + "/images-corto"
    os.makedirs(directory_path, exist_ok=True)

    connector = cielim.Connector()
    launch = cielim.Launcher()
    connector.connect(launch.launch())

    number_of_images = int(reader.get_number_of_simulations() / 1000)
    for image_number in range(number_of_images):
        print("Processing image " + str(image_number))

        fov = reader.get_simulation_parameters("camera.lensModel.fieldOfView") * np.pi / 180
        res_x = reader.get_simulation_parameters("camera.sensorModel.resolution_x")
        res_y = reader.get_simulation_parameters("camera.sensorModel.resolution_y")
        exposure = reader.get_simulation_parameters("camera.sensorModel.exposureTime")

        asteroid_position = reader.get_simulation_variables("asteroid.position", image_number)
        asteroid_quaternion = reader.get_simulation_variables("asteroid.attitude", image_number)

        spacecraft_position = reader.get_simulation_variables("spacecraft.position", image_number)
        spacecraft_quaternion = reader.get_simulation_variables("spacecraft.attitude", image_number)

        sun_position = reader.get_simulation_variables("sun.position", image_number)

        asteroid_ep = np.array([asteroid_quaternion[-1]] + asteroid_quaternion[:3])
        asteroid_mrp = rbk.quaternion_to_mrp(asteroid_ep)
        asteroid_mrp = np.eye(3)

        spacecraft_ep = np.array(spacecraft_quaternion)
        spacecraft_mrp = rbk.quaternion_to_mrp(spacecraft_ep)
        TC = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]])

        camera_mrp = rbk.dcm_to_mrp(TC)
        message = scene_frame.get_scene()

        message.camera.lensModel.ClearField("fieldOfView")
        message.camera.sensorModel.ClearField("resolution")
        message.camera.ClearField("bodyFrameToCameraMrp")
        message.camera.sensorModel.exposureTime = exposure / 10000
        [message.camera.sensorModel.resolution.append(item) for item in [res_x, res_y]]
        [message.camera.lensModel.fieldOfView.append(item) for item in [fov, fov]]
        [message.camera.bodyFrameToCameraMrp.append(item) for item in camera_mrp]

        message.spacecraft.ClearField("position")
        message.spacecraft.ClearField("attitude")
        [message.spacecraft.position.append(item) for item in np.array(spacecraft_position) * 1000]
        [message.spacecraft.attitude.append(item) for item in np.array(spacecraft_mrp)]

        message.celestialBodies[0].ClearField("position")
        message.celestialBodies[0].ClearField("attitude")
        [message.celestialBodies[0].position.append(item) for item in np.array(asteroid_position) * 1000]
        [message.celestialBodies[0].attitude.append(item) for item in asteroid_mrp.flatten()]

        message.celestialBodies[1].ClearField("position")
        [
            message.celestialBodies[1].position.append(item)
            for item in np.array(sun_position) / np.linalg.norm(sun_position) * 1.496e11
        ]

        scene_frame.set_existing_message(message)
        connector.send_frame(scene_frame.get_scene())
        [image, _, _] = connector.request_image_for_camera_id(1, True, False)
        cv2.imwrite(directory_path + "/image-" + str(image_number) + ".png", image)

    connector.disconnect()
    launch.terminate()


if __name__ == "__main__":
    corto_scenario()
