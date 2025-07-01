from numpy import ndarray

import context
from driver import *
from launcher import *
from context import cielimMessage_pb2
from context import scene
import matplotlib.pyplot as plt
import matplotlib
from context import rigid_body_kinematics as rbk
import numpy as np
from orbital_motion import ClassicOrbitalElements
import os
import json
import cv2
import re

matplotlib.rcParams.update({"font.size": 6})
colorsInt = len(matplotlib.colormaps["inferno"].colors) / (10.0)
colorList = []
for i in range(10):
    colorList.append(matplotlib.colormaps["inferno"].colors[int(i * colorsInt)])

current_file_path = os.path.dirname(__file__)


def tryint(s: str):
    """
    Attempt to turn a string into an int
    """
    try:
        return int(s)
    except:
        return s


def alphanum_key(s: str) -> list:
    """
    Turn a string into a list of string and number chunks.
    """
    return [tryint(c) for c in re.split("(\d+)", s)]


def compute_analytical_std(
    asteroid_radius: float, radius_std: float, position_N: list, position_std: float, s_hat: list, phase_angle: float
) -> float:
    """
    Compute analytical standard deviations for a given geometry
    """
    r_norm = np.linalg.norm(position_N)
    r_hat = position_N / r_norm

    delta_alpha_delta_r = np.dot(s_hat / (r_norm), np.eye(3) - np.outer(r_hat, r_hat))

    constants_delta_r = (
        4
        * asteroid_radius
        / (3 * np.pi * r_norm)
        * (1 - np.cos(phase_angle))
        / (1 + (4 * asteroid_radius / (3 * np.pi * r_norm) * (1 - np.cos(phase_angle))) ** 2)
    )

    delta_correction_delta_r = -r_hat / r_norm * constants_delta_r
    delta_correction_delta_radius = constants_delta_r / asteroid_radius
    delta_correction_delta_alpha = (
        4
        * asteroid_radius
        / (3 * np.pi * r_norm)
        / (1 + (4 * asteroid_radius / (3 * np.pi * r_norm) * (1 - np.cos(phase_angle))) ** 2)
    )

    d_r = delta_correction_delta_r + delta_correction_delta_alpha * delta_alpha_delta_r

    position_uncertainty = np.diag([position_std**2] * 3)
    return (delta_correction_delta_radius * radius_std) ** 2 + np.dot(np.dot(d_r, position_uncertainty), d_r.T)


def write_annotated_image(img, data_dict: dict, predicted_com: list, image_name, results_directory: str):
    """
    Read an image and write it back out to the results directory with annotations
    """
    _, width, _ = img.shape
    cv2.drawMarker(
        img,
        [round(x) for x in data_dict["center_of_brightness"]],
        color=[0, 250, 0],
        thickness=2,
        markerType=cv2.MARKER_TILTED_CROSS,
        line_type=cv2.LINE_AA,
        markerSize=6,
    )
    cv2.putText(
        img, "Center of Brightness", (width - 350, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 250, 0), 2, cv2.LINE_AA
    )
    cv2.drawMarker(
        img,
        [round(x) for x in predicted_com],
        color=[0, 0, 250],
        thickness=2,
        markerType=cv2.MARKER_TILTED_CROSS,
        line_type=cv2.LINE_AA,
        markerSize=6,
    )
    cv2.putText(img, "Predicted CoM", (width - 350, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 250), 2, cv2.LINE_AA)
    cv2.drawMarker(
        img,
        [round(x) for x in data_dict["center_of_mass"]],
        color=[250, 0, 0],
        thickness=2,
        markerType=cv2.MARKER_TILTED_CROSS,
        line_type=cv2.LINE_AA,
        markerSize=6,
    )
    cv2.putText(img, "True CoM", (width - 350, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (250, 0, 0), 2, cv2.LINE_AA)
    cv2.imwrite(results_directory + "/annotated-" + image_name, img)


def cob_offset_binary(phase_angle: float) -> float:
    """
    Computes COB correction due to solar phase angle assuming brightness is either 0 (shaded) or 1 (sunlit)
    Returns a normalized correction factor
    """

    gamma = 4 / (3 * np.pi) * (1 - np.cos(phase_angle))

    return gamma


def com_cob_analysis(directory_path: str, show_plots: bool):
    """
    Read a folder of images containing image data from the random_asteroid_generation.py script.
    Analyse the center of mass and center and predicted center of mass correction errors.
    Output plots and images post analysis.
    """
    images = []
    for filename in sorted(os.listdir(directory_path), key=alphanum_key):
        if filename.endswith(".png"):
            images.append(filename)

    results = os.path.dirname(directory_path) + "/" + os.path.basename(directory_path) + "-analysis"
    os.makedirs(results, exist_ok=True)
    correction_errors_arcsec = []
    phase_angles = []
    sun_headings = []
    for image in images:
        data_file = image.split(".")[0] + ".json"
        with open(directory_path + "/" + data_file, "r") as file:
            data_dict = json.load(file)

        # Get CoM estimate
        phase_angles.append(data_dict["phase_angle"])
        sun_headings.append(data_dict["sun_heading_N"])
        gamma = cob_offset_binary(data_dict["phase_angle"])
        correction_angle = np.arctan2(data_dict["sun_heading_C"][1], data_dict["sun_heading_C"][0])
        asteroid_mean_radius_rad = np.arcsin(
            data_dict["asteroid_mean_radius"] / np.linalg.norm(data_dict["mean_position_N"])
        )
        asteroid_mean_radius_pix = asteroid_mean_radius_rad / data_dict["camera_ifov"]

        predicted_com = np.zeros(2)
        predicted_com[0] = data_dict["center_of_brightness"][0] - gamma * asteroid_mean_radius_pix * np.cos(
            correction_angle
        )
        predicted_com[1] = data_dict["center_of_brightness"][1] - gamma * asteroid_mean_radius_pix * np.sin(
            correction_angle
        )

        true_offset = (
            np.linalg.norm(np.array(data_dict["center_of_mass"]) - np.array(data_dict["center_of_brightness"]))
            * data_dict["camera_ifov"]
        )
        predicted_offset = np.arctan(
            gamma * data_dict["asteroid_mean_radius"] / np.linalg.norm(data_dict["mean_position_N"])
        )
        correction_error_rad = predicted_offset - true_offset
        correction_errors_arcsec.append(correction_error_rad * 180 / np.pi * 3600)

        img = cv2.imread(directory_path + "/" + image)
        write_annotated_image(img, data_dict, predicted_com, image, results)

    phases = np.array(phase_angles)
    errors_arcsec = np.abs(correction_errors_arcsec)
    indices = phases.argsort()
    analytical_errors_arcsec = []
    numerical_errors_arcsec = []
    old_variance = 0
    old_mean = 0
    n = 0
    for phase, sun_heading in zip(phases[indices], np.array(sun_headings)[indices]):
        n += 1
        analytical_std_arcsec = (
            np.sqrt(
                compute_analytical_std(
                    data_dict["asteroid_mean_radius"],
                    data_dict["asteroid_std_radius"],
                    data_dict["mean_position_N"],
                    data_dict["position_std"],
                    sun_heading,
                    phase,
                )
            )
            * 180
            / np.pi
            * 3600
        )
        analytical_errors_arcsec.append(analytical_std_arcsec)

        index = indices[n - 1]
        new_mean = old_mean + (correction_errors_arcsec[index] - old_mean) / n
        new_variance = (
            (n - 1) * old_variance
            + (correction_errors_arcsec[index] - old_mean) * (correction_errors_arcsec[index] - new_mean)
        ) / n
        old_mean = new_mean
        old_variance = new_variance

        numerical_errors_arcsec.append(np.sqrt(new_variance))

    analytical_std_mean = np.mean(analytical_errors_arcsec)

    # If images were processed plot the data
    if len(images) > 0:
        plt.figure(facecolor="w", edgecolor="k", figsize=(5, 3), dpi=200)
        plt.scatter(phases[indices] * 180 / np.pi, errors_arcsec[indices], marker=".", s=10, color=colorList[1])
        plt.plot(
            phases[indices] * 180 / np.pi,
            2 * np.array(numerical_errors_arcsec),
            linestyle="-.",
            linewidth=1,
            color=colorList[7],
            label="2-$\sigma$ numerical",
        )
        plt.plot(
            phases[indices] * 180 / np.pi,
            2 * np.array(analytical_errors_arcsec),
            linestyle="--",
            linewidth=1,
            color=colorList[5],
            label="2-$\sigma$ analytical",
        )
        plt.plot(
            phases[indices] * 180 / np.pi,
            np.ones(len(phases)) * data_dict["camera_ifov"] * 180 / np.pi * 3600,
            linewidth=1,
            linestyle=":",
            color=colorList[9],
            label="pixel ifov",
        )
        plt.title(r"Correction error as a function of phase angle")
        plt.xlabel(r"Phase angle (deg)")
        plt.ylabel(r"Correction error (arcsec)")
        plt.legend()
        plt.savefig(results + "/error-by-phase.png")

        plt.figure(facecolor="w", edgecolor="k", figsize=(5, 3), dpi=200)
        plt.hist(correction_errors_arcsec, bins=101, color=colorList[1])
        plt.axvline(
            2 * np.std(correction_errors_arcsec),
            color=colorList[9],
            linewidth=2,
            linestyle="dashed",
            label="2-$\sigma$ numerical",
        )
        plt.axvline(
            -2 * np.std(correction_errors_arcsec),
            color=colorList[9],
            linewidth=2,
            linestyle="dashed",
        )
        plt.axvline(
            2 * analytical_std_mean,
            color=colorList[7],
            linewidth=2,
            linestyle="dashed",
            label="2-$\sigma$ analytical",
        )
        plt.axvline(
            -2 * analytical_std_mean,
            color=colorList[7],
            linewidth=2,
            linestyle="dashed",
        )
        plt.gca().ticklabel_format(axis="x", style="sci", scilimits=(0, 0))
        plt.title(r"Correction error histogram and statistics")
        plt.xlabel("Error from $\sigma_R$ (arcsec)")
        plt.ylabel("Number of runs")
        plt.legend()
        plt.savefig(results + "/cob-com-correction-errors.png")
        if show_plots:
            plt.show()


if __name__ == "__main__":
    directory_path = current_file_path + "/images-com-cob"
    show_plots = True
    com_cob_analysis(directory_path, show_plots)
