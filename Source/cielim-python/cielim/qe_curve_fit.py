import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import simps
from pathlib import Path
import pandas as pd
from scipy.optimize import basinhopping

# Constants
h = 6.62607015e-34  # Planck constant, J·s
c = 299792458  # Speed of light, m/s
k_B = 1.380649e-23  # Boltzmann constant, J/K
pi = 3.1415


def _solar_irradiance_planck_nm(
    wavelength_nm, T=5772.0, R_sun=6.957e8, AU=1.495978707e11  # Sun's effective temp [K]  # Solar radius [m]
):  # 1 astronomical unit [m]
    """
    Compute solar spectral irradiance at 1 AU from a blackbody Sun.

    Inputs
    ------
    wavelength_nm : array_like
        Wavelengths in nanometers.
    T : float
        Blackbody temperature in Kelvin (default: 5772 K).
    R_sun : float
        Radius of the Sun in meters.
    AU : float
        Astronomical Unit in meters.

    Returns
    -------
    E_lambda_nm : np.ndarray
        Spectral irradiance at 1 AU in W·m^-2·nm^-1, same shape as wavelength_nm.
    """
    # Physical constants (SI)
    global h, c, k_B

    wl_nm = np.asarray(wavelength_nm, dtype=np.float64)
    wl_m = wl_nm * 1e-9  # convert nm -> m

    # Planck spectral radiance per unit wavelength (per meter): B_λ [W·m^-2·sr^-1·m^-1]
    # Use expm1 for numerical stability.
    x = (h * c) / (wl_m * k_B * T)
    B_lambda_per_m = (2.0 * h * c**2) / (wl_m**5) / np.expm1(x)

    # Radiance -> surface flux per wavelength: F_λ = π B_λ  [W·m^-2·m^-1]
    F_lambda_per_m = np.pi * B_lambda_per_m

    # Geometric dilution to 1 AU: multiply by (R_sun / AU)^2
    dilution = (R_sun / AU) ** 2
    E_lambda_per_m = F_lambda_per_m * dilution  # [W·m^-2·m^-1]

    # Convert per meter to per nanometer
    E_lambda_per_nm = E_lambda_per_m * 1e-9  # [W·m^-2·nm^-1]

    # Clean up any non-physical values from zero/negative wavelengths
    E_lambda_per_nm = np.where(wl_nm > 0.0, E_lambda_per_nm, 0.0)

    return E_lambda_per_nm


# Parse the data
def load_qe_from_csv(csv_path) -> tuple[np.ndarray, np.ndarray]:
    """
    Read QE curve from a CSV with two columns:
      - wavelength in nm
      - QE in electrons/photon
    Handles optional header rows and comment lines starting with '#'.
    Returns:
      wavelength_nm: (N,) float64
      qe_e_per_photon: (N,) float64
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"QE CSV not found: {csv_path}")

    # Read as two columns; allow an optional header row and comments.
    df = pd.read_csv(
        csv_path,
        comment="#",
        header=None,  # read everything first; we'll clean headers/non-numerics
        names=["wavelength_nm", "qe_e_per_photon"],
        dtype=str,  # read as string, coerce below (robust to odd formatting)
    )

    # Drop non-numeric rows (e.g., header like "wave,qe_mod")
    df = df.apply(pd.to_numeric, errors="coerce").dropna(how="any")

    wavelength_nm = df["wavelength_nm"].to_numpy(dtype=np.float64)
    qe_e_per_photon = df["qe_e_per_photon"].to_numpy(dtype=np.float64)

    # Ensure strictly increasing wavelength order (optional, but nice to have)
    order = np.argsort(wavelength_nm)
    return wavelength_nm[order], qe_e_per_photon[order]


def qe_curve_fit(qe_file_path, solid_angle, pixel_area, wavelength_window=None, show_plots=True):
    wavelength_nm, qe = load_qe_from_csv(qe_file_path)
    print("Generating a qe curve fit with data in " + str(qe_file_path))

    if wavelength_window is not None and len(wavelength_window) == 2:
        print("Applying wavelength window : " + str(wavelength_window))
        mask_low = wavelength_nm > wavelength_window[0]
        wavelength_nm = wavelength_nm[mask_low]
        qe = qe[mask_low]
        mask_high = wavelength_nm < wavelength_window[1]
        wavelength_nm = wavelength_nm[mask_high]
        qe = qe[mask_high]
    # solar radiation intensity using black body radiation
    irr_wl_nm = np.copy(wavelength_nm)
    irr_interp = _solar_irradiance_planck_nm(irr_wl_nm)
    irr_val = np.copy(irr_interp)

    # Convert irradiance (W·m⁻²·nm⁻¹) to radiance (W·sr⁻¹·m⁻²·nm⁻¹) by dividing by pi
    radiance_per_nm = irr_interp / np.pi

    # Photon energy at each wavelength
    photon_energy = h * c / (1e-9 * wavelength_nm)  # Joules

    # Power per wavelength (W/nm)
    power_lambda = solid_angle * pixel_area * radiance_per_nm  # W/nm

    # Number of photons per wavelength = power / photon energy (photons/s/m)
    photons_lambda = power_lambda / photon_energy

    # Calculate electrons per wavelength
    electrons_lambda = photons_lambda * qe
    # Numerical integration using Simpson's rule
    mask = (wavelength_nm >= wavelength_nm[0]) & (wavelength_nm <= wavelength_nm[-1])
    integral_value = simps(electrons_lambda[mask], wavelength_nm[mask])

    if show_plots:
        print(
            f"Integral of electrons per wavelength from {wavelength_nm[0]:.1f} to {wavelength_nm[-1]:.1f} nm: {integral_value:.4e} (total electrons)"
        )

    # Define the 3-variable function to minimize
    def fit_three_wavelengths(sample_wl):
        # Interpolate irradiance and QE at these wavelengths
        irr_sample = np.interp(sample_wl, irr_wl_nm, irr_val)
        qe_sample = np.interp(sample_wl, wavelength_nm, qe)

        # Convert irradiance to radiance
        radiance_sample = irr_sample / np.pi  # W·m⁻²·sr⁻¹·nm⁻¹

        # Photon energy
        photon_energy_sample = h * c / (1e-9 * sample_wl)  # Joules

        # Power per wavelength
        power_sample = solid_angle * pixel_area * radiance_sample  # W/nm

        # Photon rate per wavelength
        photons_sample = power_sample / photon_energy_sample  # photons/nm

        # Electrons per wavelength
        electrons_sample = photons_sample * qe_sample

        # ---- Quadratic interpolant ----
        # Fit a quadratic polynomial (degree=2) through the three points
        coeffs = np.polyfit(sample_wl, electrons_sample, 2)  # returns [a, b, c]
        poly = np.poly1d(coeffs)

        # Fine wavelength grid for plotting the interpolant
        wl_fine = np.linspace(wavelength_nm[0], wavelength_nm[1], 300)
        electrons_fine = poly(wl_fine)

        # ---- Simpson's 1/3 rule ----
        # spacing is spacing between sample_wl points (should be uniform)
        spacing = sample_wl[2] - sample_wl[0]  # should be 200 nm here
        simpson_integral = (spacing / 6) * (electrons_sample[0] + 4 * electrons_sample[1] + electrons_sample[2])

        simpson_error = np.abs((simpson_integral - integral_value) / integral_value) * 100
        return simpson_error

    # Define an initial guess and bounds for the variables
    initial_guess = np.array([wavelength_nm[0], (wavelength_nm[0] + wavelength_nm[-1]) / 2, wavelength_nm[-1]])
    bounds = (
        (wavelength_nm[0], wavelength_nm[-1]),
        (wavelength_nm[0], wavelength_nm[-1]),
        (wavelength_nm[0], wavelength_nm[-1]),
    )

    def eq_constraint(wavelengths):
        return wavelengths[1] - (wavelengths[2] + wavelengths[0]) / 2

    def ineq_constraint_1(wavelengths):
        return wavelengths[1] - wavelengths[0] - 1

    def ineq_constraint_2(wavelengths):
        return wavelengths[2] - wavelengths[1] - 1

    constrs = [
        {"type": "ineq", "fun": ineq_constraint_1},
        {"type": "ineq", "fun": ineq_constraint_2},
        {"type": "eq", "fun": eq_constraint},
    ]

    # Run basinhopping with SLSQP as the local optimizer
    minimizer_kwargs = {"method": "SLSQP", "bounds": bounds, "constraints": constrs}
    result = basinhopping(fit_three_wavelengths, initial_guess, minimizer_kwargs=minimizer_kwargs, niter=100, seed=123)

    if show_plots:
        print(f"Optimal variables: {result.x}")
        print(f"Minimum function value: {result.fun}")
        print(f"Optimization successful: {result.success}")

    # get electrons/nm at fitted wavelength
    # Three wavelengths for sampling
    sample_wl = np.array(result.x)  # nm

    # Interpolate irradiance and QE at these wavelengths
    irr_sample = np.interp(sample_wl, irr_wl_nm, irr_val)
    qe_sample = np.interp(sample_wl, wavelength_nm, qe)

    # Convert irradiance to radiance
    radiance_sample = irr_sample / np.pi  # W·m⁻²·sr⁻¹·nm⁻¹

    # Photon energy
    photon_energy_sample = h * c / (1e-9 * sample_wl)  # Joules

    # Power per wavelength
    power_sample = solid_angle * pixel_area * radiance_sample  # W/nm

    # Photon rate per wavelength
    photons_sample = power_sample / photon_energy_sample  # photons/nm

    # Electrons per wavelength
    electrons_sample = photons_sample * qe_sample

    # ---- Quadratic interpolant ----
    # Fit a quadratic polynomial (degree=2) through the three points
    coeffs = np.polyfit(sample_wl, electrons_sample, 2)  # returns [a, b, c]
    poly = np.poly1d(coeffs)

    # Fine wavelength grid for plotting the interpolant
    wl_fine = np.linspace(wavelength_nm[0], wavelength_nm[-1], 300)
    electrons_fine = poly(wl_fine)

    # ---- Simpson's 1/3 rule ----
    # spacing is spacing between sample_wl points (should be uniform)
    spacing = sample_wl[2] - sample_wl[0]  # should be 200 nm here
    simpson_integral = (spacing / 6) * (electrons_sample[0] + 4 * electrons_sample[1] + electrons_sample[2])

    simpson_error = np.abs((simpson_integral - integral_value) / integral_value) * 100

    corrected_actual_color = (integral_value / 10e4) ** (1 / 2.2)
    corrected_estimate_color = (simpson_integral / 10e4) ** (1 / 2.2)

    if show_plots:
        print("Electrons at sample points:")
        for wl, val in zip(sample_wl, electrons_sample):
            print(f"  λ = {wl:.1f} nm: {val:.4e} electrons/nm")

        print(
            f"\nSimpson's 1/3 rule integral estimate: {simpson_integral:.4e} electrons (over {wavelength_nm[0]:.1f} nm to {wavelength_nm[-1]:.1f} nm"
        )
        print(f"Error from actual: {simpson_error:.2f}%")
        print(f"\nGrayscale actual color: {corrected_actual_color:.2f}")
        print(f"Grayscale approx color: {corrected_estimate_color:.2f}")

    # ---- Plot ----
    plt.figure(figsize=(10, 6))
    plt.plot(wavelength_nm, electrons_lambda, "k--", alpha=0.3, label="Actual electrons per wavelength (ref)")
    plt.plot(wl_fine, electrons_fine, "b-", label="Quadratic interpolant (electrons)")
    plt.scatter(sample_wl, electrons_sample, color="red", zorder=5, label="Sample points")
    plt.xlabel("Wavelength (nm)")
    plt.ylabel("Electrons / nm")
    plt.title("Estimated vs actual electrons per wavelength")
    plt.legend()
    plt.ylim(0, np.max(electrons_lambda) * 1.1)
    plt.grid(True)

    fit_wavelengths = np.array(result.x)
    # interpolate to get the qe values (in the loaded qe_file_path: wavelength_nm, qe) corresponding to the fit_wavelengths
    fit_qe = np.interp(fit_wavelengths, wavelength_nm, qe)

    if show_plots:
        plt.show()
        print(fit_wavelengths, fit_qe)

    return fit_wavelengths, fit_qe


def main():
    # Parameters to modify
    solid_angle = pi * 0.005**2 / (0.16**2)  # steradians
    pixel_area = (0.022528 * 0.016896) / (4096 * 3072)  # m^2
    qe_file_path = Path(__file__).resolve().parent.parent / "support-data/deimos-spice/qe-mod-5.csv"
    qe_curve_fit(qe_file_path, solid_angle, pixel_area, show_plots=True)


if __name__ == "__main__":
    main()
