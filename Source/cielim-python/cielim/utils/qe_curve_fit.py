from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, ScalarFormatter
import numpy as np
import pandas as pd
from scipy.integrate import simpson
from scipy.optimize import basinhopping

from ..cielimMessage_pb2 import CielimMessage
from . import plot_style

# Constants
figure_px = 1024

# Where set_qe_curve_fit writes its figure. Not gitignored, unlike examples/images*, so these are
# committable alongside the paper.
figure_directory = Path(__file__).resolve().parents[2] / "docs" / "figures"

# Three inferno-sampled series; plot_style.series_colors only holds two. CVD-checked.
series_colors_3 = (mpl.cm.inferno(0.38), mpl.cm.inferno(0.58), mpl.cm.inferno(0.76))

const_au = 1.495978707e11  # Astronomical Unit in meters
const_c = 299792458  # Speed of light, m/s
const_h = 6.62607015e-34  # Planck constant, J·s
const_k = 1.380649e-23  # Boltzmann constant, J/K


def _solar_irradiance_planck_nm(wavelengths: np.ndarray, temp: float = 5772.0, radius: float = 6.957e8) -> np.ndarray:
    """
    Compute solar spectral irradiance at 1 AU from a blackbody Sun.

    Args:
        wavelengths (np.ndarray): Wavelengths in nanometers.
        temp (float): Effective blackbody temperature of the sun in Kelvin.
        radius (float): Radius of the Sun in meters.

    Returns:
        np.ndarray: Spectral irradiance at 1 AU in W·m^-2·nm^-1, same shape as wavelength.
    """
    wl_nm = np.asarray(wavelengths, dtype=np.float64)
    wl_m = wl_nm * 1e-9  # convert nm -> m

    # Planck spectral radiance per unit wavelength (per meter): B_λ [W·m^-2·sr^-1·m^-1]
    # Use expm1 for numerical stability.
    x = (const_h * const_c) / (wl_m * const_k * temp)
    B_lambda_per_m = (2.0 * const_h * const_c**2) / (wl_m**5) / np.expm1(x)

    # Radiance -> surface flux per wavelength: F_λ = π B_λ  [W·m^-2·m^-1]
    F_lambda_per_m = np.pi * B_lambda_per_m

    # Geometric dilution to 1 AU: multiply by (R_sun / AU)^2
    dilution = (radius / const_au) ** 2
    E_lambda_per_m = F_lambda_per_m * dilution  # [W·m^-2·m^-1]

    # Convert per meter to per nanometer
    E_lambda_per_nm = E_lambda_per_m * 1e-9  # [W·m^-2·nm^-1]

    # Clean up any non-physical values from zero/negative wavelengths
    E_lambda_per_nm = np.where(wl_nm > 0.0, E_lambda_per_nm, 0.0)

    return E_lambda_per_nm


def load_qe_from_csv(csv_path: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Read QE curve from a CSV with two columns:
      - wavelength in nm
      - QE in electrons/photon
    Handles optional header rows and comment lines starting with '#'.

    Args:
        csv_path (str): Path to the CSV file.

    Returns:
        tuple[np.ndarray, np.ndarray]: Wavelengths (nm) and QE values (electrons/photon).
    """
    path = Path(csv_path)

    if not path.exists():
        raise FileNotFoundError(f"QE CSV not found: {csv_path}")

    # Read as two columns; allow an optional header row and comments.
    df = pd.read_csv(
        path,
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


def qe_curve_fit(
    qe_file_path: str,
    solid_angle: float,
    pixel_area: float,
    wavelength_window: list | None = None,
    show_plots: bool = True,
    output_path: str | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    A function to fit a QE curve to three wavelengths that minimize the error in the integral of electrons per wavelength.

    Args:
        qe_file_path (str): Path to the QE CSV file.
        solid_angle (float): Solid angle in steradians.
        pixel_area (float): Pixel area in square meters.
        wavelength_window (list, optional): Two-element list specifying the wavelength range to consider (in nm). Defaults to None (use full range).
        show_plots (bool, optional): Whether to display plots of the QE curve and fit. Defaults to True.
        output_path (str, optional): Base path for the PDF. The measured area error is appended to
            the stem, so 'qe_fit_x.pdf' is written as 'qe_fit_x_err0p42pct.pdf'. None skips saving.

    Returns:
        tuple[np.ndarray, np.ndarray]: Fitted wavelengths (nm) and corresponding QE values (electrons/photon).
    """
    wavelength_nm, qe = load_qe_from_csv(qe_file_path)

    print("Generating a qe curve fit with data in " + str(qe_file_path))

    if wavelength_window is not None and len(wavelength_window) == 2:
        print("Applying wavelength window : " + str(wavelength_window))
        mask_low = wavelength_nm >= wavelength_window[0]
        wavelength_nm = wavelength_nm[mask_low]
        qe = qe[mask_low]
        mask_high = wavelength_nm <= wavelength_window[1]
        wavelength_nm = wavelength_nm[mask_high]
        qe = qe[mask_high]

    # solar radiation intensity using black body radiation
    irr_wl_nm = np.copy(wavelength_nm)

    irr_interp = _solar_irradiance_planck_nm(irr_wl_nm)

    irr_val = np.copy(irr_interp)

    # Convert irradiance (W·m⁻²·nm⁻¹) to radiance (W·sr⁻¹·m⁻²·nm⁻¹) by dividing by pi
    radiance_per_nm = irr_interp / np.pi

    # Photon energy at each wavelength
    photon_energy = const_h * const_c / (1e-9 * wavelength_nm)  # Joules

    # Power per wavelength (W/nm)
    power_lambda = solid_angle * pixel_area * radiance_per_nm  # W/nm

    # Number of photons per wavelength = power / photon energy (photons/s/m)
    photons_lambda = power_lambda / photon_energy

    # Calculate electrons per wavelength
    electrons_lambda = photons_lambda * qe

    # Numerical integration using Simpson's rule
    mask = (wavelength_nm >= wavelength_nm[0]) & (wavelength_nm <= wavelength_nm[-1])
    integral_value = simpson(electrons_lambda[mask], wavelength_nm[mask])

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
        photon_energy_sample = const_h * const_c / (1e-9 * sample_wl)  # Joules

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
    result = basinhopping(fit_three_wavelengths, initial_guess, minimizer_kwargs=minimizer_kwargs, niter=100)

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
    photon_energy_sample = const_h * const_c / (1e-9 * sample_wl)  # Joules

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

    plot_style.apply_showcase_style()
    side_in = figure_px / plot_style.save_dpi  # square, 1024 px on a side at the save dpi
    figure, axes = plt.subplots(figsize=(side_in, side_in))

    # Bare panel: actual electrons, the 3-point Simpson fit, and the fitted sample wavelengths.
    reference_color, fit_color, sample_color = series_colors_3
    axes.plot(wavelength_nm, electrons_lambda, color=reference_color, linewidth=1.4)
    axes.plot(wl_fine, electrons_fine, color=fit_color, linewidth=1.4)
    axes.scatter(sample_wl, electrons_sample, color=sample_color, zorder=5, s=36)

    axes.set_ylim(0, np.max(electrons_lambda) * 1.1)
    axes.set_xlabel("Wavelength (nm)")
    axes.set_ylabel("Electrons / nm")

    # powerlimits (0, 0) forces the scientific form at every scale: left to itself matplotlib
    # switches styles with the magnitude, so figures from different cameras could not be compared.
    formatter = ScalarFormatter(useMathText=True)
    formatter.set_scientific(True)
    formatter.set_powerlimits((0, 0))
    axes.yaxis.set_major_formatter(formatter)
    axes.yaxis.set_major_locator(MaxNLocator(nbins=5))

    axes.spines["top"].set_visible(False)
    for side in ("left", "bottom", "right"):
        axes.spines[side].set_linewidth(0.6)
        axes.spines[side].set_color("0.6")

    fit_wavelengths = np.array(result.x)

    # interpolate to get the qe values (in the loaded qe_file_path: wavelength_nm, qe) corresponding to the fit_wavelengths
    fit_qe = np.interp(fit_wavelengths, wavelength_nm, qe)

    if output_path is not None:
        figure.tight_layout()
        # The measured area error is stamped into the stem, since the figure no longer carries it.
        # "0p00" not "0.00": a second dot in the stem makes LaTeX guess at the extension, and these
        # go straight into the paper.
        base = Path(output_path)
        error_tag = f"{simpson_error:.2f}".replace(".", "p")
        output_path = base.with_name(f"{base.stem}_err{error_tag}pct{base.suffix}")
        plot_style.save_figure(figure, str(output_path))
        if show_plots:
            print(f"Saved QE fit figure -> {output_path}")

    if show_plots:
        plt.show()
        print(fit_wavelengths, fit_qe)
    else:
        plt.close(figure)

    return fit_wavelengths, fit_qe


def set_qe_curve_fit(
    message: CielimMessage,
    qe_data_path: str,
    solid_angle: float,
    pixel_area: float,
    wavelength_window: list | None = None,
    figure_name: str | None = None,
) -> None:
    """
    Sets the wavelengths and QE values in the CielimMessage based on a QE curve fit from a CSV file.

    Args:
        message (CielimMessage): The CielimMessage to update.
        qe_data_path (str): Path to the QE CSV file.
        solid_angle (float): Solid angle in steradians.
        pixel_area (float): Pixel area in square meters.
        wavelength_window (list, optional): Two-element list specifying the wavelength range to consider (in nm). Defaults to None (use full range).
        figure_name (str, optional): Stem for the PDF written into docs/figures/. Defaults to the QE
            file's own stem — pass an explicit name when two callers share a QE file but differ in
            optics, or the second one silently overwrites the first's figure.
    """
    figure_path = figure_directory / f"{figure_name or Path(qe_data_path).stem}.pdf"
    fit_wavelengths, fit_values = qe_curve_fit(
        qe_data_path,
        solid_angle,
        pixel_area,
        wavelength_window=wavelength_window,
        show_plots=False,
        output_path=str(figure_path),
    )

    message.renderParameters.wavelength1 = fit_wavelengths[0]
    message.renderParameters.wavelength2 = fit_wavelengths[1]
    message.renderParameters.wavelength3 = fit_wavelengths[2]

    message.camera.sensorModel.qeCurve.redValue1 = fit_values[0]
    message.camera.sensorModel.qeCurve.greenValue1 = fit_values[0]
    message.camera.sensorModel.qeCurve.blueValue1 = fit_values[0]
    message.camera.sensorModel.qeCurve.redValue2 = fit_values[1]
    message.camera.sensorModel.qeCurve.greenValue2 = fit_values[1]
    message.camera.sensorModel.qeCurve.blueValue2 = fit_values[1]
    message.camera.sensorModel.qeCurve.redValue3 = fit_values[2]
    message.camera.sensorModel.qeCurve.greenValue3 = fit_values[2]
    message.camera.sensorModel.qeCurve.blueValue3 = fit_values[2]


if __name__ == "__main__":
    # Parameters to modify
    solid_angle = np.pi * 0.005**2 / (0.16**2)  # steradians
    pixel_area = (0.022528 * 0.016896) / (4096 * 3072)  # m^2
    qe_file_path = str(Path(__file__).resolve().parents[2] / "support-data/deimos-spice/qe-mod-5.csv")

    # Same window deimos_flyby.py uses for F635, or this writes a full-spectrum fit under that name.
    f635_window = [625, 645]

    qe_curve_fit(
        qe_file_path,
        solid_angle,
        pixel_area,
        wavelength_window=f635_window,
        show_plots=True,
        output_path=str(figure_directory / "qe_fit_deimos_f635.pdf"),
    )
