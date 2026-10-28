"""
Section 4.3 -- assumption fall-off for the geometric (binary) CoB model
on a triaxial ellipsoid.

Conventions
-----------
A      3x3 shape matrix, x^T A x = 1.  Principal axes: diag(1/a^2, 1/b^2, 1/c^2).
       In the camera frame, A_C = [EC]^T A_E [EC].
s      unit vector body -> Sun
r      unit vector body -> observer
rho    observer range (same length units as the semi-axes)

All lengths are in body units unless noted.  Image-plane 2-vectors are expressed
in the orthonormal basis (e1, e2) of r-perp returned by image_basis().
"""

import numpy as np

G0 = 4.0 / (3.0 * np.pi)


# ----------------------------------------------------------------------
# 4.3.0  invariants  (Eqs. 11, 13, 40)
# ----------------------------------------------------------------------


def invariants(A, s, r, rho=None):
    """sigma, tau, chi, alpha, alpha_tilde, k, eps_tilde."""
    sig2, tau2, chi = s @ A @ s, r @ A @ r, s @ A @ r
    sig, tau = np.sqrt(sig2), np.sqrt(tau2)
    disc = sig2 * tau2 - chi**2  # > 0 unless s || r
    out = dict(
        sig=sig,
        tau=tau,
        chi=chi,
        disc=disc,
        alpha=np.arccos(np.clip(s @ r, -1.0, 1.0)),
        cos_at=chi / (sig * tau),
        sin_at=np.sqrt(max(disc, 0.0)) / (sig * tau),
        k=tau / sig,
    )
    out["alpha_t"] = np.arctan2(out["sin_at"], out["cos_at"])
    out["eps_t"] = None if rho is None else 1.0 / (rho * tau)
    return out


def image_basis(r):
    """Orthonormal (e1, e2) spanning r-perp.  e3 = -r is the boresight."""
    e3 = -r
    tmp = np.array([0.0, 0.0, 1.0])
    if abs(tmp @ e3) > 0.9:
        tmp = np.array([1.0, 0.0, 0.0])
    e1 = np.cross(tmp, e3)
    e1 /= np.linalg.norm(e1)
    return e1, np.cross(e3, e1)


def delta_caseA(A, s, r):
    """Baseline offset, Eq. (33).  3-vector in body units, along Pi s."""
    v = invariants(A, s, r)
    gam = G0 * (1.0 - v["cos_at"])
    return gam * v["tau"] / np.sqrt(v["disc"]) * (s - (s @ r) * r)


def half_width(A, d3):
    """Apparent half-width along a unit 3-vector d3 perpendicular to r.
    Lemma 3:  h = sqrt(d^T A^-1 d).  Body units."""
    return np.sqrt(d3 @ np.linalg.inv(A) @ d3)


# ----------------------------------------------------------------------
# 4.3.1  geometric threshold  (Eqs. 47-49)
# ----------------------------------------------------------------------


def gamma_D(alpha, eps):
    """Threshold-corrected spherical offset, Eq. (49).

    Returns (gamma_D, gamma_D_hat).  gamma_D is the one that pushes forward to
    the ellipsoid; gamma_D_hat = gamma_D / r_L is the one comparable to gamma_G.
    Dividing by r_L before the push-forward is an O(eps^2) error.
    """
    sa, ca = np.sin(alpha), np.cos(alpha)
    if sa <= eps:  # terminator does not reach the limb
        return (0.0, 0.0) if ca > 0 else (np.nan, np.nan)  # fully lit / fully dark
    rL = np.sqrt(1.0 - eps**2)
    psi = np.arccos(np.clip(-eps * ca / (sa * rL), -1.0, 1.0))
    phi = np.arccos(np.clip(-eps / sa, -1.0, 1.0))
    Ac = rL**2 * (psi - np.sin(psi) * np.cos(psi))
    Qc = (2.0 / 3.0) * rL**3 * np.sin(psi) ** 3
    Ae = ca * (np.pi - phi + np.sin(phi) * np.cos(phi))  # ca kept signed
    Qe = -(2.0 / 3.0) * ca**2 * np.sin(phi) ** 3
    gD = (Qc + Qe) / (Ac + Ae)
    return gD, gD / rL


def delta_caseD(A, s, r, rho):
    """Threshold-corrected offset, Eq. (50).  Exact under the change of
    variables: Eq. (33) with gamma_G(alpha_t) -> gamma_D(alpha_t, eps_t)."""
    v = invariants(A, s, r, rho)
    gD, _ = gamma_D(v["alpha_t"], v["eps_t"])
    return gD * v["tau"] / np.sqrt(v["disc"]) * (s - (s @ r) * r)


# ----------------------------------------------------------------------
# 4.3.2  projective error  (Eqs. 51-55)
# ----------------------------------------------------------------------

# c1(alpha): leading projective coefficient, fitted over eps in [0.004, 0.045].
# gamma_hat_ref = gamma_G - c1*eps - c2*eps^2 + O(eps^3).
_C1_DEG = np.arange(5, 180, 5, dtype=float)
_C1_VAL = np.array(
    [
        +0.04307,
        +0.08554,
        +0.12524,
        +0.16120,
        +0.19238,
        +0.21786,
        +0.23689,
        +0.24889,
        +0.25348,
        +0.25051,
        +0.24002,
        +0.22226,
        +0.19770,
        +0.16697,
        +0.13086,
        +0.09030,
        +0.04632,
        +0.00000,
        -0.04755,
        -0.09524,
        -0.14204,
        -0.18704,
        -0.22948,
        -0.26882,
        -0.30480,
        -0.33752,
        -0.36756,
        -0.39618,
        -0.42565,
        -0.45990,
        -0.50599,
        -0.57778,
        -0.70683,
        -0.98620,
        -1.87501,
    ]
)


def c1(alpha):
    """Projective coefficient, interpolated.  Sign flips at quadrature.
    Diverges as alpha -> pi; do not trust beyond ~165 deg."""
    return float(np.interp(np.degrees(alpha), _C1_DEG, _C1_VAL))


def limb_centre(A, r, rho):
    """x_c, Eq. (53).  EXACT at every range (Sherman-Morrison).

    Returns (x_c_2vec_body, e1, e2).  The 2-vector is in body length units,
    in the (e1, e2) image basis.  Zero for a sphere, and whenever A r || r.
    """
    e1, e2 = image_basis(r)
    Ar = A @ r
    tau2 = r @ A @ r
    a = np.array([e1 @ Ar, e2 @ Ar])  # Pi_perp(A r)
    Aperp = np.array([[e1 @ A @ e1, e1 @ A @ e2], [e2 @ A @ e1, e2 @ A @ e2]])
    Ainv_a = np.linalg.solve(Aperp, a)
    beta = a @ Ainv_a
    xc_gnomonic = -Ainv_a / (rho**2 * (tau2 - beta) - 1.0)
    return rho * xc_gnomonic, e1, e2  # gnomonic -> body units


def tilt_angle(A, r):
    """theta_tilt = angle(A r, r).  Drives x_c; zero on a principal axis."""
    Ar = A @ r
    return np.arccos(np.clip(abs(Ar @ r) / np.linalg.norm(Ar), -1.0, 1.0))


def error_components(A, s, r, rho):
    """Case-D residual decomposed on the solar frame, Eq. (55).

        e = (reference - delta_caseD) / h

    with h the apparent half-width along Pi s.  Returns e_par, e_perp as
    fractions of h, plus the pieces that build them.

    Accuracy, measured against full numerical integration of Eq. (1) over
    random triaxial configurations with eps_t <= 0.25:

        e_perp   residual ~5e-4 of h   (median)  -- x_c is exact, and it is the
                                                    only contributor
        e_par    residual ~2e-2 of h   (median)  -- O(eps_t^2) remainder, plus
                                                    c1 being a SPHERICAL
                                                    coefficient applied at
                                                    alpha_t

    So treat e_perp as a prediction and e_par as an estimate.  Both degrade
    beyond eps_t ~ 0.3, where the O(eps_t) budget stops being meaningful.

    Note h is evaluated orthographically (Lemma 3).  The perspective half-width
    differs at O(eps_t), hence O(eps_t^2) here -- the same order as the residual.
    """
    v = invariants(A, s, r, rho)
    xc, e1, e2 = limb_centre(A, r, rho)

    w3 = s - (s @ r) * r  # 3-vector along Pi s
    d3 = w3 / np.linalg.norm(w3)
    h = half_width(A, d3)  # body units
    d2 = np.array([d3 @ e1, d3 @ e2])  # same direction, image basis
    d2 /= np.linalg.norm(d2)
    dperp2 = np.array([-d2[1], d2[0]])

    # e = reference - model, and  gamma_hat_ref = gamma_hat_D - c1*eps,
    # so the projective term enters with a MINUS sign.
    proj = -c1(v["alpha_t"]) * v["eps_t"]
    return dict(
        e_par=(xc @ d2) / h + proj,
        e_perp=(xc @ dperp2) / h,
        xc_over_h=np.linalg.norm(xc) / h,
        xi_sh=np.linalg.norm(xc) / (h * v["eps_t"]),  # shape-pose amplitude
        dphi=np.arctan2(xc @ dperp2, xc @ d2),  # angle from d to x_c
        c1=c1(v["alpha_t"]),
        eps_t=v["eps_t"],
        h=h,
    )


def error_vector(A, s, r, rho):
    """The residual as a 3-vector in body units, perpendicular to r.

    Adding this to delta_caseD approximates the finite-range reference; it is
    NOT a correction the paper endorses, but it is the natural object to feed a
    covariance as a bias term.
    """
    e = error_components(A, s, r, rho)
    e1, e2 = image_basis(r)
    w3 = s - (s @ r) * r
    d3 = w3 / np.linalg.norm(w3)
    # e_perp is measured along dperp2 = d2 rotated +90 deg in the right-handed (e1, e2, e3) basis, which is
    # e3 x d3 = -r x d3. np.cross(r, d3) is the opposite direction and flips the perpendicular term.
    dperp3 = np.cross(-r, d3)
    return e["h"] * (e["e_par"] * d3 + e["e_perp"] * dperp3)


def full_offset(A, s, r, rho):
    """Case D offset plus the projective and limb-centre residual: the finite-range CoB offset, body units.

    Against a perspective ray cast of the lit ellipsoid this is within ~1e-2 of the half-width h for
    eps_t <= 0.2, where Case A is off by up to 0.15 h.
    """
    return delta_caseD(A, s, r, rho) + error_vector(A, s, r, rho)


def max_range_for(A, s, r, q):
    """Validity criterion, Eq. (56):  eps_t <= q / (|c1| + xi_sh).
    Returns the minimum range rho giving error <= q * apparent half-width.
    xi_sh is evaluated at a large reference range, where it is range-independent.
    """
    v = invariants(A, s, r, 1.0)
    ref = 1e4 / np.sqrt(v["tau"])  # any far range
    xi = error_components(A, s, r, ref)["xi_sh"]
    eps_max = q / (abs(c1(v["alpha_t"])) + xi)
    return 1.0 / (eps_max * v["tau"]), eps_max, xi


# ----------------------------------------------------------------------
# 4.3.3  foreshortening: identically zero for the geometric model.
#        Under flat-fielding the offset is the image-AREA centroid, so the
#        (n.d)/|d|^2 weight enters only through the image-area conversion,
#        which the projective map already carries.  No separate term.
# ----------------------------------------------------------------------


if __name__ == "__main__":
    a, b, c = 1.6, 1.0, 0.7
    A = np.diag([1 / a**2, 1 / b**2, 1 / c**2])
    r = np.array([0.25, 0.55, -0.797])
    r /= np.linalg.norm(r)
    s = np.array([0.8, 0.10, 0.59])
    s /= np.linalg.norm(s)
    rho = 6.0

    v = invariants(A, s, r, rho)
    print(f"alpha    = {np.degrees(v['alpha']):7.2f} deg")
    print(f"alpha_t  = {np.degrees(v['alpha_t']):7.2f} deg    k = {v['k']:.4f}" f"    eps_t = {v['eps_t']:.4f}")
    print(f"tilt     = {np.degrees(tilt_angle(A, r)):7.2f} deg")
    print()
    dA, dD = delta_caseA(A, s, r), delta_caseD(A, s, r, rho)
    print(f"delta (Case A) = {np.round(dA, 6)}   |.| = {np.linalg.norm(dA):.6f}")
    print(f"delta (Case D) = {np.round(dD, 6)}   |.| = {np.linalg.norm(dD):.6f}")
    print()
    e = error_components(A, s, r, rho)
    print(f"xi_sh        = {e['xi_sh']:.4f}      c1(alpha_t) = {e['c1']:+.4f}")
    print(f"e_par  / h   = {e['e_par']:+.4f}")
    print(f"e_perp / h   = {e['e_perp']:+.4f}")
    print()
    for q in (0.01, 0.05):
        rmin, emax, xi = max_range_for(A, s, r, q)
        print(
            f"error <= {q:.0%} of apparent radius:  eps_t <= {emax:.4f}"
            f"   ->  rho >= {rmin:.1f}  ({rmin / max(a, b, c):.0f} max-semi-axes)"
        )
