from pathlib import Path

import numpy as np
import pytest

import cielim
from cielim import orbital_motion, scene
from cielim import rigid_body_kinematics as rbk


def scene_setup():
    protobuf_message = cielim.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "earth"
    [body.position.append(item) for item in [1, 2, 3]]
    [body.velocity.append(item) for item in [0, 0, -1]]
    [body.attitude.append(item) for item in [4, 5, 6]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [35786 * 10**3, 0, 0]]
    [protobuf_message.spacecraft.velocity.append(item) for item in [0, 3.07 * 10**3, 0]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [1, 1, 1]]

    return protobuf_message


def test_setters_getters():
    scene_frame = scene.Scene()
    message = scene_setup()
    scene_frame.set_existing_message(message)
    returned = scene_frame.get_scene()

    np.testing.assert_equal(returned.celestialBodies[0].position, message.celestialBodies[0].position)
    np.testing.assert_equal(returned.celestialBodies[0].attitude, message.celestialBodies[0].attitude)

    scene_frame.set_pointing_target("testing")
    np.testing.assert_equal(scene_frame.target_name, "testing")

    scene_frame.set_gravitational_parameter(3.2 * 1e-10)
    np.testing.assert_equal(scene_frame.gravitational_parameter, 3.2 * 1e-10)

    orbital_elements = orbital_motion.ClassicOrbitalElements()
    orbital_elements.eccentricity = 0
    orbital_elements.semi_major_axis = 35786 * 10**3
    orbital_elements.inclination = np.pi / 6
    orbital_elements.ascending_node = np.pi / 12
    orbital_elements.argument_periapsis = np.pi / 10
    orbital_elements.true_anomaly = np.pi
    mu = 3.986 * 10**14
    scene_frame.set_orbital_elements(orbital_elements, mu)
    returned = scene_frame.get_scene()

    r = np.array(returned.spacecraft.position)
    v = np.array(returned.spacecraft.velocity)
    h = np.cross(r, v)
    np.testing.assert_equal(np.dot(h / np.linalg.norm(h), [0.0, 0.0, 1.0]), np.cos(orbital_elements.inclination))
    np.testing.assert_equal(np.linalg.norm(v), np.sqrt(mu / orbital_elements.semi_major_axis))

    mrp = [1, 2, 3]
    scene_frame.set_mrp(mrp)
    returned = scene_frame.get_scene()
    np.testing.assert_equal(returned.spacecraft.attitude, mrp)

    angle = np.pi / 2
    prv = angle * np.array([1, 0, 0])
    scene_frame.set_prv(prv)
    returned = scene_frame.get_scene()
    np.testing.assert_almost_equal(returned.spacecraft.attitude[0], np.tan(angle / 4), decimal=15)

    angle = np.pi / 4
    dcm = np.array([[np.cos(angle), np.sin(angle), 0.0], [-np.sin(angle), np.cos(angle), 0.0], [0.0, 0.0, 1.0]])
    scene_frame.set_dcm(dcm)
    returned = scene_frame.get_scene()
    np.testing.assert_almost_equal(returned.spacecraft.attitude[2], np.tan(angle / 4), decimal=15)

    angle = np.pi / 6
    euler321 = [0, angle, 0]
    scene_frame.set_euler321(euler321)
    returned = scene_frame.get_scene()
    np.testing.assert_almost_equal(returned.spacecraft.attitude[1], np.tan(angle / 4), decimal=15)

    offset = [0.1, 0, 0]
    scene_frame.set_euler321_pointing_offset(offset)
    returned = scene_frame.get_scene()
    dcm1 = rbk.euler321_to_dcm(euler321)
    dcm2 = rbk.euler321_to_dcm(offset)
    np.testing.assert_almost_equal(returned.spacecraft.attitude, rbk.dcm_to_mrp(np.dot(dcm2, dcm1)), decimal=15)


def test_camera_correction_rotation():
    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup())
    scene_frame.look_at_target("earth")
    returned = scene_frame.get_scene()
    BN = rbk.mrp_to_dcm(list(returned.spacecraft.attitude))

    CB = rbk.mrp_to_dcm(list(returned.camera.bodyFrameToCameraMrp))
    CN = np.array([[0.0, 0.0, -1.0], [1.0, 0.0, 0.0], [0.0, -1, 0.0]])

    # TODO confirm that CN.T is correct and not CN (or that the method is correct)
    np.testing.assert_allclose(np.dot(CB, BN), CN.T, rtol=1e-6, atol=1e-3)

    return


def test_propagation():
    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup())
    mu = 3.986 * 10**14
    initial_position = list(scene_frame.get_scene().spacecraft.position)
    initial_velocity = list(scene_frame.get_scene().spacecraft.velocity)

    positions = [initial_position]
    velocities = [initial_velocity]
    step = 10
    for i in range(int(600 * 12 / step)):
        scene_frame.propagate(step, mu)  # quarter turn in geo around the earth is 6h
        positions.append(list(scene_frame.get_scene().spacecraft.position))
        velocities.append(list(scene_frame.get_scene().spacecraft.velocity))

    positions = np.array(positions)
    velocities = np.array(velocities)
    h = np.zeros(np.shape(positions))
    energy = np.zeros(len(positions[:, 0]))
    for i in range(len(positions[:, 0])):
        h[i, :] = np.cross(positions[i, :], velocities[i, :])
        energy[i] = np.linalg.norm(velocities[i, :]) ** 2 / 2 - mu / np.linalg.norm(positions[i, :])

    np.testing.assert_almost_equal(h[-1, :] / np.linalg.norm(h[-1, :]), [0.0, 0.0, 1.0])
    np.testing.assert_allclose(h[:, 0], h[0, 0], rtol=1e-10)
    np.testing.assert_allclose(h[:, 1], h[0, 1], rtol=1e-10)
    np.testing.assert_allclose(h[:, 2], h[0, 2], rtol=1e-10)
    np.testing.assert_allclose(energy, energy[0])


def test_qe_curve_fit():
    scene_frame = scene.Scene()
    scene_frame.set_existing_message(scene_setup())
    qe_file_path = Path(__file__).resolve().parent.parent.parent / "support-data/deimos-spice/qe-mod-5.csv"
    if not qe_file_path.exists():
        pytest.skip(f"Missing data: {qe_file_path}")
    solid_angle = np.pi * 0.005**2 / (0.16**2)  # steradians
    pixel_area = (0.022528 * 0.016896) / (4096 * 3072)  # m^2
    scene_frame.set_qe_curve_fit(str(qe_file_path), solid_angle, pixel_area)

    returned = scene_frame.get_scene()
    fit_wv1 = returned.renderParameters.wavelength1
    fit_wv2 = returned.renderParameters.wavelength2
    fit_wv3 = returned.renderParameters.wavelength3
    np.testing.assert_almost_equal(fit_wv2, (fit_wv1 + fit_wv3) / 2)
    np.testing.assert_array_less(fit_wv1, fit_wv2)
    np.testing.assert_array_less(fit_wv2, fit_wv3)
    np.testing.assert_allclose(fit_wv1, 350, atol=50)
    np.testing.assert_allclose(fit_wv2, 650, atol=50)
    np.testing.assert_allclose(fit_wv3, 950, atol=50)
    fit_redvalue1 = returned.camera.sensorModel.qeCurve.redValue1
    fit_redvalue2 = returned.camera.sensorModel.qeCurve.redValue2
    fit_redvalue3 = returned.camera.sensorModel.qeCurve.redValue3
    np.testing.assert_array_less(fit_redvalue1, fit_redvalue2)
    np.testing.assert_array_less(fit_redvalue3, fit_redvalue2)
    np.testing.assert_allclose(fit_redvalue1, 0.3, atol=0.1)
    np.testing.assert_allclose(fit_redvalue2, 0.9, atol=0.1)
    np.testing.assert_allclose(fit_redvalue3, 0.2, atol=0.1)
