import os
import cv2
import matplotlib.pyplot as plt
import numpy as np

current_file_path = os.path.dirname(__file__)


def list_files_alphabetically(directory: str) -> list:
    """method to read files from directory assuming an alphabetical/chronological naming convention"""
    files = os.listdir(directory)
    files = [f for f in files if (os.path.isfile(os.path.join(directory, f)) and f[0] != ".")]
    files.sort()
    return files


def analysis_function(img: np.ndarray, top_left: list, size: list) -> float:
    """perform analysis on an image and return a metric to be plotted"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresholded_image = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)[1]  # Adjust threshold value as needed
    total_bright_pixels = cv2.countNonZero(thresholded_image)

    # Define the region of interest (ROI) coordinates
    x_start, y_start = int(top_left[0]), int(top_left[1])  # Top-left corner coordinates
    width, height = int(size[0]), int(size[1])  # Width and height of the ROI
    cropped_image = thresholded_image[y_start : y_start + height, x_start : x_start + width]
    bright_pixels_fov = cv2.countNonZero(cropped_image)

    if total_bright_pixels != 0:
        return bright_pixels_fov / total_bright_pixels * 100
    else:
        return np.nan


def data_analysis(show_plots=True):
    """Example script to read and process images from a directory"""
    folder = current_file_path + "/images-saved-monte-carlo"

    # Define some image parameters for the analysis
    image_resolution = [2000, 1500]
    image_fov = [40, 30]
    target_fov = [15, 15]
    center = [round(image_resolution[0] / 2), round(image_resolution[1] / 2)]

    top_left = [
        center[0] - image_resolution[0] * target_fov[0] / image_fov[0] / 2,
        center[1] - image_resolution[1] * target_fov[1] / image_fov[1] / 2,
    ]
    size = [image_resolution[0] * target_fov[0] / image_fov[0], image_resolution[1] * target_fov[1] / image_fov[1]]

    # Loop through the images in order and run analysis function on each
    data = {}
    time = []
    images = list_files_alphabetically(folder)
    for filename in images:
        image_information = filename.split(".")[0].split("-")
        img = cv2.imread(os.path.join(folder, filename))
        metric = analysis_function(img, top_left, size)

        if int(image_information[1]) == 0:
            time.append(float(image_information[3]) / 60)
        if float(image_information[3]) == 0.0:
            data[image_information[0] + image_information[1]] = []
        data[image_information[0] + image_information[1]].append(metric)

    # If images were processed plot the data
    if len(images) > 0:
        plt.figure()
        for key, values in data.items():
            plt.plot(time, values, label=key)
        plt.title(r"Sub-FOV Coverage of Target")
        plt.xlabel(r"Time (min)")
        plt.ylabel(r"Coverage (%)")
        plt.legend()
        plt.savefig(current_file_path + "/coverage.png")
        if show_plots:
            plt.show()


if __name__ == "__main__":
    data_analysis(True)
