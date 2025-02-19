# ISC License
#
# Copyright (c) 2016, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
# Copyright (c) 2025, Laboratory for Atmospheric and Space Physics, University of Colorado at Boulder
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.


import numpy as np


def form_dcm(primary_heading : np.ndarray, secondary_heading : np.ndarray) -> np.ndarray:
    """
    Form DCM of the target frame in the base frame (inertial most commonly):
        - use the primary heading as the x direction
        - optimal solution for secondary to be in y
        - z completes the orthonormal frame
    """
    primary_heading = np.array(primary_heading)
    secondary_heading = np.array(secondary_heading)

    x_direction = primary_heading / np.linalg.norm(primary_heading)
    secondary_direction = secondary_heading / np.linalg.norm(secondary_heading)
    z_direction = np.cross(x_direction, secondary_direction)
    z_direction /= np.linalg.norm(z_direction)
    y_direction = np.cross(z_direction, x_direction)

    base_to_target = np.zeros([3, 3])
    base_to_target[0, :] = x_direction
    base_to_target[1, :] = y_direction
    base_to_target[2, :] = z_direction

    return base_to_target


def camera_correction_rotation() -> np.ndarray:
    """
    Correct the frame axes to represent the camera pointing direction:
        - boresight along +z
        - vertical pixels moving down along +y
        - horizontal pixels moving right along +x
    """

    return np.array([[0, 0, 1], [-1, 0, 0], [0, -1, 0]])


def body_to_inertial_for_pointing(primary_heading : np.ndarray, secondary_heading : np.ndarray, camera_to_body_dcm : np.ndarray) -> np.ndarray:
    """
    Create the BN dcm in order to point to the primary and secondary headings
    """
    primary_heading = primary_heading / np.linalg.norm(primary_heading)
    secondary_heading = secondary_heading / np.linalg.norm(secondary_heading)

    BC = camera_to_body_dcm.transpose()
    CP = camera_correction_rotation().transpose()
    TN = form_dcm(primary_heading, secondary_heading)
    return np.dot(BC, np.dot(CP, TN))


def dcm_to_quaternion(dcm : np.ndarray) -> np.ndarray:
    """
    dcm_to_quaternion
        quaternion = dcm_to_quaternion(dcm) translates the 3x3 direction cosine matrix
        dcm into the corresponding 4x1 euler parameter vector quaternion,
        where the first component of quaternion is the non-dimensional
        Euler parameter Beta_0 >= 0. Transformation is done
        using the Stanley method.
    """
    tr = np.trace(dcm)
    quaternion2 = np.array([(1 + tr) / 4, (1 + 2 * dcm[0, 0] - tr) / 4, (1 + 2 * dcm[1, 1] - tr) / 4, (1 + 2 * dcm[2, 2] - tr) / 4])
    case = np.argmax(quaternion2)
    quaternion = quaternion2
    if case == 0:
        quaternion[0] = np.sqrt(quaternion2[0])
        quaternion[1] = (dcm[1, 2] - dcm[2, 1]) / 4 / quaternion[0]
        quaternion[2] = (dcm[2, 0] - dcm[0, 2]) / 4 / quaternion[0]
        quaternion[3] = (dcm[0, 1] - dcm[1, 0]) / 4 / quaternion[0]
    elif case == 1:
        quaternion[1] = np.sqrt(quaternion2[1])
        quaternion[0] = (dcm[1, 2] - dcm[2, 1]) / 4 / quaternion[1]
        if quaternion[0] < 0:
            quaternion[1] = -quaternion[1]
            quaternion[0] = -quaternion[0]
        quaternion[2] = (dcm[0, 1] + dcm[1, 0]) / 4 / quaternion[1]
        quaternion[3] = (dcm[2, 0] + dcm[0, 2]) / 4 / quaternion[1]
    elif case == 2:
        quaternion[2] = np.sqrt(quaternion2[2])
        quaternion[0] = (dcm[2, 0] - dcm[0, 2]) / 4 / quaternion[2]
        if quaternion[0] < 0:
            quaternion[2] = -quaternion[2]
            quaternion[0] = -quaternion[0]
        quaternion[1] = (dcm[0, 1] + dcm[1, 0]) / 4 / quaternion[2]
        quaternion[3] = (dcm[1, 2] + dcm[2, 1]) / 4 / quaternion[2]
    elif case == 3:
        quaternion[3] = np.sqrt(quaternion2[3])
        quaternion[0] = (dcm[0, 1] - dcm[1, 0]) / 4 / quaternion[3]
        if quaternion[0] < 0:
            quaternion[3] = -quaternion[3]
            quaternion[0] = -quaternion[0]
        quaternion[1] = (dcm[2, 0] + dcm[0, 2]) / 4 / quaternion[3]
        quaternion[2] = (dcm[1, 2] + dcm[2, 1]) / 4 / quaternion[3]
    return quaternion


def dcm_to_euler321(dcm : np.ndarray) -> np.ndarray:
    """
    dcm_to_euler321

    	euler321 = dcm_to_euler321(dcm) translates the 3x3 direction cosine matrix
    	dcm into the corresponding (3-2-1) euler angle set.
    """

    euler0 = np.arctan2(dcm[0, 1], dcm[0, 0])
    euler1 = np.arcsin(-dcm[0, 2])
    euler2 = np.arctan2(dcm[1, 2], dcm[2, 2])
    euler = np.array([euler0, euler1, euler2])
    return euler


def dcm_to_mrp(dcm : np.ndarray) -> np.ndarray:
    """
    dcm_to_mrp

    	mrp = dcm_to_mrp(dcm) translates the 3x3 direction cosine matrix
    	dcm into the corresponding 3x1 mrp vector mrp where the
    	mrp vector is chosen such that :math:`|mrp| <= 1`.
    """

    quaternion = dcm_to_quaternion(dcm)
    mrp = np.array([quaternion[1] / (1 + quaternion[0]), quaternion[2] / (1 + quaternion[0]), quaternion[3] / (1 + quaternion[0])])
    return mrp


def dcm_to_principalRotation(dcm : np.ndarray) -> np.ndarray:
    """
    dcm_to_principalRotation

    	prv = dcm_to_principalRotation(dcm) translates the 3x3 direction cosine matrix
    	dcm into the corresponding 3x1 principal rotation vector prv,
    	where the first component of prv is the principal rotation angle
    	phi (0<= phi <= Pi)
    """

    cp = (np.trace(dcm) - 1) / 2
    p = np.arccos(cp)
    sp = p / 2. / np.sin(p)
    prv = np.array([(dcm[1, 2] - dcm[2, 1]) * sp, (dcm[2, 0] - dcm[0, 2]) * sp, (dcm[0, 1] - dcm[1, 0]) * sp])
    return prv


def mrp_to_dcm(mrp : np.ndarray) -> np.ndarray:
    """
    mrp_to_dcm

    	dcm = mrp_to_dcm(mrp) returns the direction cosine
    	matrix in terms of the 3x1 mrp vector mrp.
    """
    S = 1 - np.linalg.norm(mrp) ** 2
    d = (1 + np.linalg.norm(mrp) ** 2) * (1 + np.linalg.norm(mrp) ** 2)
    dcm = np.zeros((3, 3))
    dcm[0, 0] = 4 * (2 * mrp[0] * mrp[0] - np.linalg.norm(mrp) ** 2) + S * S
    dcm[0, 1] = 8 * mrp[0] * mrp[1] + 4 * mrp[2] * S
    dcm[0, 2] = 8 * mrp[0] * mrp[2] - 4 * mrp[1] * S
    dcm[1, 0] = 8 * mrp[1] * mrp[0] - 4 * mrp[2] * S
    dcm[1, 1] = 4 * (2 * mrp[1] * mrp[1] - np.linalg.norm(mrp) ** 2) + S * S
    dcm[1, 2] = 8 * mrp[1] * mrp[2] + 4 * mrp[0] * S
    dcm[2, 0] = 8 * mrp[2] * mrp[0] + 4 * mrp[1] * S
    dcm[2, 1] = 8 * mrp[2] * mrp[1] - 4 * mrp[0] * S
    dcm[2, 2] = 4 * (2 * mrp[2] * mrp[2] - np.linalg.norm(mrp) ** 2) + S * S
    return dcm / d


def mrp_to_quaternion(mrp : np.ndarray) -> np.ndarray:
    """
    mrp_to_quaternion(mrp)

    	quaternion = mrp_to_quaternion(mrp) translates the mrp vector
    	into the euler parameter vector quaternion.
    """
    ps = 1 + np.linalg.norm(mrp) * np.linalg.norm(mrp)
    quaternion = np.array([(1 - np.linalg.norm(mrp) * np.linalg.norm(mrp)) / ps, 2 * mrp[0] / ps, 2 * mrp[1] / ps, 2 * mrp[2] / ps])
    return quaternion


def mrp_to_euler321(mrp : np.ndarray) -> np.ndarray:
    """
    mrp_to_euler321(mrp)

    	euler321 = mrp_to_euler321(mrp) translates the mrp
    	 vector into the (3-2-1) euler angle vector euler321.
    """

    return quaternion_to_euler321(mrp_to_quaternion(mrp))


def mrp_to_principalRotation(mrp : np.ndarray) -> np.ndarray:
    """
    mrp_to_principalRotation(mrp)

    	prv = mrp_to_principalRotation(mrp) translates the mrp vector
    	into the principal rotation vector prv.
    """
    p = 4 * np.arctan(np.linalg.norm(mrp))
    return np.array([mrp[0], mrp[1], mrp[2]])/ np.linalg.norm(mrp) * p


def mrp_switch(mrp : np.ndarray, threshold : float) -> np.ndarray:
    """
    mrp_switch

    	S = mrp_switch(mrp,threshold) checks to see if norm(mrp) is larger than threshold.
    	If yes, then the mrp vector mrp is mapped to its shadow set.
    """

    if np.dot(mrp, mrp) > threshold ** 2:
        s = -mrp / np.dot(mrp, mrp)
    else:
        s = mrp

    return s


def principalRotation_to_dcm(prv: np.ndarray) -> np.ndarray:
    """
    principalRotation_to_dcm

    	dcm = principalRotation_to_dcm(prv) returns the direction cosine
    	matrix in terms of the 3x1 principal rotation vector
    	prv.
    """
    if np.linalg.norm(prv) == 0.0:
        prv1 = prv[0]
        prv2 = prv[1]
        prv3 = prv[2]
    else:
        prv1 = prv[0] / np.linalg.norm(prv)
        prv2 = prv[1] / np.linalg.norm(prv)
        prv3 = prv[2] / np.linalg.norm(prv)
    cp = np.cos(np.linalg.norm(prv))
    sp = np.sin(np.linalg.norm(prv))
    d1 = 1 - cp
    dcm = np.zeros((3, 3))
    dcm[0, 0] = prv1 * prv1 * d1 + cp
    dcm[0, 1] = prv1 * prv2 * d1 + prv3 * sp
    dcm[0, 2] = prv1 * prv3 * d1 - prv2 * sp
    dcm[1, 0] = prv2 * prv1 * d1 - prv3 * sp
    dcm[1, 1] = prv2 * prv2 * d1 + cp
    dcm[1, 2] = prv2 * prv3 * d1 + prv1 * sp
    dcm[2, 0] = prv3 * prv1 * d1 + prv2 * sp
    dcm[2, 1] = prv3 * prv2 * d1 - prv1 * sp
    dcm[2, 2] = prv3 * prv3 * d1 + cp
    return dcm


def principalRotation_to_quaternion(prv : np.ndarray) -> np.ndarray:
    """"
    principalRotation_to_quaternion(prv)

    	quaternion = principalRotation_to_quaternion(prv) translates the principal rotation vector prv
    	into the euler parameter vector quaternion.
    """

    return dcm_to_quaternion(principalRotation_to_dcm(prv))


def principalRotation_to_euler321(prv : np.ndarray) -> np.ndarray:
    """
    principalRotation_to_euler321(prv)

    	euler321 = principalRotation_to_euler321(prv) translates the principal rotation
    	vector prv into the (3-2-1) euler angle vector euler321.
    """

    return quaternion_to_euler321(principalRotation_to_quaternion(prv))


def principalRotation_to_mrp(prv : np.ndarray) -> np.ndarray:
    """
     principalRotation_to_mrp(prv)

    	mrp = principalRotation_to_mrp(prv) translates the principal rotation vector prv
    	into the mrp vector.
    """

    return dcm_to_mrp(principalRotation_to_dcm(prv))


def quaternion_to_dcm(quaternion : np.ndarray) -> np.ndarray:
    """
	quaternion_to_dcm

        dcm = quaternion_to_dcm(quaternion) returns the direction np.cosine
        matrix in terms of the 4x1 euler parameter vector
        quaternion.  The first element is the non-dimensional euler
        parameter, while the remain three elements form
        the euler parameter vector.
	"""
    dcm = np.zeros([3, 3])
    dcm[0, 0] = quaternion[0] ** 2 + quaternion[1] ** 2 - quaternion[2] ** 2 - quaternion[3] ** 2
    dcm[0, 1] = 2 * (quaternion[1] * quaternion[2] + quaternion[0] * quaternion[3])
    dcm[0, 2] = 2 * (quaternion[1] * quaternion[3] - quaternion[0] * quaternion[2])
    dcm[1, 0] = 2 * (quaternion[1] * quaternion[2] - quaternion[0] * quaternion[3])
    dcm[1, 1] = quaternion[0] ** 2 - quaternion[1] ** 2 + quaternion[2] ** 2 - quaternion[3] ** 2
    dcm[1, 2] = 2 * (quaternion[2] * quaternion[3] + quaternion[0] * quaternion[1])
    dcm[2, 0] = 2 * (quaternion[1] * quaternion[3] + quaternion[0] * quaternion[2])
    dcm[2, 1] = 2 * (quaternion[2] * quaternion[3] - quaternion[0] * quaternion[1])
    dcm[2, 2] = quaternion[0] ** 2 - quaternion[1] ** 2 - quaternion[2] ** 2 + quaternion[3] ** 2
    return dcm


def quaternion_to_euler321(quaternion : np.ndarray) -> np.ndarray:
    """
    quaternion_to_euler321

    	euler321 = quaternion_to_euler321(quaternion) translates the euler parameter vector
    	quaternion into the corresponding (3-2-1) euler angle set.
    """

    e1 = np.arctan2(2 * (quaternion[1] * quaternion[2] + quaternion[0] * quaternion[3]),
                    quaternion[0] ** 2 + quaternion[1] ** 2 - quaternion[2] ** 2 - quaternion[3] ** 2)
    e2 = np.arcsin(-2 * (quaternion[1] * quaternion[3] - quaternion[0] * quaternion[2]))
    e3 = np.arctan2(2 * (quaternion[2] * quaternion[3] + quaternion[0] * quaternion[1]),
                    quaternion[0] ** 2 - quaternion[1] ** 2 - quaternion[2] ** 2 + quaternion[3] ** 2)

    return np.array([e1, e2, e3])


def quaternion_to_mrp(quaternion : np.ndarray) -> np.ndarray:
    """
    quaternion_to_mrp(quaternion)
        mrp = quaternion_to_mrp(quaternion) translates the euler parameter vector quaternion
        into the mrp vector.
    """

    if quaternion[0] < 0:
        quaternion = -quaternion

    return np.array([quaternion[1], quaternion[2], quaternion[3]])/ (1 + quaternion[0])


def quaternion_to_principalRotation(quaternion : np.ndarray) -> np.ndarray:
    """
    quaternion_to_principalRotation(quaternion)

    	prv = quaternion_to_principalRotation(quaternion) translates the euler parameter vector quaternion
    	into the principal rotation vector prv.
    """

    p = 2 * np.arccos(quaternion[0])
    sp = np.sin(p / 2)

    return np.array([quaternion[1], quaternion[2], quaternion[3]]) / sp * p


def euler1(angle :float) -> np.ndarray:
    """
	EULER1 	Elementary rotation matrix
	Returns the elementary rotation matrix about the first body axis.
	"""
    m = np.identity(3)
    m[1, 1] = np.cos(angle)
    m[1, 2] = np.sin(angle)
    m[2, 1] = -m[1, 2]
    m[2, 2] = m[1, 1]

    return m


def euler2(angle :float) -> np.ndarray:
    """
	EULER2 	Elementary rotation matrix
	Returns the elementary rotation matrix about the
	second body axis.
	"""
    m = np.identity(3)
    m[0, 0] = np.cos(angle)
    m[0, 2] = -np.sin(angle)
    m[2, 0] = -m[0, 2]
    m[2, 2] = m[0, 0]

    return m


def euler3(angle :float) -> np.ndarray:
    """
	EULER3 	Elementary rotation matrix
	Returns the elementary rotation matrix about the
	third body axis.
	"""
    m = np.identity(3)
    m[0, 0] = np.cos(angle)
    m[0, 1] = np.sin(angle)
    m[1, 0] = -m[0, 1]
    m[1, 1] = m[0, 0]

    return m


def euler321_to_dcm(euler321 :np.ndarray) -> np.ndarray:
    """
    euler321_to_dcm
    	dcm = euler321_to_dcm(euler321) returns the direction cosine
    	matrix in terms of the 3-2-1 euler angles.
    	Input Q must be a 3x1 vector of euler angles.
    """

    dcm = np.identity(3)
    dcm[0, 0] = np.cos(euler321[1]) * np.cos(euler321[0])
    dcm[0, 1] = np.cos(euler321[1]) * np.sin(euler321[0])
    dcm[0, 2] = -np.sin(euler321[1])
    dcm[1, 0] =  np.sin(euler321[2]) * np.sin(euler321[1]) * np.cos(euler321[0]) - np.cos(euler321[2]) * np.sin(euler321[0])
    dcm[1, 1] =  np.sin(euler321[2]) * np.sin(euler321[1]) * np.sin(euler321[0]) + np.cos(euler321[2]) * np.cos(euler321[0])
    dcm[1, 2] =  np.sin(euler321[2]) * np.cos(euler321[1])
    dcm[2, 0] = np.cos(euler321[2]) * np.sin(euler321[1]) * np.cos(euler321[0]) +  np.sin(euler321[2]) * np.sin(euler321[0])
    dcm[2, 1] = np.cos(euler321[2]) * np.sin(euler321[1]) * np.sin(euler321[0]) -  np.sin(euler321[2]) * np.cos(euler321[0])
    dcm[2, 2] = np.cos(euler321[2]) * np.cos(euler321[1])

    return dcm


def euler321_to_quaternion(euler321 : np.ndarray) -> np.ndarray:
    """
    euler321_to_quaternion(euler321)
        quaternion = euler321_to_quaternion(euler321) translates the 321 euler angle
        vector E into the euler parameter vector quaternion.
    """

    q0 = (np.cos(euler321[0] / 2) * np.cos(euler321[1] / 2) * np.cos(euler321[2] / 2) + np.sin(euler321[0] / 2) *
          np.sin(euler321[1] / 2) * np.sin(euler321[2] / 2))
    q1 = (np.cos(euler321[0] / 2) * np.cos(euler321[1] / 2) * np.sin(euler321[2] / 2) - np.sin(euler321[0] / 2) *
          np.sin(euler321[1] / 2) * np.cos(euler321[2] / 2))
    q2 = (np.cos(euler321[0] / 2) * np.sin(euler321[1] / 2) * np.cos(euler321[2] / 2) + np.sin(euler321[0] / 2) *
          np.cos(euler321[1] / 2) * np.sin(euler321[2] / 2))
    q3 = (np.sin(euler321[0] / 2) * np.cos(euler321[1] / 2) * np.cos(euler321[2] / 2) - np.cos(euler321[0] / 2) *
          np.sin(euler321[1] / 2) * np.sin(euler321[2] / 2))

    return np.array([q0, q1, q2, q3])


def euler321_to_mrp(euler321 : np.ndarray) -> np.ndarray:
    """
    euler321_to_mrp(euler321)
        mrp = euler321_to_mrp(euler321) translates the (3-2-1) euler
        angle vector euler321 into the mrp vector.
    """

    return quaternion_to_mrp(euler321_to_quaternion(euler321))


def euler321_to_principalRotation(euler321 : np.ndarray) -> np.ndarray:
    """
     euler321_to_principalRotation(euler321)

    	prv = euler321_to_principalRotation(euler321) translates the (3-2-1) euler
    	angle vector euler321 into the principal rotation vector prv.
    """

    return quaternion_to_principalRotation(euler321_to_quaternion(euler321))
