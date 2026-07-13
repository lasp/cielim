import numpy as np
import pytest

from cielim.utils import orbital_motion

mu = 1e10


def make_elements(semi_major_axis, eccentricity, inclination, ascending_node, argument_periapsis, true_anomaly):
    elements = orbital_motion.ClassicOrbitalElements()
    elements.semi_major_axis = semi_major_axis
    elements.eccentricity = eccentricity
    elements.inclination = inclination
    elements.ascending_node = ascending_node
    elements.argument_periapsis = argument_periapsis
    elements.true_anomaly = true_anomaly
    return elements

ORBIT_TYPES = [
    ("circular", 7e5, 0.0, 0.5, 0.3, 0.0, 1.0, False),
    ("elliptic", 7e5, 0.3, 0.6, 0.5, 1.0, 0.8, True),
    ("polar", 7e5, 0.2, np.pi / 2, 0.4, 0.9, 1.2, True),
    ("retrograde", 7e5, 0.25, 2.6, 0.3, 0.7, 2.0, True),
    ("hyperbolic", -7e5, 1.5, 0.5, 0.2, 0.6, 0.5, True),
    ("near_circular (e=0.001)", 7e5, 0.001, 0.5, 0.3, 0.4, 1.0, True),
    ("near_equatorial (i=0.001deg)", 7e5, 0.2, np.radians(0.001), 0.3, 0.4, 1.0, True),
]


@pytest.mark.parametrize(
    "test_name, a, e, i, ascending_node, argument_periapsis, true_anomaly, well_defined", ORBIT_TYPES
)
def test_orbital_elements_round_trip(
    test_name, a, e, i, ascending_node, argument_periapsis, true_anomaly, well_defined
):
    """
    Checks that converting orbital elements → position/velocity → orbital elements gives back the same numbers you started with,
    across different orbit shapes.
    """
    original_elements = make_elements(a, e, i, ascending_node, argument_periapsis, true_anomaly)
    position, velocity = orbital_motion.orbital_elements_to_cartesian(mu, original_elements)

    recovered_elements = orbital_motion.cartesian_to_orbital_elements(mu, position, velocity)

    round_trip_position, round_trip_velocity = orbital_motion.orbital_elements_to_cartesian(mu, recovered_elements)
    np.testing.assert_allclose(position, round_trip_position, rtol=1e-8, atol=1e-3, err_msg=test_name)
    np.testing.assert_allclose(velocity, round_trip_velocity, rtol=1e-8, atol=1e-6, err_msg=test_name)

    if well_defined:
        assert recovered_elements.semi_major_axis is not None
        assert recovered_elements.eccentricity is not None
        assert recovered_elements.inclination is not None
        assert recovered_elements.ascending_node is not None
        assert recovered_elements.argument_periapsis is not None
        assert recovered_elements.true_anomaly is not None

        decimal = 6 if "near_" in test_name else 8
        np.testing.assert_almost_equal(
            recovered_elements.semi_major_axis, a, decimal, err_msg=f"{test_name}: semi_major_axis"
        )
        np.testing.assert_almost_equal(
            recovered_elements.eccentricity, e, decimal, err_msg=f"{test_name}: eccentricity"
        )
        np.testing.assert_almost_equal(recovered_elements.inclination, i, decimal, err_msg=f"{test_name}: inclination")
        np.testing.assert_almost_equal(
            recovered_elements.ascending_node, ascending_node, decimal, err_msg=f"{test_name}: ascending_node"
        )
        np.testing.assert_almost_equal(
            recovered_elements.argument_periapsis,
            argument_periapsis,
            decimal,
            err_msg=f"{test_name}: argument_periapsis",
        )
        np.testing.assert_almost_equal(
            recovered_elements.true_anomaly, true_anomaly, decimal, err_msg=f"{test_name}: true_anomaly"
        )
    else:
        assert recovered_elements.semi_major_axis is not None
        assert recovered_elements.eccentricity is not None
        assert recovered_elements.inclination is not None

        np.testing.assert_almost_equal(
            recovered_elements.semi_major_axis, a, 8, err_msg=f"{test_name}: semi_major_axis"
        )
        np.testing.assert_almost_equal(recovered_elements.eccentricity, e, 8, err_msg=f"{test_name}: eccentricity")
        np.testing.assert_almost_equal(recovered_elements.inclination, i, 8, err_msg=f"{test_name}: inclination")


def test_zero_g():
    """
    With no gravity, an object should just move in a straight line at constant speed
    this checks that holds true over several propagation steps, not just one.
    """
    pos = np.array([1e5, 1e6, 1e2])
    vel = np.array([10.0, 20.0, 30.0])
    state = np.concatenate([pos, vel])

    dstate_dt = orbital_motion.point_mass_dynamics(np.array([0, 1]), state, 0.0)
    np.testing.assert_almost_equal(dstate_dt[:3], vel, 10)
    np.testing.assert_almost_equal(dstate_dt[3:], np.zeros(3), 10)

    times = np.linspace(0, 1000, 11)
    propagated = state
    for i in range(1, len(times)):
        propagated = orbital_motion.propagate_cartesian(0.0, propagated, times[i - 1], times[i])
        expected_position = pos + vel * times[i]
        np.testing.assert_allclose(propagated[:3], expected_position, rtol=1e-9)
        np.testing.assert_allclose(propagated[3:], vel, rtol=1e-9)


def test_gravity_acceleration():
    """
    Checks that gravity pulls with the right strength (inverse-square law) and in the right direction (toward the center).
    """
    pos = np.array([1e5, 1e6, 1e2])
    vel = np.array([10.0, 20.0, 30.0])
    state = np.concatenate([pos, vel])

    dstate_dt = orbital_motion.point_mass_dynamics(np.array([0, 1]), state, mu)
    accel = dstate_dt[3:]

    np.testing.assert_almost_equal(dstate_dt[:3], vel, 10)
    np.testing.assert_almost_equal(np.linalg.norm(accel), mu / np.linalg.norm(pos) ** 2, 10)

    pos_hat = pos / np.linalg.norm(pos)
    np.testing.assert_almost_equal(np.dot(accel, -pos_hat), np.linalg.norm(accel), 10)


def test_conservation_laws():
    """
    Checks that angular momentum and energy stay constant across several full orbits
     a short window wouldn't catch drift that only builds up over time.
    """
    pos = np.array([1e5, 1e6, 1e2])
    vel = np.array([10.0, 20.0, 30.0])
    state = np.concatenate([pos, vel])

    elements = orbital_motion.cartesian_to_orbital_elements(mu, pos, vel)
    assert elements.semi_major_axis is not None
    period = 2.0 * np.pi * np.sqrt(elements.semi_major_axis**3 / mu)

    times = np.linspace(0, 2 * period, 50)
    states = [state]
    for i in range(1, len(times)):
        states.append(orbital_motion.propagate_cartesian(mu, states[-1], times[i - 1], times[i]))
    states = np.array(states)

    h = np.cross(states[:, :3], states[:, 3:])
    energy = np.linalg.norm(states[:, 3:], axis=1) ** 2 / 2 - mu / np.linalg.norm(states[:, :3], axis=1)

    np.testing.assert_allclose(h[:, 0], h[0, 0], rtol=1e-10)
    np.testing.assert_allclose(h[:, 1], h[0, 1], rtol=1e-10)
    np.testing.assert_allclose(h[:, 2], h[0, 2], rtol=1e-10)
    np.testing.assert_allclose(np.linalg.norm(h, axis=1), np.linalg.norm(h[0, :]), rtol=1e-10)
    np.testing.assert_allclose(energy, energy[0])


def test_orbit_closure():
    """
    Checks that after propagating for exactly one full orbit, the object ends up back where it started
    the simplest possible sanity check on the propagator.
    """
    pos = np.array([1e5, 1e6, 1e2])
    vel = np.array([10.0, 20.0, 30.0])
    state = np.concatenate([pos, vel])

    elements = orbital_motion.cartesian_to_orbital_elements(mu, pos, vel)
    assert elements.semi_major_axis is not None
    period = 2.0 * np.pi * np.sqrt(elements.semi_major_axis**3 / mu)

    final_state = orbital_motion.propagate_cartesian(mu, state, 0.0, period)

    np.testing.assert_allclose(final_state[:3], pos, rtol=1e-3, atol=15.0)
    np.testing.assert_allclose(final_state[3:], vel, rtol=1e-3, atol=1e-2)


def test_circular_orbit_analytical():
    """
    For a circular orbit, there's an exact known formula for where the object should be at any time
    this checks the propagator's output against that formula directly,
    """
    r0 = 7e5
    omega = np.sqrt(mu / r0**3)
    pos = np.array([r0, 0.0, 0.0])
    vel = np.array([0.0, r0 * omega, 0.0])
    state = np.concatenate([pos, vel])

    period = 2 * np.pi / omega
    sample_times = np.linspace(0, period, 21)  # 20 sub-intervals across one period

    propagated = state
    last_time = 0.0
    for t in sample_times[1:]:
        propagated = orbital_motion.propagate_cartesian(mu, propagated, last_time, t)
        last_time = t

        expected_position = r0 * np.array([np.cos(omega * t), np.sin(omega * t), 0.0])
        expected_velocity = r0 * omega * np.array([-np.sin(omega * t), np.cos(omega * t), 0.0])

        np.testing.assert_allclose(propagated[:3], expected_position, rtol=1e-3, atol=250.0)
        np.testing.assert_allclose(propagated[3:], expected_velocity, rtol=1e-3, atol=0.05)
