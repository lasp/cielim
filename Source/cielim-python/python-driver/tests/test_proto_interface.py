import os
import sys

sys.path.insert(0, os.path.dirname(__file__) + "/../astrodynamics/")
sys.path.insert(0, os.path.dirname(__file__) + "/../")
from proto_interface import ProtoInterface
from orbital_motion import *
from rigid_body_kinematics import *
import cielimMessage_pb2

import numpy as np


def scene_setup():
    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "earth"
    [body.position.append(item) for item in [1, 2, 3]]
    [body.velocity.append(item) for item in [0, 0, -1]]
    [body.attitude.append(item) for item in [4, 5, 6]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [35786 * 10 ** 3, 0, 0]]
    [protobuf_message.spacecraft.velocity.append(item) for item in [0, 3.07 * 10 ** 3, 0]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [1, 1, 1]]

    return protobuf_message


def test_setters_getters():
    interface = ProtoInterface()
    message = scene_setup()
    interface.set_existing_message(message)
    returned = interface.return_message()

    np.testing.assert_equal(returned.celestialBodies[0].position, message.celestialBodies[0].position)
    np.testing.assert_equal(returned.celestialBodies[0].attitude, message.celestialBodies[0].attitude)

    interface.set_pointing_target("testing")
    np.testing.assert_equal(interface.target_name, "testing")

    interface.set_gravitational_parameter(3.2 * 1E-10)
    np.testing.assert_equal(interface.gravitational_parameter, 3.2 * 1E-10)

    orbital_elements = ClassicElements()
    orbital_elements.e = 0
    orbital_elements.a = 35786 * 10 ** 3
    orbital_elements.i = np.pi / 6
    orbital_elements.Omega = np.pi / 12
    orbital_elements.omega = np.pi / 10
    orbital_elements.f = np.pi
    mu = 3.986 * 10 ** 14
    interface.set_initial_orbital_elements(orbital_elements, mu)
    returned = interface.return_message()

    r = np.array(returned.spacecraft.position)
    v = np.array(returned.spacecraft.velocity)
    h = np.cross(r, v)
    np.testing.assert_equal(np.dot(h / np.linalg.norm(h), [0., 0., 1.]), np.cos(orbital_elements.i))
    np.testing.assert_equal(np.linalg.norm(v), np.sqrt(mu / orbital_elements.a))

    mrp = [1, 2, 3]
    interface.set_initial_mrp(mrp)
    returned = interface.return_message()
    np.testing.assert_equal(returned.spacecraft.attitude, mrp)

    angle = np.pi / 2
    prv = angle * np.array([1, 0, 0])
    interface.set_initial_prv(prv)
    returned = interface.return_message()
    np.testing.assert_almost_equal(returned.spacecraft.attitude[0], np.tan(angle / 4), decimal=15)

    angle = np.pi / 4
    dcm = np.array([[np.cos(angle), np.sin(angle), 0.], [-np.sin(angle), np.cos(angle), 0.], [0., 0., 1.]])
    interface.set_initial_dcm(dcm)
    returned = interface.return_message()
    np.testing.assert_almost_equal(returned.spacecraft.attitude[2], np.tan(angle / 4), decimal=15)

    angle = np.pi / 6
    euler321 = [0, angle, 0]
    interface.set_initial_euler321(euler321)
    returned = interface.return_message()
    np.testing.assert_almost_equal(returned.spacecraft.attitude[1], np.tan(angle / 4), decimal=15)

    offset = [0.1, 0, 0]
    interface.set_euler321_pointing_offset(offset)
    returned = interface.return_message()
    dcm1 = euler321_to_dcm(euler321)
    dcm2 = euler321_to_dcm(offset)
    np.testing.assert_almost_equal(returned.spacecraft.attitude, dcm_to_mrp(np.dot(dcm2, dcm1)), decimal=15)


def test_camera_correction_rotation():
    interface = ProtoInterface()
    interface.set_existing_message(scene_setup())
    interface.look_at_target("earth")
    returned = interface.return_message()
    BN = mrp_to_dcm(list(returned.spacecraft.attitude))

    CB = mrp_to_dcm(list(returned.camera.bodyFrameToCameraMrp))
    CN = np.array([[0., 0., -1.], [1., 0., 0.], [0., -1, 0.]])

    # TODO confirm that CN.T is correct and not CN (or that the method is correct)
    np.testing.assert_allclose(np.dot(CB, BN), CN.T, rtol=1E-6, atol=1E-3)

    return


def test_propagation():
    interface = ProtoInterface()
    interface.set_existing_message(scene_setup())
    mu = 3.986 * 10 ** 14
    initial_position = list(interface.return_message().spacecraft.position)
    initial_velocity = list(interface.return_message().spacecraft.velocity)

    positions = [initial_position]
    velocities = [initial_velocity]
    step = 10
    for i in range(int(600 * 12 / step)):
        interface.propagate(step, mu)  # quarter turn in geo around the earth is 6h
        positions.append(list(interface.return_message().spacecraft.position))
        velocities.append(list(interface.return_message().spacecraft.velocity))

    positions = np.array(positions)
    velocities = np.array(velocities)
    h = np.zeros(np.shape(positions))
    energy = np.zeros(len(positions[:, 0]))
    for i in range(len(positions[:, 0])):
        h[i, :] = np.cross(positions[i, :], velocities[i, :])
        energy[i] = np.linalg.norm(velocities[i, :]) ** 2 / 2 - mu / np.linalg.norm(positions[i, :])

    np.testing.assert_almost_equal(h[-1, :] / np.linalg.norm(h[-1, :]), [0., 0., 1.])
    np.testing.assert_allclose(h[:, 0], h[0, 0], rtol=1E-10)
    np.testing.assert_allclose(h[:, 1], h[0, 1], rtol=1E-10)
    np.testing.assert_allclose(h[:, 2], h[0, 2], rtol=1E-10)
    np.testing.assert_allclose(energy, energy[0])
