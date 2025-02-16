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


class ClassicElements(object):
    """
    Containger class for the classical orbital elements
    """
    a = None
    e = None
    i = None
    Omega = None
    omega = None
    f = None
    rmag = None
    alpha = None
    rPeriap = None
    rApoap = None


def elem2rv_parab(mu, elements):
    """
    Translates the orbit elements:

    === ========================= =======
    a   semi-major axis           km
    e   eccentricity
    i   inclination               rad
    AN  ascending node            rad
    AP  argument of periapses     rad
    f   true anomaly angle        rad
    === ========================= =======

    to the inertial Cartesian position and velocity vectors.
    The attracting body is specified through the supplied
    gravitational constant mu (units of km^3/s^2).

    The code can handle the following cases:

    ================== ============  ===========   =======================
        circular:       e = 0           a > 0
        elliptical-2D:  0 < e < 1       a > 0
        elliptical-1D:  e = 1           a > 0        f = Ecc. Anom. here
        parabolic:      e = 1           rp = -a
        hyperbolic:     e > 1           a < 0
    ================== ============  ===========   =======================

    .. note::

        To handle the parabolic case and distinguish it form the
        rectilinear elliptical case, instead of passing along the
        semi-major axis a in the "a" input slot, the negative radius
        at periapses is supplied.  Having "a" be negative and e = 1
        is a then a unique identified for the code for the parabolic
        case.

    :param mu: gravitational parameter
    :param elements: orbital elements
    :return:   rVec = position vector, vVec = velocity vector
    """
    a = elements.a
    e = elements.e
    i = elements.i
    AN = elements.Omega
    AP = elements.omega
    f = elements.f

    ir = np.zeros(3)
    rVec = np.zeros(3)
    vVec = np.zeros(3)

    # TODO: Might want to have an error band on this equality #
    if np.abs(e - 1) < 1E-10 and a > 0.0:  # rectilinear elliptic orbit case #
        Ecc = f  # f is treated as ecc. anomaly #
        r = a * (1.0 - e * math.cos(Ecc))  # orbit radius #
        v = math.sqrt(2.0 * mu / r - mu / a)
        ir[0] = math.cos(AN) * math.cos(AP) - math.sin(AN) * math.sin(AP) * math.cos(i)
        ir[1] = math.sin(AN) * math.cos(AP) + math.cos(AN) * math.sin(AP) * math.cos(i)
        ir[2] = math.sin(AP) * math.sin(i)
        rVec = r * ir
        if math.sin(Ecc) > 0.0:
            vVec = -v * ir
        else:
            vVec = v * ir

    else:
        if e == 1.0 and a < 0.0:  # parabolic case #
            rp = -a  # radius at periapses #
            p = 2.0 * rp  # semi-latus rectum #
        else:  # elliptic and hyperbolic cases #
            p = a * (1.0 - e * e)  # semi-latus rectum #

        r = p / (1.0 + e * math.cos(f))  # orbit radius #
        theta = AP + f  # true latitude angle #
        h = math.sqrt(mu * p)  # orbit ang. momentum mag.

        rVec[0] = r * (math.cos(AN) * math.cos(theta) - math.sin(AN) * math.sin(theta) * math.cos(i))
        rVec[1] = r * (math.sin(AN) * math.cos(theta) + math.cos(AN) * math.sin(theta) * math.cos(i))
        rVec[2] = r * (math.sin(theta) * math.sin(i))

        vVec[0] = -mu / h * (math.cos(AN) * (math.sin(theta) + e * math.sin(AP)) + math.sin(AN) * (
                    math.cos(theta) + e * math.cos(AP)) * math.cos(i))
        vVec[1] = -mu / h * (math.sin(AN) * (math.sin(theta) + e * math.sin(AP)) - math.cos(AN) * (
                    math.cos(theta) + e * math.cos(AP)) * math.cos(i))
        vVec[2] = -mu / h * (-(math.cos(theta) + e * math.cos(AP)) * math.sin(i))

    return rVec, vVec


def rv2elem_parab(mu, rVec, vVec):
    """
    Translates the orbit elements inertial Cartesian position
    vector rVec and velocity vector vVec into the corresponding
    classical orbit elements where

    === ========================= =======
    a   semi-major axis             km
    e   eccentricity
    i   inclination                 rad
    AN  ascending node              rad
    AP  argument of periapses       rad
    f   true anomaly angle          rad
    === ========================= =======

    If the orbit is rectilinear, then f will be the eccentric or hyperbolic anomaly

    The attracting body is specified through the supplied
    gravitational constant mu (units of km^3/s^2).

    The code can handle the following cases:

    ============== ============= ===========
    circular:       e = 0           a > 0
    elliptical-2D:  0 < e < 1       a > 0
    elliptical-1D:  e = 1           a > 0
    parabolic:      e = 1           a = -rp
    hyperbolic:     e > 1           a < 0
    ============== ============= ===========

    For the parabolic case the semi-major axis is not defined.
    In this case -rp (radius at periapses) is returned instead
    of a.  For the circular case, the AN and AP are ill-defined,
    along with the associated ie and ip unit direction vectors
    of the perifocal frame. In this circular orbit case, the
    unit vector ie is set equal to the normalized inertial
    position vector ir.

    :param   mu:  gravitational parameter
    :param   rVec:  position vector
    :param   vVec: velocity vector
    :return: orbital elements


    Todo: Modify this code to return true longitude of periapsis
    (non-circular, equatorial), argument of latitude (circular, inclined),
    and true longitude (circular, equatorial) when appropriate instead of
    simply zeroing out omega and Omega

    """
    ie = np.zeros(3)
    elements = ClassicElements()

    # compute orbit radius #
    r = np.linalg.norm(rVec)
    elements.rmag = r
    ir = rVec / np.linalg.norm(rVec)

    # compute the angular momentum vector #
    hVec = np.cross(rVec, vVec)
    h = np.linalg.norm(hVec)

    # compute the eccentricity vector #
    cVec = np.cross(vVec, hVec)
    dum = (-mu / r) * rVec
    cVec = cVec + dum
    elements.e = np.linalg.norm(cVec) / mu

    # compute semi-major axis #
    elements.alpha = 2.0 / r - np.dot(vVec, vVec) / mu
    if np.abs(elements.alpha) > 1E-10:
        # elliptic or hyperbolic case #
        elements.a = 1.0 / elements.alpha
        elements.rPeriap = elements.a * (1.0 - elements.e)
        elements.rApoap = elements.a * (1.0 + elements.e)
    else:
        #  parabolic case #
        elements.alpha = 0.
        p = h * h / mu
        rp = p / 2.0
        elements.a = -rp  # a is not defined for parabola, so - rp is returned instead #
        elements.e = 1.0
        elements.rPeriap = rp
        elements.rApoap = -rp  # periapses radius doesn't exist, returning -rp instead #

    if h < 1E-10:  # rectilinear motion case #
        dum = np.array([0.0, 0.0, 1.0])
        dum2 = np.array([0.0, 1.0, 0.0])
        ih = np.cross(ie, dum)
        ip = np.cross(ie, dum2)
        if np.linalg.norm(ih) > np.linalg.norm(ip):
            ih = ih / np.linalg.norm(ih)
        else:
            ih = ip / np.linalg.norm(ip)
        ip = np.cross(ih, ie)
    else:
        ih = hVec / np.linalg.norm(hVec)
        if np.abs(elements.e) > 1E-10:
            ie = (1.0 / mu / elements.e) * cVec
        else:
            ie = ir
        # circular orbit case.  Here ie, ip are arbitrary, as long as they #
        # are perpenticular to the ih vector. #
        ip = np.cross(ih, ie)

    # compute the 3-1-3 orbit plane orientation angles #
    elements.i = math.acos(ih[2])
    if elements.i > 1E-10 and elements.i < np.pi - 1E-10:
        elements.Omega = math.atan2(ih[0], -ih[1])
        elements.omega = math.atan2(ie[2], ip[2])
    else:
        elements.Omega = 0.
        elements.omega = math.atan2(ie[1], ie[0])

    if h < 1E-10:  # rectilinear motion case #
        if elements.alpha > 0:  # elliptic case #
            Ecc = math.acos(1 - r * elements.alpha)
            if np.dot(rVec, vVec) > 0:
                Ecc = 2.0 * np.pi - Ecc
            elements.f = Ecc  # for this mode the eccentric anomaly is returned #
        else:  # hyperbolic case #
            H = math.acosh(r * elements.alpha + 1)
            if np.dot(rVec, vVec) < 0:
                H = 2.0 * np.pi - H
            elements.f = H  # for this mode the hyperbolic anomaly is returned #
    else:
        # compute true anomaly #
        dum = np.cross(ie, ir)
        elements.f = math.atan2(np.dot(dum, ih), np.dot(ie, ir))

    return elements


def rk4(dynamics, time, initial_state, arg=None):
    if arg is not None:
        functionArg = arg
    state = np.zeros([len(time), len(initial_state) + 1])
    step = (time[len(time) - 1] - time[0]) / len(time)
    state[0, 0] = time[0]
    state[0, 1:] = initial_state
    for i in range(len(time) - 1):
        step = time[i + 1] - time[i]
        state[i, 0] = time[i]
        k1 = step * dynamics(time[i], state[i, 1:], functionArg)
        k2 = step * dynamics(time[i] + 0.5 * step, state[i, 1:] + 0.5 * k1, functionArg)
        k3 = step * dynamics(time[i] + 0.5 * step, state[i, 1:] + 0.5 * k2, functionArg)
        k4 = step * dynamics(time[i] + step, state[i, 1:] + k3, functionArg)
        state[i + 1, 1:] = state[i, 1:] + (k1 + 2. * k2 + 2. * k3 + k4) / 6.
        state[i + 1, 0] = time[i + 1]
    return state


def point_mass_dynamics(time, state, gravitational_parameter):
    dxdt = np.zeros(np.shape(state))
    dxdt[0:3] = state[3:]
    dxdt[3:] = -gravitational_parameter / np.linalg.norm(state[0:3]) ** 3. * state[0:3]
    return dxdt


def propagate_cartesian(gravitational_parameter, initial_state, start_time, end_time):
    time = np.arange(start_time, end_time + 1, 1)  # 1 sec steps for orbital integration
    propagated = rk4(point_mass_dynamics, time, initial_state, arg=gravitational_parameter)
    return propagated[-1, 1:]
