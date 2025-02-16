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


import math

import numpy as np


def form_dcm(primary_heading, secondary_heading):
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


def camera_correction_rotation():
    """
    Correct the frame axes to represent the camera pointing direction:
        - boresight along +z
        - vertical pixels moving down along +y
        - horizontal pixels moving right along +x
    """

    return np.array([[0, 0, 1], [-1, 0, 0], [0, -1, 0]])


def body_to_inertial_for_pointing(primary_heading, secondary_heading, camera_to_body_dcm):
    """
    Create the BN dcm in order to point to the primary and secondary headings
    """
    primary_heading = primary_heading / np.linalg.norm(primary_heading)
    secondary_heading = secondary_heading / np.linalg.norm(secondary_heading)

    BC = camera_to_body_dcm.transpose()
    CP = camera_correction_rotation().transpose()
    TN = form_dcm(primary_heading, secondary_heading)
    return np.dot(BC, np.dot(CP, TN))


def dcm_to_quaternion(C):
    """
    dcm_to_quaternion
        Q = dcm_to_quaternion(C) translates the 3x3 direction cosine matrix
        C into the corresponding 4x1 euler parameter vector Q,
        where the first component of Q is the non-dimensional
        Euler parameter Beta_0 >= 0. Transformation is done
        using the Stanley method.
    """
    tr = np.trace(C)
    b2 = np.array([(1 + tr) / 4, (1 + 2 * C[0, 0] - tr) / 4, (1 + 2 * C[1, 1] - tr) / 4, (1 + 2 * C[2, 2] - tr) / 4])
    case = np.argmax(b2)
    b = b2
    if case == 0:
        b[0] = np.sqrt(b2[0])
        b[1] = (C[1, 2] - C[2, 1]) / 4 / b[0]
        b[2] = (C[2, 0] - C[0, 2]) / 4 / b[0]
        b[3] = (C[0, 1] - C[1, 0]) / 4 / b[0]
    elif case == 1:
        b[1] = np.sqrt(b2[1])
        b[0] = (C[1, 2] - C[2, 1]) / 4 / b[1]
        if b[0] < 0:
            b[1] = -b[1]
            b[0] = -b[0]
        b[2] = (C[0, 1] + C[1, 0]) / 4 / b[1]
        b[3] = (C[2, 0] + C[0, 2]) / 4 / b[1]
    elif case == 2:
        b[2] = np.sqrt(b2[2])
        b[0] = (C[2, 0] - C[0, 2]) / 4 / b[2]
        if b[0] < 0:
            b[2] = -b[2]
            b[0] = -b[0]
        b[1] = (C[0, 1] + C[1, 0]) / 4 / b[2]
        b[3] = (C[1, 2] + C[2, 1]) / 4 / b[2]
    elif case == 3:
        b[3] = np.sqrt(b2[3])
        b[0] = (C[0, 1] - C[1, 0]) / 4 / b[3]
        if b[0] < 0:
            b[3] = -b[3]
            b[0] = -b[0]
        b[1] = (C[2, 0] + C[0, 2]) / 4 / b[3]
        b[2] = (C[1, 2] + C[2, 1]) / 4 / b[3]
    return b


def dcm_to_euler321(C):
    """
    dcm_to_euler321

    	Q = dcm_to_euler321(C) translates the 3x3 direction cosine matrix
    	C into the corresponding (3-2-1) euler angle set.
    """

    q0 = math.atan2(C[0, 1], C[0, 0])
    q1 = math.asin(-C[0, 2])
    q2 = math.atan2(C[1, 2], C[2, 2])
    q = np.array([q0, q1, q2])
    return q


def dcm_to_mrp(C):
    """
    dcm_to_mrp

    	Q = dcm_to_mrp(C) translates the 3x3 direction cosine matrix
    	C into the corresponding 3x1 mrp vector Q where the
    	mrp vector is chosen such that :math:`|Q| <= 1`.
    """

    b = dcm_to_quaternion(C)
    q = np.array([b[1] / (1 + b[0]), b[2] / (1 + b[0]), b[3] / (1 + b[0])])
    return q


def dcm_to_principalRotation(C):
    """
    dcm_to_principalRotation

    	Q = dcm_to_principalRotation(C) translates the 3x3 direction cosine matrix
    	C into the corresponding 3x1 principal rotation vector Q,
    	where the first component of Q is the principal rotation angle
    	phi (0<= phi <= Pi)
    """

    cp = (np.trace(C) - 1) / 2
    p = np.arccos(cp)
    sp = p / 2. / np.sin(p)
    q = np.array([(C[1, 2] - C[2, 1]) * sp, (C[2, 0] - C[0, 2]) * sp, (C[0, 1] - C[1, 0]) * sp])
    return q


def mrp_to_dcm(q):
    """
    mrp_to_dcm

    	C = mrp_to_dcm(Q) returns the direction cosine
    	matrix in terms of the 3x1 mrp vector Q.
    """

    q1 = q[0]
    q2 = q[1]
    q3 = q[2]
    qm = np.linalg.norm(q)
    d1 = qm * qm
    S = 1 - d1
    d = (1 + d1) * (1 + d1)
    C = np.zeros((3, 3))
    C[0, 0] = 4 * (2 * q1 * q1 - d1) + S * S
    C[0, 1] = 8 * q1 * q2 + 4 * q3 * S
    C[0, 2] = 8 * q1 * q3 - 4 * q2 * S
    C[1, 0] = 8 * q2 * q1 - 4 * q3 * S
    C[1, 1] = 4 * (2 * q2 * q2 - d1) + S * S
    C[1, 2] = 8 * q2 * q3 + 4 * q1 * S
    C[2, 0] = 8 * q3 * q1 + 4 * q2 * S
    C[2, 1] = 8 * q3 * q2 - 4 * q1 * S
    C[2, 2] = 4 * (2 * q3 * q3 - d1) + S * S
    C = C / d
    return C


def mrp_to_quaternion(q1):
    """
    mrp_to_quaternion(Q1)

    	Q = mrp_to_quaternion(Q1) translates the mrp vector Q1
    	into the euler parameter vector Q.
    """
    qm = np.linalg.norm(q1)
    ps = 1 + qm * qm
    q = np.array([(1 - qm * qm) / ps, 2 * q1[0] / ps, 2 * q1[1] / ps, 2 * q1[2] / ps])
    return q


def mrp_to_euler321(q):
    """
    mrp_to_euler321(Q)

    	E = mrp_to_euler321(Q) translates the mrp
    	 vector Q into the (3-2-1) euler angle vector E.
    """

    return quaternion_to_euler321(mrp_to_quaternion(q))


def mrp_to_principalRotation(q):
    """
    mrp_to_principalRotation(Q1)

    	Q = mrp_to_principalRotation(Q1) translates the mrp vector Q1
    	into the principal rotation vector Q.
    """

    tp = np.linalg.norm(q)
    p = 4 * math.atan(tp)
    q0 = q[0] / tp * p
    q1 = q[1] / tp * p
    q2 = q[2] / tp * p
    q = np.array([q0, q1, q2])

    return q


def mrp_switch(q, s2):
    """
    mrp_switch

    	S = mrp_switch(Q,s2) checks to see if norm(Q) is larger than s2.
    	If yes, then the mrp vector Q is mapped to its shadow set.
    """

    q2 = np.dot(q, q)
    if (q2 > s2 * s2):
        s = -q / q2
    else:
        s = q

    return s


def principalRotation_to_dcm(q):
    """
    principalRotation_to_dcm

    	C = principalRotation_to_dcm(Q) returns the direction cosine
    	matrix in terms of the 3x1 principal rotation vector
    	Q.
    """

    q0 = np.linalg.norm(q)
    if q0 == 0.0:
        q1 = q[0]
        q2 = q[1]
        q3 = q[2]
    else:
        q1 = q[0] / q0
        q2 = q[1] / q0
        q3 = q[2] / q0
    cp = np.cos(q0)
    sp = np.sin(q0)
    d1 = 1 - cp
    C = np.zeros((3, 3))
    C[0, 0] = q1 * q1 * d1 + cp
    C[0, 1] = q1 * q2 * d1 + q3 * sp
    C[0, 2] = q1 * q3 * d1 - q2 * sp
    C[1, 0] = q2 * q1 * d1 - q3 * sp
    C[1, 1] = q2 * q2 * d1 + cp
    C[1, 2] = q2 * q3 * d1 + q1 * sp
    C[2, 0] = q3 * q1 * d1 + q2 * sp
    C[2, 1] = q3 * q2 * d1 - q1 * sp
    C[2, 2] = q3 * q3 * d1 + cp
    return C


def principalRotation_to_quaternion(qq1):
    """"
    principalRotation_to_quaternion(Q1)

    	Q = principalRotation_to_quaternion(Q1) translates the principal rotation vector Q1
    	into the euler parameter vector Q.
    """

    return dcm_to_quaternion(principalRotation_to_dcm(qq1))


def principalRotation_to_euler321(q):
    """
    principalRotation_to_euler321(Q)

    	E = principalRotation_to_euler321(Q) translates the principal rotation
    	vector Q into the (3-2-1) euler angle vector E.
    """

    return quaternion_to_euler321(principalRotation_to_quaternion(q))


def principalRotation_to_mrp(q):
    """
     principalRotation_to_mrp(Q1)

    	Q = principalRotation_to_mrp(Q1) translates the principal rotation vector Q1
    	into the mrp vector Q.
    """

    return dcm_to_mrp(principalRotation_to_dcm(q))


def quaternion_to_dcm(q):
    """
	quaternion_to_dcm

        C = quaternion_to_dcm(Q) returns the direction math.cosine
        matrix in terms of the 4x1 euler parameter vector
        Q.  The first element is the non-dimensional euler
        parameter, while the remain three elements form
        the euler parameter vector.
	"""
    q0 = q[0]
    q1 = q[1]
    q2 = q[2]
    q3 = q[3]
    C = np.zeros([3, 3])
    C[0, 0] = q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3
    C[0, 1] = 2 * (q1 * q2 + q0 * q3)
    C[0, 2] = 2 * (q1 * q3 - q0 * q2)
    C[1, 0] = 2 * (q1 * q2 - q0 * q3)
    C[1, 1] = q0 * q0 - q1 * q1 + q2 * q2 - q3 * q3
    C[1, 2] = 2 * (q2 * q3 + q0 * q1)
    C[2, 0] = 2 * (q1 * q3 + q0 * q2)
    C[2, 1] = 2 * (q2 * q3 - q0 * q1)
    C[2, 2] = q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3
    return C


def quaternion_to_euler321(q):
    """
    quaternion_to_euler321

    	E = quaternion_to_euler321(Q) translates the euler parameter vector
    	Q into the corresponding (3-2-1) euler angle set.
    """

    q0 = q[0]
    q1 = q[1]
    q2 = q[2]
    q3 = q[3]

    e1 = math.atan2(2 * (q1 * q2 + q0 * q3), q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3)
    e2 = math.asin(-2 * (q1 * q3 - q0 * q2))
    e3 = math.atan2(2 * (q2 * q3 + q0 * q1), q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3)

    e = np.array([e1, e2, e3])
    return e


def quaternion_to_mrp(q):
    """
    quaternion_to_mrp(Q1)
        Q = quaternion_to_mrp(Q1) translates the euler parameter vector Q1
        into the mrp vector Q.
    """

    if q[0] < 0:
        q = -q

    q1 = q[1] / (1 + q[0])
    q2 = q[2] / (1 + q[0])
    q3 = q[3] / (1 + q[0])

    return np.array([q1, q2, q3])


def quaternion_to_principalRotation(q):
    """
    quaternion_to_principalRotation(Q1)

    	Q = quaternion_to_principalRotation(Q1) translates the euler parameter vector Q1
    	into the principal rotation vector Q.
    """

    p = 2 * math.acos(q[0])
    sp = math.sin(p / 2)
    q1 = q[1] / sp * p
    q2 = q[2] / sp * p
    q3 = q[3] / sp * p

    return np.array([q1, q2, q3])


def euler1(x):
    """
	EULER1 	Elementary rotation matrix
	Returns the elementary rotation matrix about the first body axis.
	"""
    m = np.identity(3)
    m[1, 1] = math.cos(x)
    m[1, 2] = math.sin(x)
    m[2, 1] = -m[1, 2]
    m[2, 2] = m[1, 1]

    return m


def euler2(x):
    """
	EULER2 	Elementary rotation matrix
	Returns the elementary rotation matrix about the
	second body axis.
	"""
    m = np.identity(3)
    m[0, 0] = math.cos(x)
    m[0, 2] = -math.sin(x)
    m[2, 0] = -m[0, 2]
    m[2, 2] = m[0, 0]

    return m


def euler3(x):
    """
	EULER3 	Elementary rotation matrix
	Returns the elementary rotation matrix about the
	third body axis.
	"""
    m = np.identity(3)
    m[0, 0] = math.cos(x)
    m[0, 1] = math.sin(x)
    m[1, 0] = -m[0, 1]
    m[1, 1] = m[0, 0]

    return m


def euler321_to_dcm(q):
    """
    euler321_to_dcm
    	C = euler321_to_dcm(Q) returns the direction cosine
    	matrix in terms of the 3-2-1 euler angles.
    	Input Q must be a 3x1 vector of euler angles.
    """

    st1 = math.sin(q[0])
    ct1 = math.cos(q[0])
    st2 = math.sin(q[1])
    ct2 = math.cos(q[1])
    st3 = math.sin(q[2])
    ct3 = math.cos(q[2])

    C = np.identity(3)
    C[0, 0] = ct2 * ct1
    C[0, 1] = ct2 * st1
    C[0, 2] = -st2
    C[1, 0] = st3 * st2 * ct1 - ct3 * st1
    C[1, 1] = st3 * st2 * st1 + ct3 * ct1
    C[1, 2] = st3 * ct2
    C[2, 0] = ct3 * st2 * ct1 + st3 * st1
    C[2, 1] = ct3 * st2 * st1 - st3 * ct1
    C[2, 2] = ct3 * ct2

    return C


def euler321_to_quaternion(e):
    """
    euler321_to_quaternion(E)
        Q = euler321_to_quaternion(E) translates the 321 euler angle
        vector E into the euler parameter vector Q.
    """

    c1 = math.cos(e[0] / 2)
    s1 = math.sin(e[0] / 2)
    c2 = math.cos(e[1] / 2)
    s2 = math.sin(e[1] / 2)
    c3 = math.cos(e[2] / 2)
    s3 = math.sin(e[2] / 2)

    q0 = c1 * c2 * c3 + s1 * s2 * s3
    q1 = c1 * c2 * s3 - s1 * s2 * c3
    q2 = c1 * s2 * c3 + s1 * c2 * s3
    q3 = s1 * c2 * c3 - c1 * s2 * s3

    return np.array([q0, q1, q2, q3])


def euler321_to_mrp(e):
    """
    euler321_to_mrp(E)
        Q = euler321_to_mrp(E) translates the (3-2-1) euler
        angle vector E into the mrp vector Q.
    """

    return quaternion_to_mrp(euler321_to_quaternion(e))


def euler321_to_principalRotation(e):
    """
     euler321_to_principalRotation(E)

    	Q = euler321_to_principalRotation(E) translates the (3-2-1) euler
    	angle vector E into the principal rotation vector Q.
    """

    return quaternion_to_principalRotation(euler321_to_quaternion(e))
