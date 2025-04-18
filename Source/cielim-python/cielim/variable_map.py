from abc import ABC, abstractmethod
import numpy as np

"""
Variable mapping class:
 - provide the location of the data
 - create a map between specific data variables and parameters and cielim
 - define the abstract methods to get simulation data
 """


class VariableMap(ABC):
    def __init__(self):
        self.variable_map = {}
        self.parameter_map = {}
        self.data_directory = ""

    @abstractmethod
    def get_number_of_simulations(self, variable_name: str) -> int:
        """
        Get the number of simulations in the data directory
        """
        pass

    @abstractmethod
    def get_simulation_time(self, variable_name: str) -> list:
        """
        Retrieve a list of simulation times
        """
        pass

    @abstractmethod
    def get_simulation_parameters(self, cielim_parameter_name: str, run_number: int) -> None:
        """
        Retrieve a specific simulation parameter
        """
        pass

    @abstractmethod
    def get_simulation_variables(self, cielim_variable_name: str, run_number: int, time: double) -> np.ndarray:
        """
        Retrieve a specific simulation variable
        """
        pass

    @abstractmethod
    def read_simulation_data(self) -> None:
        """
        Read and store the simulation data
        """
        pass

    def set_data_directory(self, data_directory: str) -> None:
        """
        Set path to the data
        :param: data_directory (string)
        """
        self.data_directory = data_directory

    def add_variable_mapping(self, variable_name: str, cielim_variable_name: str) -> None:
        """
        Add a variable name from the data as a key to the dictionary pointing to the cielim variable
        it corresponds to
        :param: variable_name (string)
        :param: cielim_variable_name (string)
        """
        self.variable_map[variable_name] = cielim_variable_name

    def add_parameter_mapping(self, parameter_name: str, cielim_variable_name: str) -> None:
        """
        Add a parameter name from the data as a key to the dictionary pointing to the cielim variable
        it corresponds to
        :param: parameter_name (string)
        :param: cielim_variable_name (string)
        """
        self.variable_map[parameter_name] = cielim_variable_name
