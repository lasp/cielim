import json
import os
import pickle

import cv2
import numpy as np
import context
from driver import *
from launcher import *
from variable_map import *

from context import cielimMessage_pb2
from context import scene

current_file_path = os.path.dirname(__file__)


""" Populate abstract variables of the VariableMap class in order to instruct it on how to read Basilisk MC data """


class BasiliskMCReader(VariableMap):
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
        for variable_name in self.variable_map.keys():
            if variable_name.endswith(".data"):
                with open(os.path.join(self.data_directory, variable_name), "rb") as file:
                    self.raw_data[variable_name] = pickle.load(file)

    def get_number_of_simulations(self):
        """
        Provide the number of simulations that are in the data
        """
        first_key = list(self.raw_data.keys())[0]
        self.num_runs = self.raw_data[first_key].columns.levshape[0]
        return self.num_runs

    def get_simulation_time(self):
        """
        Provide the simulation time vector in the data
        """
        first_key = list(self.raw_data.keys())[0]
        return list(self.raw_data[first_key].index * 1e-9)  # Time in Basilisk is logged in nano-seconds

    def get_simulation_parameters(self, cielim_parameter_name, run_number):
        """
        Extract a parameter from a specific run
        Note: if the parameter is not in the mapping dictionary, try reading it directly from the parameter file
        """
        with open(os.path.join(self.data_directory, "run" + str(run_number) + ".json"), "rb") as file:
            self.raw_parameters[run_number] = json.load(file)

        try:
            parameter = self.parameter_map.keys()[self.parameter_map.values().index(cielim_parameter_name)]
        except:
            parameter = cielim_parameter_name

        return json.loads(self.raw_parameters[run_number][parameter])

    def get_simulation_variables(self, cielim_variable_name, run_number, time):
        """
        Extract a variable from a specific run
        Note: if the variable is not in the mapping dictionary, try reading it directly from the data file
        """
        try:
            key = list(filter(lambda key: self.variable_map[key] == cielim_variable_name, self.variable_map))[0]
        except:
            key = cielim_variable_name

        data = self.raw_data[key]
        return data.loc[round(time * 1e9), run_number].to_list()


""" Default scene setup """


def scene_setup():
    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "2000269"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.velocity.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]

    body.model.shapeModel = "bennu_normalized"
    body.model.meanRadius = 500 * 1e3

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, -10000]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    protobuf_message.camera.exposureTime = 1
    [protobuf_message.camera.fieldOfView.append(item) for item in [30 * np.pi / 180, 20 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [1, 1, 1]]
    [protobuf_message.camera.resolution.append(item) for item in [2000, 1500]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, -1000000]]
    [protobuf_message.spacecraft.velocity.append(item) for item in [0, 1000, 0]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    return protobuf_message


""" Example script to read and save images from a Basilisk MC scenario """


def saved_monte_carlo_scenario():
    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup())

    reader = BasiliskMCReader()
    data_path = os.path.dirname(current_file_path) + "/support-data/monte-carlo-sample/"
    reader.set_data_directory(data_path)
    reader.add_variable_mapping("scStateOutMsg.sigma_BN.data", "attitude")
    reader.add_variable_mapping("sNavTransMsg.r_BN_N.data", "position")
    reader.read_simulation_data()
    # prep file for saving
    directory_path = current_file_path + "/images-saved-monte-carlo"
    os.makedirs(directory_path, exist_ok=True)

    connector = Connector()
    launcher = Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()

    cadence = 60
    for run_number in range(reader.get_number_of_simulations()):
        r_BcB_B = reader.get_simulation_parameters("TaskList[0].TaskModels[0].hub.r_BcB_B", run_number)
        for time in reader.get_simulation_time():
            if np.round(time, 2) % cadence == 0:
                position = reader.get_simulation_variables("position", run_number, time)
                attitude = reader.get_simulation_variables("attitude", run_number, time)

                message = scene_frame.get_scene()
                message.spacecraft.ClearField("position")
                message.spacecraft.ClearField("attitude")
                [message.spacecraft.position.append(item) for item in position]
                [message.spacecraft.attitude.append(item) for item in attitude]
                scene_frame.set_existing_message(message)
                connector.send_frame(scene_frame.get_scene())
                [image, center_of_brightness] = connector.request_image_for_camera_id(1, 1)
                cv2.imwrite(
                    directory_path + "/run-" + str(run_number) + "-time-" + str(np.round(time, 2)) + ".png", image
                )

    connector.disconnect()
    launcher.terminate()


if __name__ == "__main__":
    saved_monte_carlo_scenario()
