import context
from orbital_motion import *
import numpy as np


def test_rv_oe():
    gravitational_parameter = 1e10
    position = np.array([1e5, 1e6, 1e2])
    velocity = np.array([10, 20, 30])

    elements = cartesian_to_orbital_elements(gravitational_parameter, position, velocity)
    r, v = orbital_elements_to_cartesian(gravitational_parameter, elements)
    np.testing.assert_almost_equal(position, r, 8)
    np.testing.assert_almost_equal(velocity, v, 8)

    gravitational_parameter = 1e10
    position = np.array([1e5, 1e6, 0])
    h = np.array([0.0, 0.0, 1.0])
    velocity = np.sqrt(gravitational_parameter / np.linalg.norm(position)) * np.cross(
        h, position / np.linalg.norm(position)
    )
    elements = cartesian_to_orbital_elements(gravitational_parameter, position, velocity)
    np.testing.assert_almost_equal(elements.semi_major_axis, np.linalg.norm(position), 8)
    np.testing.assert_almost_equal(elements.eccentricity, 0, 8)
    np.testing.assert_almost_equal(elements.inclination, 0, 8)
    np.testing.assert_almost_equal(elements.true_anomaly, 0, 8)


def test_equations_of_motion():
    time = [0, 1]
    pos = [1e5, 1e6, 1e2]
    vel = [10, 20, 30]
    state = np.array(pos + vel)
    dstate_dt = point_mass_dynamics(time, state, 0)
    np.testing.assert_almost_equal(dstate_dt[:3], vel, 10)
    np.testing.assert_almost_equal(dstate_dt[3:], np.zeros(3), 10)

    gravitational_parameter = 1e10
    dstate_dt = point_mass_dynamics(time, state, gravitational_parameter)
    np.testing.assert_almost_equal(dstate_dt[:3], vel, 10)
    np.testing.assert_almost_equal(
        np.linalg.norm(dstate_dt[3:]), gravitational_parameter / np.linalg.norm(pos) ** 2, 10
    )

    times = list(range(0, 1001, 10))
    states = [state]
    for i in range(1, len(times)):
        states.append(propagate_cartesian(gravitational_parameter, states[-1], times[i - 1], times[i]))

    states = np.array(states)
    h = np.zeros([len(states[:, 0]), 3])
    energy = np.zeros(len(states[:, 0]))
    for i in range(len(states[:, 0])):
        h[i, :] = np.cross(states[i, :3], states[i, 3:])
        energy[i] = np.linalg.norm(states[i, 3:]) ** 2 / 2 - gravitational_parameter / np.linalg.norm(states[i, :3])

    np.testing.assert_allclose(h[:, 0], h[0, 0], rtol=1e-10)
    np.testing.assert_allclose(h[:, 1], h[0, 1], rtol=1e-10)
    np.testing.assert_allclose(h[:, 2], h[0, 2], rtol=1e-10)
    np.testing.assert_allclose(energy, energy[0])
