import numpy as np
from numpy import ndarray

from . import orbital_motion
from . import rigid_body_kinematics as rbk
from .scene import Scene


def set_orbital_elements(
    scene: Scene,
    orbital_elements: orbital_motion.ClassicOrbitalElements,
    gravitational_parameter: float = 0,
) -> None:
    """
    Set spacecraft position and velocity with orbital elements.

    Args:
        scene (Scene): The Scene object to update.
        orbital_elements (ClassicOrbitalElements): The orbital elements to use.
        gravitational_parameter (float, optional): The gravitational parameter of the central body in SI units. Defaults to 0.
    """
    position, velocity = orbital_motion.orbital_elements_to_cartesian(gravitational_parameter, orbital_elements)

    scene.set_spacecraft_params(position=tuple(position), velocity=tuple(velocity))


def set_euler321_pointing_offset(scene: Scene, delta_euler321: ndarray) -> None:
    """
    Add a pointing offset using euler angles (assuming small offsets).

    Args:
        scene (Scene): The Scene object to update.
        delta_euler321 (ndarray): The small pointing offset in euler angles (radians).
    """
    delta_dcm = rbk.euler321_to_dcm(delta_euler321)
    dcm = rbk.mrp_to_dcm(np.array(scene.get_scene().spacecraft.attitude))
    mrp = rbk.dcm_to_mrp(np.dot(delta_dcm, dcm))

    scene.set_spacecraft_params(attitude=tuple(mrp))


def look_at_target(scene: Scene, target_name: str) -> None:
    """
    Function to point the camera at the target in the scene.
    The velocity direction of the relative motion is used as the secondary direction to make the camera pointing frame.
    If the target is not found among the bodies, the pointing will point to the zero inertial point.

    Args:
        scene (Scene): The Scene object to update.
        target_name (str): The name of the target celestial body to look at. If not found, will point to the origin.
    """
    if not target_name:
        print("No target name provided, pointing to center of inertial frame.")

    target_position = np.zeros(3)
    target_velocity = np.zeros(3)

    spacecraft_position = np.array(scene.get_scene().spacecraft.position)
    spacecraft_velocity = np.array(scene.get_scene().spacecraft.velocity)

    camera_position = np.array(scene.get_scene().camera.cameraPositionInBody)
    camera_orientation = np.array(scene.get_scene().camera.bodyFrameToCameraMrp)

    for body in scene.get_scene().celestialBodies:
        if body.bodyName.lower() == target_name.lower():
            target_position = np.array(body.position)
            target_velocity = np.array(body.velocity)

    primary = target_position - (spacecraft_position - camera_position)
    primary /= np.linalg.norm(primary)

    secondary = target_velocity - spacecraft_velocity
    secondary /= np.linalg.norm(secondary)

    BN = rbk.body_to_inertial_for_pointing(primary, secondary, rbk.mrp_to_dcm(camera_orientation))

    scene.set_spacecraft_params(attitude=tuple(rbk.dcm_to_mrp(BN)))


def propagate(scene: Scene, end_time: float, gravitational_parameter: float = 0) -> None:
    """
    Function to propagate the camera position.
    If the target is not found among the bodies, the pointing will point to the zero inertial point.

    Args:
        scene (Scene): The Scene object to update.
        end_time (float): Time (seconds) to propagate to.
        gravitational_parameter (float, optional): The gravitational parameter of the central body in SI units. Defaults to 0.
    """
    if gravitational_parameter <= 0:
        print("No gravitational parameter provided, rectilinear trajectory assumed.")

    initial_state = np.array(list(scene.get_scene().spacecraft.position) + list(scene.get_scene().spacecraft.velocity))
    final_state = orbital_motion.propagate_cartesian(gravitational_parameter, initial_state, 0, end_time)

    scene.set_spacecraft_params(position=tuple(final_state[:3]), velocity=tuple(final_state[3:]))


def propagate_and_stare(
    scene: Scene,
    end_time: float,
    gravitational_parameter: float = 0,
    target_name: str = "",
) -> None:
    """
    Function to propagate the camera position and maintain the pointing of the camera to the target in the scene.
    If the target is not found among the bodies, the pointing will point to the zero inertial point.

    Args:
        scene (Scene): The Scene object to update.
        end_time (float): Time (seconds) to propagate to.
        gravitational_parameter (float, optional): The gravitational parameter of the central body in SI units. Defaults to 0.
        target_name (str, optional): The name of the target body. Defaults to "".
    """
    propagate(scene, end_time, gravitational_parameter)
    look_at_target(scene, target_name)
