# All definitions and transformations are pulled from Fundamentals of Astrodynamics and Applications by David A. Vallado, Chapter 1

from collections.abc import Callable

import numpy as np

circular_threshold = 1e-10


class ClassicOrbitalElements(object):
    """
    Container class for the classical orbital elements.

    Attributes:
        semi_major_axis (float | None): The semi-major axis in km.
        eccentricity (float | None): The eccentricity (dimensionless).
        inclination (float | None): The inclination in radians.
        ascending_node (float | None): The right ascension of the ascending node in radians.
        argument_periapsis (float | None): The argument of periapsis in radians.
        true_anomaly (float | None): The true anomaly angle in radians.
        radius_periapsis (float | None): The radius of periapsis in km.
    """

    argument_periapsis: float | None = None  # radians
    ascending_node: float | None = None  # radians
    eccentricity: float | None = None  # dimensionless
    inclination: float | None = None  # radians
    radius_periapsis: float | None = None  # km
    semi_major_axis: float | None = None  # km
    true_anomaly: float | None = None  # radians


def orbital_elements_to_cartesian(mu: float, elements: ClassicOrbitalElements) -> tuple[np.ndarray, np.ndarray]:
    """
    A function to handle the perfect parabolic case and distinguish it form the rectilinear elliptical case,
    provide a negative semi-major axis. The absolute value of the semi-major axis will be the radius of periapsis.

    Args:
        mu (float): Gravitational parameter of central body (units of km^3/s^2).
        elements (ClassicOrbitalElements): Classical orbital elements object.

    Returns:
        tuple[np.ndarray, np.ndarray]: position and velocity in inertial frame coordinates
    """
    if (
        elements.argument_periapsis is None
        or elements.ascending_node is None
        or elements.eccentricity is None
        or elements.inclination is None
        or elements.semi_major_axis is None
        or elements.true_anomaly is None
    ):
        raise ValueError("Not all orbital elements are provided.")

    # rectilinear elliptic orbit case
    if np.abs(elements.eccentricity - 1) < circular_threshold and elements.semi_major_axis > 0:
        Ecc = elements.true_anomaly  # true anomaly is treated as eccentric anomaly

        r_magnitude = elements.semi_major_axis * (1.0 - elements.eccentricity * np.cos(Ecc))
        v_magnitude = np.sqrt(2.0 * mu / r_magnitude - mu / elements.semi_major_axis * mu)

        direction = np.zeros(3)

        direction[0] = np.cos(elements.ascending_node) * np.cos(elements.argument_periapsis) - np.sin(
            elements.ascending_node
        ) * np.sin(elements.argument_periapsis) * np.cos(elements.inclination)
        direction[1] = np.sin(elements.ascending_node) * np.cos(elements.argument_periapsis) + np.cos(
            elements.ascending_node
        ) * np.sin(elements.argument_periapsis) * np.cos(elements.inclination)
        direction[2] = np.sin(elements.argument_periapsis) * np.sin(elements.inclination)

        position = r_magnitude * direction

        if np.sin(Ecc) > 0.0:
            velocity = -v_magnitude * direction
        else:
            velocity = v_magnitude * direction
    # parabolic case
    else:
        if elements.eccentricity == 1.0 and elements.semi_major_axis < 0:
            rp = -elements.semi_major_axis
            p = 2.0 * rp
        # elliptic and hyperbolic cases #
        else:
            p = elements.semi_major_axis * (1.0 - elements.eccentricity**2)

        r = p / (1.0 + elements.eccentricity * np.cos(elements.true_anomaly))

        theta = elements.argument_periapsis + elements.true_anomaly

        h = np.sqrt(mu * p)  # orbit angular momentum magnitude

        position = np.zeros(3)

        position[0] = r * (
            np.cos(elements.ascending_node) * np.cos(theta)
            - np.sin(elements.ascending_node) * np.sin(theta) * np.cos(elements.inclination)
        )
        position[1] = r * (
            np.sin(elements.ascending_node) * np.cos(theta)
            + np.cos(elements.ascending_node) * np.sin(theta) * np.cos(elements.inclination)
        )
        position[2] = r * (np.sin(theta) * np.sin(elements.inclination))

        velocity = np.zeros(3)

        velocity[0] = (
            -mu
            / h
            * (
                np.cos(elements.ascending_node)
                * (np.sin(theta) + elements.eccentricity * np.sin(elements.argument_periapsis))
                + np.sin(elements.ascending_node)
                * (np.cos(theta) + elements.eccentricity * np.cos(elements.argument_periapsis))
                * np.cos(elements.inclination)
            )
        )
        velocity[1] = (
            -mu
            / h
            * (
                np.sin(elements.ascending_node)
                * (np.sin(theta) + elements.eccentricity * np.sin(elements.argument_periapsis))
                - np.cos(elements.ascending_node)
                * (np.cos(theta) + elements.eccentricity * np.cos(elements.argument_periapsis))
                * np.cos(elements.inclination)
            )
        )
        velocity[2] = (
            -mu
            / h
            * (
                -(np.cos(theta) + elements.eccentricity * np.cos(elements.argument_periapsis))
                * np.sin(elements.inclination)
            )
        )

    return position, velocity


def cartesian_to_orbital_elements(mu: float, position: np.ndarray, velocity: np.ndarray) -> ClassicOrbitalElements:
    """
    If the orbit is rectilinear, the true anomaly will be the eccentric or hyperbolic anomaly.
    In a parabolic orbit, the semi-major axis will be the opposite of the radius at periapsis.

    Args:
        mu (float): gravitational parameter of central body (units of km^3/s^2)
        position (np.ndarray): position vector in inertial frame coordinates
        velocity (np.ndarray): velocity vector in inertial frame coordinates

    Returns:
        ClassicOrbitalElements: classical orbital elements object
    """
    elements = ClassicOrbitalElements()

    r_magnitude = np.linalg.norm(position)
    r_hat = position / np.linalg.norm(position)

    angular_momentum = np.cross(position, velocity)
    h = float(np.linalg.norm(angular_momentum))

    eccentricity_vector = np.cross(velocity, angular_momentum) - mu * r_hat
    elements.eccentricity = float(np.linalg.norm(eccentricity_vector)) / mu

    alpha = 2.0 / r_magnitude - np.dot(velocity, velocity) / mu

    # elliptic or hyperbolic case
    if np.abs(alpha) > circular_threshold:
        elements.semi_major_axis = 1.0 / alpha
    # parabolic case
    else:
        p = h**2 / mu
        rp = p / 2.0

        elements.semi_major_axis = -rp  # a is not defined for parabola, so - rp is returned instead
        elements.eccentricity = 1.0

    # rectilinear motion case
    if h < circular_threshold:
        e_hat = np.zeros(3)

        inertial_z = np.array([0.0, 0.0, 1.0])
        inertial_y = np.array([0.0, 1.0, 0.0])

        h_hat = np.cross(e_hat, inertial_z)
        ip = np.cross(e_hat, inertial_y)

        if np.linalg.norm(h_hat) > np.linalg.norm(ip):
            h_hat = h_hat / np.linalg.norm(h_hat)
        else:
            h_hat = ip / np.linalg.norm(ip)

        ip = np.cross(h_hat, e_hat)
    else:
        h_hat = angular_momentum / h

        if np.abs(elements.eccentricity) > 1e-10:
            e_hat = (1.0 / mu / elements.eccentricity) * eccentricity_vector
        else:
            e_hat = r_hat

        ip = np.cross(h_hat, e_hat)

    elements.inclination = np.arccos(h_hat[2])

    if elements.inclination is None:
        raise ValueError("Inclination is not defined.")

    if elements.inclination > circular_threshold and elements.inclination < np.pi - circular_threshold:
        elements.ascending_node = np.arctan2(h_hat[0], -h_hat[1])
        elements.argument_periapsis = np.arctan2(e_hat[2], ip[2])
    else:
        elements.ascending_node = 0.0
        elements.argument_periapsis = np.arctan2(e_hat[1], e_hat[0])

    # rectilinear motion case
    if h < circular_threshold:
        # elliptic case
        if alpha > 0:
            Ecc = np.arccos(1 - r_magnitude * alpha)
            if np.dot(position, velocity) > 0:
                Ecc = 2.0 * np.pi - Ecc
            elements.true_anomaly = Ecc  # eccentric anomaly is returned
        # hyperbolic case
        else:
            H = np.arccosh(r_hat * alpha + 1)
            if np.dot(position, velocity) < 0:
                H = 2.0 * np.pi - H
            elements.true_anomaly = H  # hyperbolic anomaly is returned
    else:
        elements.true_anomaly = np.arctan2(np.dot(np.cross(e_hat, r_hat), h_hat), np.dot(e_hat, r_hat))

    return elements


def runge_kutta_4(dynamics: Callable, time: np.ndarray, initial_state: np.ndarray, *args) -> np.ndarray:
    """
    Implementation of the 4th order Runge-Kutta method for numerical integration of ordinary differential equations.

    Args:
        dynamics (Callable): The function that computes the derivatives of the state vector.
        time (np.ndarray): An array of time points at which to evaluate the solution.
        initial_state (np.ndarray): The initial state vector at the first time point.
        *args: Optional additional arguments to pass to the dynamics function.

    Returns:
        np.ndarray: An array containing the integrated state vectors at each time point.
    """
    state = np.zeros([len(time), len(initial_state) + 1])

    state[0, 0] = time[0]
    state[0, 1:] = initial_state

    for i in range(len(time) - 1):
        step = time[i + 1] - time[i]

        state[i, 0] = time[i]

        k1 = step * dynamics(time[i], state[i, 1:], *args)
        k2 = step * dynamics(time[i] + 0.5 * step, state[i, 1:] + 0.5 * k1, *args)
        k3 = step * dynamics(time[i] + 0.5 * step, state[i, 1:] + 0.5 * k2, *args)
        k4 = step * dynamics(time[i] + step, state[i, 1:] + k3, *args)

        state[i + 1, 1:] = state[i, 1:] + (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        state[i + 1, 0] = time[i + 1]

    return state


def point_mass_dynamics(time: np.ndarray, state: np.ndarray, gravitational_parameter: float) -> np.ndarray:
    """
    A function to compute the dynamics of a point mass under the influence of gravity.

    Args:
        time (np.ndarray): The current time (not used in this function but included for compatibility).
        state (np.ndarray): The current state vector, where the first three elements are position and the last three elements are velocity.
        gravitational_parameter (float): The gravitational parameter of the central body (units of km^3/s^2).

    Returns:
        np.ndarray: The derivative of the state vector, where the first three elements are the velocity and the last three elements are the acceleration due to gravity.
    """
    dxdt = np.zeros(np.shape(state))

    dxdt[0:3] = state[3:]

    dxdt[3:] = -gravitational_parameter / np.linalg.norm(state[0:3]) ** 3.0 * state[0:3]

    return dxdt


def propagate_cartesian(
    gravitational_parameter: float, initial_state: np.ndarray, start_time: float, end_time: float
) -> np.ndarray:
    """
    A function to propagate the state of a point mass in a gravitational field using the Runge-Kutta 4th order method.

    Args:
        gravitational_parameter (float): The gravitational parameter of the central body (units of km^3/s^2).
        initial_state (np.ndarray): The initial state vector, where the first three elements are position and the last three elements are velocity.
        start_time (float): The start time of the integration arc.
        end_time (float): The end time of the integration arc.

    Returns:
        np.ndarray: The propagated state vector at the end time.
    """
    time = np.arange(start_time, end_time + 1, 1)  # 1 sec steps for orbital integration
    propagated = runge_kutta_4(point_mass_dynamics, time, initial_state, gravitational_parameter)

    return propagated[-1, 1:]
