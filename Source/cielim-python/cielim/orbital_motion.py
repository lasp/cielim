# All definitions and transformations are pulled from Fundamentals of Astrodynamics and Applications
# by David A. Vallado, Chapter 1

from collections.abc import Callable
import numpy as np

circular_threshold = 1e-10


class ClassicOrbitalElements(object):
    """
    Container class for the classical orbital elements

        semi-major axis in km
        eccentricity
        inclination in rad
        right ascension of the ascending node in rad
        argument of periapsis in rad
        true anomaly angle in rad
        radius of periapsis in rad
    """

    semi_major_axis = None  # km
    eccentricity = None  # rad
    inclination = None  # rad
    ascending_node = None  # rad
    argument_periapsis = None  # rad
    true_anomaly = None  # rad
    radius_periapsis = None  # km


def orbital_elements_to_cartesian(mu: float, elements: ClassicOrbitalElements) -> (np.ndarray, np.ndarray):
    """
    orbital_elements_to_cartesian

        To handle the perfect parabolic case and distinguish it form the
        rectilinear elliptical case, provide a negative semi-major axis.
        The absolute value of the semi-major axis will be the radius of periapsis.

    :param mu: gravitational parameter of central body (units of km^3/s^2)
    :param elements: classical orbital elements
    :return: position, velocity in inertial frame coordinates
    """

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
    else:
        # parabolic case
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
    cartesian_to_orbital_elements
        If the orbit is rectilinear, the true anomaly will be the eccentric or hyperbolic anomaly
        In a parabolic orbit, the semi-major axis will be the opposite of the radius at periapsis.

    :param   mu:  gravitational parameter
    :param   position
    :param   velocity
    :return: ClassicOrbitalElements

    """
    elements = ClassicOrbitalElements()

    r_magnitude = np.linalg.norm(position)
    r_hat = position / np.linalg.norm(position)

    angular_momentum = np.cross(position, velocity)
    h = np.linalg.norm(angular_momentum)

    eccentricity_vector = np.cross(velocity, angular_momentum) - mu * r_hat
    elements.eccentricity = np.linalg.norm(eccentricity_vector) / mu

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


def runge_kutta_4(dynamics: Callable, time: np.ndarray, initial_state: np.ndarray, arg=None) -> np.ndarray:
    """
    runge_kutta_4

    :param dynamics: function to integrate
    :param time: time array
    :param initial_state: initial state vector
    :param arg: arguments if necessary for dynamics function
    :return: integrated state array of size of the time vector
    """

    if arg is not None:
        functionArg = arg
    state = np.zeros([len(time), len(initial_state) + 1])
    state[0, 0] = time[0]
    state[0, 1:] = initial_state
    for i in range(len(time) - 1):
        step = time[i + 1] - time[i]
        state[i, 0] = time[i]
        k1 = step * dynamics(time[i], state[i, 1:], functionArg)
        k2 = step * dynamics(time[i] + 0.5 * step, state[i, 1:] + 0.5 * k1, functionArg)
        k3 = step * dynamics(time[i] + 0.5 * step, state[i, 1:] + 0.5 * k2, functionArg)
        k4 = step * dynamics(time[i] + step, state[i, 1:] + k3, functionArg)
        state[i + 1, 1:] = state[i, 1:] + (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        state[i + 1, 0] = time[i + 1]
    return state


def point_mass_dynamics(time: np.ndarray, state: np.ndarray, gravitational_parameter: float) -> np.ndarray:
    """
    point_mass_dynamics

    :param time: time array
    :param state: state vector
    :param gravitational_parameter: gravitational parameter of central body
    :return: derivative of the state vector
    """
    dxdt = np.zeros(np.shape(state))
    dxdt[0:3] = state[3:]
    dxdt[3:] = -gravitational_parameter / np.linalg.norm(state[0:3]) ** 3.0 * state[0:3]
    return dxdt


def propagate_cartesian(
    gravitational_parameter: float, initial_state: np.ndarray, start_time: float, end_time: float
) -> np.ndarray:
    """
    propagate_cartesian

    :param gravitational_parameter: gravitational parameter of central body
    :param initial_state: initial state vector
    :param start_time: start time of integration arc
    :param end_time: end time of integration arc
    :return: propagated state
    """
    time = np.arange(start_time, end_time + 1, 1)  # 1 sec steps for orbital integration
    propagated = runge_kutta_4(point_mass_dynamics, time, initial_state, arg=gravitational_parameter)
    return propagated[-1, 1:]
