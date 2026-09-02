import json
import os
import pickle

import cv2
import numpy as np

import cielim
from cielim import variable_map

current_file_path = os.path.dirname(__file__)


""" Populate abstract variables of the VariableMap class in order to instruct it on how to read Basilisk MC data """


class BasiliskMCReader(variable_map.VariableMap):
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

    def get_number_of_simulations(self, variable_name):
        """
        Provide the number of simulations that are in the data
        """
        first_key = list(self.raw_data.keys())[0]
        self.num_runs = self.raw_data[first_key].columns.levshape[0]
        return self.num_runs

    def get_simulation_time(self, variable_name):
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
            parameter = list(filter(lambda key: self.variable_map[key] == cielim_parameter_name, self.variable_map))[0]
        except Exception:
            parameter = cielim_parameter_name

        return json.loads(self.raw_parameters[run_number][parameter])

    def get_simulation_variables(self, cielim_variable_name, run_number, time):
        """
        Extract a variable from a specific run
        Note: if the variable is not in the mapping dictionary, try reading it directly from the data file
        """
        try:
            key = list(filter(lambda key: self.variable_map[key] == cielim_variable_name, self.variable_map))[0]
        except Exception:
            key = cielim_variable_name

        data = self.raw_data[key]
        return data.loc[round(time * 1e9), run_number].to_list()


""" Default scene setup """


def scene_setup() -> cielim.Scene:
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, -1000000), velocity=(0, 1000, 0))

    scene.set_lens_params(fov=(30 * np.pi / 180, 20 * np.pi / 180))

    scene.set_sensor_params(resolution=(2000, 1500), exposure=1)

    scene.set_celestial_body_params(0, position=(0, 0, -10000))

    index = scene.add_celestial_body("2000269")

    scene.set_celestial_body_params(index, mesh_shape="bennu_normalized", mesh_brdf="Lambertian", mesh_radius=500 * 1e3)

    return scene


""" Example script to read and save images from a Basilisk MC scenario """


def saved_monte_carlo_scenario():
    scene = scene_setup()

    reader = BasiliskMCReader()
    data_path = os.path.dirname(current_file_path) + "/support-data/monte-carlo-sample/"
    reader.set_data_directory(data_path)
    reader.add_variable_mapping("scStateOutMsg.sigma_BN.data", "attitude")
    reader.add_variable_mapping("sNavTransMsg.r_BN_N.data", "position")
    reader.read_simulation_data()

    # prep file for saving
    directory_path = current_file_path + "/images-saved-monte-carlo"
    os.makedirs(directory_path, exist_ok=True)

    connector = cielim.Connector()
    launch = cielim.Launcher()
    connector.connect(launch.launch())
    connector.send_init_request()

    cadence = 60

    for run_number in range(reader.get_number_of_simulations("")):
        r_BcB_B = reader.get_simulation_parameters("TaskList[0].TaskModels[0].hub.r_BcB_B", run_number)

        for time in reader.get_simulation_time(""):
            if np.round(time, 2) % cadence == 0:
                position = reader.get_simulation_variables("position", run_number, time)
                attitude = reader.get_simulation_variables("attitude", run_number, time)

                scene.set_spacecraft_params(position=position, attitude=attitude)

                connector.send_frame(scene.get_scene())
                [image, _, _] = connector.request_image_for_camera_id(1, True, False)
                cv2.imwrite(
                    directory_path + "/run-" + str(run_number) + "-time-" + str(np.round(time, 2)) + ".png", image
                )

    connector.disconnect()
    launch.terminate()


if __name__ == "__main__":
    saved_monte_carlo_scenario()
