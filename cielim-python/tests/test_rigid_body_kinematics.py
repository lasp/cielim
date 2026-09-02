import numpy as np

from cielim.utils import rigid_body_kinematics as rbk


def test_dcm():
    camera_dcm = rbk.camera_correction_rotation()
    np.testing.assert_almost_equal(np.linalg.det(camera_dcm), 1, 5)

    primary_heading = np.array([1, 1, 0])
    secondary_heading = np.array([0, 1, 0])
    target_dcm = rbk.form_dcm(primary_heading, secondary_heading)
    np.testing.assert_almost_equal(np.linalg.det(target_dcm), 1, 5)
    np.testing.assert_almost_equal(target_dcm[0, :], primary_heading / np.linalg.norm(primary_heading), 5)
    np.testing.assert_array_less(np.arccos(np.dot(target_dcm[1, :], secondary_heading)), np.pi / 2)

    composed_dcm = rbk.body_to_inertial_for_pointing(primary_heading, secondary_heading, camera_dcm)
    np.testing.assert_almost_equal(np.linalg.det(composed_dcm), 1, 5)

    quaternion = rbk.dcm_to_quaternion(target_dcm)
    principalRotation = rbk.dcm_to_principalRotation(target_dcm)
    mrp = rbk.dcm_to_mrp(target_dcm)
    euler = rbk.dcm_to_euler321(target_dcm)
    np.testing.assert_almost_equal(np.arccos(quaternion[0]) * 2, np.pi / 4, 5)
    np.testing.assert_almost_equal(np.linalg.norm(principalRotation), np.pi / 4, 5)
    np.testing.assert_almost_equal(np.arctan(np.linalg.norm(mrp)) * 4, np.pi / 4, 5)
    np.testing.assert_almost_equal(euler[0], np.pi / 4, 5)
    np.testing.assert_almost_equal(
        np.sqrt(quaternion[0] ** 2 + quaternion[1] ** 2 + quaternion[2] ** 2 + quaternion[3] ** 2), 1, 5
    )


def test_transformations():
    primary_heading = np.array([1, 1, 0])
    secondary_heading = np.array([0, 1, 0])
    composed_dcm = rbk.body_to_inertial_for_pointing(primary_heading, secondary_heading, np.eye(3))

    quaternion = rbk.dcm_to_quaternion(composed_dcm)
    principalRotation = rbk.dcm_to_principalRotation(composed_dcm)
    mrp = rbk.dcm_to_mrp(composed_dcm)
    euler = rbk.dcm_to_euler321(composed_dcm)

    np.testing.assert_almost_equal(rbk.quaternion_to_dcm(quaternion), composed_dcm, 5)
    np.testing.assert_almost_equal(rbk.principalRotation_to_dcm(principalRotation), composed_dcm, 5)
    np.testing.assert_almost_equal(rbk.mrp_to_dcm(mrp), composed_dcm, 5)
    np.testing.assert_almost_equal(rbk.euler321_to_dcm(euler), composed_dcm, 5)

    np.testing.assert_almost_equal(rbk.quaternion_to_mrp(quaternion), mrp, 5)
    np.testing.assert_almost_equal(rbk.principalRotation_to_mrp(principalRotation), mrp, 5)
    np.testing.assert_almost_equal(rbk.euler321_to_mrp(euler), mrp, 5)

    np.testing.assert_almost_equal(rbk.mrp_to_quaternion(mrp), quaternion, 5)
    np.testing.assert_almost_equal(rbk.principalRotation_to_quaternion(principalRotation), quaternion, 5)
    np.testing.assert_almost_equal(rbk.euler321_to_quaternion(euler), quaternion, 5)

    np.testing.assert_almost_equal(rbk.mrp_to_euler321(mrp), euler, 5)
    np.testing.assert_almost_equal(rbk.principalRotation_to_euler321(principalRotation), euler, 5)
    np.testing.assert_almost_equal(rbk.quaternion_to_euler321(quaternion), euler, 5)

    np.testing.assert_almost_equal(rbk.mrp_to_principalRotation(mrp), principalRotation, 5)
    np.testing.assert_almost_equal(rbk.euler321_to_principalRotation(euler), principalRotation, 5)
    np.testing.assert_almost_equal(rbk.quaternion_to_principalRotation(quaternion), principalRotation, 5)
