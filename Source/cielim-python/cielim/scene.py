from numpy import ndarray

import cielimMessage_pb2
from orbital_motion import *
from rigid_body_kinematics import *
import numpy as np
from qe_curve_fit import qe_curve_fit


class Scene(object):
    def __init__(self):
        self.cielim_msg = cielimMessage_pb2.CielimMessage()
        self.target_name = ""
        self.gravitational_parameter = 0

    def set_existing_message(self, cielim_msg: cielimMessage_pb2.CielimMessage) -> None:
        """
        Set an existing message
        :param: cielim_msg (cielim message type)
        """
        self.cielim_msg = cielim_msg

    def set_pointing_target(self, target_name: str) -> None:
        """
        Set the name of the pointing target for the camera
        :param: target_name (string)
        """
        self.target_name = target_name

    def set_gravitational_parameter(self, gravitational_parameter: float) -> None:
        """
        Set gravitational parameter of central body in SI units
        :param: gravitational_parameter (SI)
        """
        self.gravitational_parameter = gravitational_parameter

    def set_orbital_elements(
        self, orbital_elements: ClassicOrbitalElements, gravitational_parameter: float = 0
    ) -> None:
        """
        Set spacecraft position with orbital elements
        :param: orbital_elements
        :param: optional, gravitational_parameter (SI)
        """
        if gravitational_parameter != 0:
            self.gravitational_parameter = gravitational_parameter
        position, velocity = orbital_elements_to_cartesian(self.gravitational_parameter, orbital_elements)
        self.cielim_msg.spacecraft.ClearField("position")
        self.cielim_msg.spacecraft.ClearField("velocity")
        [self.cielim_msg.spacecraft.position.append(item) for item in position]
        [self.cielim_msg.spacecraft.velocity.append(item) for item in velocity]

    def set_mrp(self, mrp: ndarray) -> None:
        """
        Set attitude with a modified rodrigues parameter
        :param: mrp
        """
        self.cielim_msg.spacecraft.ClearField("attitude")
        [self.cielim_msg.spacecraft.attitude.append(item) for item in mrp]

    def set_prv(self, prv: ndarray) -> None:
        """
        Set attitude with a principal rotation vector
        :param: prv
        """
        mrp = principalRotation_to_mrp(prv)
        self.cielim_msg.spacecraft.ClearField("attitude")
        [self.cielim_msg.spacecraft.attitude.append(item) for item in mrp]

    def set_dcm(self, dcm: ndarray) -> None:
        """
        Set attitude with a direction cosine matrix
        :param: dcm
        """
        mrp = dcm_to_mrp(dcm)
        self.cielim_msg.spacecraft.ClearField("attitude")
        [self.cielim_msg.spacecraft.attitude.append(item) for item in mrp]

    def set_euler321(self, euler321: ndarray) -> None:
        """
        Set attitude with euler angles
        :param: euler321
        """
        mrp = euler321_to_mrp(euler321)
        self.cielim_msg.spacecraft.ClearField("attitude")
        [self.cielim_msg.spacecraft.attitude.append(item) for item in mrp]

    def set_euler321_pointing_offset(self, delta_euler321: ndarray) -> None:
        """
        Add a pointing offset using euler angles (assuming small offsets)
        :param: delta_euler321
        """
        delta_dcm = euler321_to_dcm(delta_euler321)
        dcm = mrp_to_dcm(self.cielim_msg.spacecraft.attitude)
        mrp = dcm_to_mrp(np.dot(delta_dcm, dcm))
        self.cielim_msg.spacecraft.ClearField("attitude")
        [self.cielim_msg.spacecraft.attitude.append(item) for item in mrp]

    def look_at_target(self, target_name: str = "") -> None:
        """
        Function to point the camera at the target in the scene. The velocity direction of the
        relative motion is used as the secondary direction to make the camera pointing frame.
        If the target is not found among the bodies, the pointing will point to the zero inertial point
        :param target_name: optional, reset the target (string)
        :return:
        """
        if target_name != "":
            self.target_name = target_name
        elif self.target_name == "":
            print("No target name provided, pointing to center of inertial frame")

        target_position = np.zeros(3)
        target_velocity = np.zeros(3)
        spacecraft_position = np.array(self.cielim_msg.spacecraft.position)
        spacecraft_velocity = np.array(self.cielim_msg.spacecraft.velocity)
        camera_position = np.array(self.cielim_msg.camera.cameraPositionInBody)
        camera_orientation = np.array(self.cielim_msg.camera.bodyFrameToCameraMrp)
        for body in self.cielim_msg.celestialBodies:
            if body.bodyName.lower() == target_name.lower():
                target_position = np.array(body.position)
                target_velocity = np.array(body.velocity)

        primary = target_position - (spacecraft_position - camera_position)
        primary /= np.linalg.norm(primary)

        secondary = target_velocity - spacecraft_velocity
        secondary /= np.linalg.norm(secondary)

        BN = body_to_inertial_for_pointing(primary, secondary, mrp_to_dcm(camera_orientation))
        self.cielim_msg.spacecraft.ClearField("attitude")
        [self.cielim_msg.spacecraft.attitude.append(item) for item in dcm_to_mrp(BN)]

    def propagate(self, end_time: float, gravitational_parameter: float = 0) -> None:
        """
        Function to propagate the camera position.
        If the target is not found among the bodies, the pointing will point to the zero inertial point
        :param end_time: time (seconds) to go to
        :param gravitational_parameter: optional, reset gravitational parameter (SI)
        :param target_name: optional, reset target (string)
        :return:
        """
        if gravitational_parameter != 0:
            self.gravitational_parameter = gravitational_parameter
        elif self.gravitational_parameter == "":
            print("No gravitational parameter provided, rectilinear trajectory assumed")

        initial_state = np.array(list(self.cielim_msg.spacecraft.position) + list(self.cielim_msg.spacecraft.velocity))
        final_state = propagate_cartesian(self.gravitational_parameter, initial_state, 0, end_time)
        self.cielim_msg.spacecraft.ClearField("position")
        self.cielim_msg.spacecraft.ClearField("velocity")
        [self.cielim_msg.spacecraft.position.append(item) for item in final_state[:3]]
        [self.cielim_msg.spacecraft.velocity.append(item) for item in final_state[3:]]

    def propagate_and_stare(self, end_time: float, gravitational_parameter: float = 0, target_name: str = "") -> None:
        """
        Function to propagate the camera position and maintain the pointing of the camera to the target in the scene.
        If the target is not found among the bodies, the pointing will point to the zero inertial point
        :param end_time: time (seconds) to go to
        :param gravitational_parameter: optional, reset gravitational parameter (SI)
        :param target_name: optional, reset target (string)
        :return:
        """
        self.propagate(end_time, gravitational_parameter)
        self.look_at_target(target_name)

    def set_qe_curve_fit(
        self,
        qe_data_path: str,
        solid_angle: float,
        pixel_area: float,
        wavelength_window: list = None,
    ) -> None:
        fit_wavelengths, fit_values = qe_curve_fit(
            qe_data_path, solid_angle, pixel_area, wavelength_window=wavelength_window, show_plots=False
        )
        self.cielim_msg.renderParameters.wavelength1 = fit_wavelengths[0]
        self.cielim_msg.renderParameters.wavelength2 = fit_wavelengths[1]
        self.cielim_msg.renderParameters.wavelength3 = fit_wavelengths[2]
        self.cielim_msg.camera.sensorModel.qeCurve.redValue1 = fit_values[0]
        self.cielim_msg.camera.sensorModel.qeCurve.greenValue1 = fit_values[0]
        self.cielim_msg.camera.sensorModel.qeCurve.blueValue1 = fit_values[0]
        self.cielim_msg.camera.sensorModel.qeCurve.redValue2 = fit_values[1]
        self.cielim_msg.camera.sensorModel.qeCurve.greenValue2 = fit_values[1]
        self.cielim_msg.camera.sensorModel.qeCurve.blueValue2 = fit_values[1]
        self.cielim_msg.camera.sensorModel.qeCurve.redValue3 = fit_values[2]
        self.cielim_msg.camera.sensorModel.qeCurve.greenValue3 = fit_values[2]
        self.cielim_msg.camera.sensorModel.qeCurve.blueValue3 = fit_values[2]

    def get_scene(self) -> cielimMessage_pb2.CielimMessage:
        """
        Return the current state of the protobuffer
        :return: protobuffer message
        """
        return self.cielim_msg
