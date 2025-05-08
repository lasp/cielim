import saved_monte_carlo_scenario
import image_analysis
import spice_scenario
import print_protobuffer_content
import os, shutil
import subprocess

def test_run_saved_monte_carlo_scenario():
    saved_monte_carlo_scenario.saved_monte_carlo_scenario()
    assert os.path.exists("saved_monte_carlo_images")
    image_analysis.data_analysis(False)
    assert os.path.exists("coverage.png")
    shutil.rmtree("saved_monte_carlo_images")
    os.remove("coverage.png")

def test_run_spice_scenario():
    spice_scenario.spice_scenario()
    assert os.path.exists("cassini-images")
    shutil.rmtree("cassini-images")

def test_run_print_protobuffer_content():
    print_protobuffer_content.print_protobuffer_content()
    assert os.path.exists("bennu_image_decoded.txt")
    os.remove("bennu_image_decoded.txt")

def test_run_send_protobuffer_file():
    subprocess.run(["python3", "send_protobuffer_file.py", "--filename", "bennu_image.bin", "--hide_image"])
    assert os.path.exists("received_image_0.png")
    os.remove("received_image_0.png")