import saved_monte_carlo_scenario
import image_analysis
import spice_scenario
import print_protobuffer_content
import os, shutil
import subprocess
current_file_path = os.path.dirname(__file__)

def test_run_saved_monte_carlo_scenario():
    saved_monte_carlo_scenario.saved_monte_carlo_scenario()
    assert os.path.exists(current_file_path + "/saved_monte_carlo_images")
    image_analysis.data_analysis(False)
    assert os.path.exists(current_file_path + "/coverage.png")
    shutil.rmtree(current_file_path + "/saved_monte_carlo_images")
    os.remove(current_file_path + "/coverage.png")

def test_run_spice_scenario():
    spice_scenario.spice_scenario()
    assert os.path.exists(current_file_path + "/cassini-images")
    shutil.rmtree(current_file_path + "/cassini-images")

def test_run_print_protobuffer_content():
    print_protobuffer_content.print_protobuffer_content()
    assert os.path.exists(current_file_path + "/bennu_image_decoded.txt")
    os.remove(current_file_path + "/bennu_image_decoded.txt")

def test_run_send_protobuffer_file():
    subprocess.run(["python3", current_file_path + "/send_protobuffer_file.py", "--filename", "bennu_image.bin", "--hide_image"])
    assert os.path.exists(current_file_path + "/received_image_0.png")
    os.remove(current_file_path + "/received_image_0.png")