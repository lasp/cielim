import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"


def _load_module_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_random_asteroid_generation(monkeypatch):
    # headless plotting
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Load modules directly from files (no need for examples/__init__.py)
    rag = _load_module_from(EXAMPLES_DIR / "random_asteroid_generation.py", "random_asteroid_generation")
    cca = _load_module_from(EXAMPLES_DIR / "com_cob_analysis.py", "com_cob_analysis")

    # Figure out where the example writes (module usually defines current_file_path = os.path.dirname(__file__))
    base_dir = Path(getattr(rag, "current_file_path", EXAMPLES_DIR))

    gen_dir = base_dir / "images-com-cob"
    out_dir = base_dir / "images-com-cob-analysis"

    # Ensure a clean slate
    if gen_dir.exists():
        shutil.rmtree(gen_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)

    # 1) Generate a small set of images
    rag.random_asteroid_generation(5)
    np.testing.assert_(gen_dir.exists(), msg="images-com-cob directory was not created")
    np.testing.assert_(any(gen_dir.glob("*.png")), msg="No PNGs produced in images-com-cob")

    # 2) Run CoM/CoB analysis (False to keep it headless)
    cca.com_cob_analysis(str(gen_dir), False)

    # 3) Verify analysis artifacts
    np.testing.assert_((out_dir / "annotated-image-0.png").exists(), msg="annotated-image-0.png missing")
    np.testing.assert_(
        (out_dir / "cob-com-correction-errors.png").exists(), msg="cob-com-correction-errors.png missing"
    )
    np.testing.assert_((out_dir / "error-by-phase.png").exists(), msg="error-by-phase.png missing")

    # Cleanup repo tree after assertions
    shutil.rmtree(gen_dir)
    shutil.rmtree(out_dir)


def test_asteroid_departure():
    # headless plotting
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Load modules directly from files (no need for examples/__init__.py)
    dep = _load_module_from(EXAMPLES_DIR / "asteroid_departure.py", "departure_scene")

    # where this example writes outputs (falls back to examples/ if attribute missing)
    base_dir = Path(getattr(dep, "current_file_path", EXAMPLES_DIR))

    out_dir = base_dir / "images-departure"
    bin_file = out_dir / "departure.bin"

    # clean slate
    if out_dir.exists():
        shutil.rmtree(out_dir)

    dep.departure_scene(5)

    # assertions (numpy.testing)
    np.testing.assert_(out_dir.exists(), msg="images-departure directory was not created")
    np.testing.assert_(bin_file.exists(), msg="departure.bin was not created")

    # cleanup
    shutil.rmtree(out_dir)


def test_saved_monte_carlo_scenario():
    # headless plotting
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Load modules directly from files
    smc = _load_module_from(EXAMPLES_DIR / "saved_monte_carlo_scenario.py", "saved_monte_carlo_scenario")
    ia = _load_module_from(EXAMPLES_DIR / "image_analysis.py", "image_analysis")

    # Base dir where the example writes outputs (fallback to examples/)
    base_dir = Path(getattr(smc, "current_file_path", EXAMPLES_DIR))

    mc_dir = base_dir / "images-saved-monte-carlo"
    coverage_png = base_dir / "coverage.png"

    # Clean slate
    if mc_dir.exists():
        shutil.rmtree(mc_dir)
    if coverage_png.exists():
        coverage_png.unlink()

    # 1) Run the saved Monte Carlo scenario
    smc.saved_monte_carlo_scenario()
    np.testing.assert_(mc_dir.exists(), msg="images-saved-monte-carlo directory was not created")

    # 2) Run analysis (False to keep headless), expect coverage.png
    ia.data_analysis(False)
    np.testing.assert_(coverage_png.exists(), msg="coverage.png was not created")

    # Cleanup
    shutil.rmtree(mc_dir)
    coverage_png.unlink()


def test_corto_scenario():
    # headless plotting
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Load modules directly from files
    corto = _load_module_from(EXAMPLES_DIR / "corto_scenario.py", "corto_scenario")

    # Base dir where the example writes outputs (fallback to examples/)
    base_dir = Path(getattr(corto, "current_file_path", EXAMPLES_DIR))

    image_dir = base_dir / "images-corto"

    # Remove previous file
    if image_dir.exists():
        shutil.rmtree(image_dir)

    # Run the scenario
    corto.corto_scenario()
    assert image_dir.exists(), "corto scenario didn't create images"

    shutil.rmtree(image_dir)


def test_spice_scenario():
    # headless plotting
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Require kernels; xfail if not available
    spice_root = PROJECT_ROOT / "support-data" / "cassini-spice.json"
    if not spice_root.exists():
        pytest.xfail(f"Missing SPICE kernels: {spice_root}")

    # Load the example module
    sp = _load_module_from(EXAMPLES_DIR / "spice_scenario.py", "spice_scenario")

    # Output dir lives next to the script by its own logic
    base_dir = Path(getattr(sp, "current_file_path", EXAMPLES_DIR))
    out_dir = base_dir / "images-cassini-spice"

    # clean slate
    if out_dir.exists():
        shutil.rmtree(out_dir)

    # run
    sp.spice_scenario()

    # assert (numpy.testing)
    np.testing.assert_(out_dir.exists(), msg="images-cassini-spice directory was not created")

    # cleanup
    shutil.rmtree(out_dir)


def test_deimos_flyby():
    # headless plotting
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Require kernels; xfail if not available
    spice_root = PROJECT_ROOT / "support-data" / "deimos-spice"
    if not spice_root.exists():
        pytest.skip(f"Missing SPICE kernels: {spice_root}")

    # Load the example module
    df = _load_module_from(EXAMPLES_DIR / "deimos_flyby.py", "spice_scenario")

    # Output dir lives next to the script by its own logic
    base_dir = Path(getattr(df, "current_file_path", EXAMPLES_DIR))
    out_dir = base_dir / "images-deimos-spice"

    # clean slate
    if out_dir.exists():
        shutil.rmtree(out_dir)

    # run
    df.spice_scenario()

    # assert (numpy.testing)
    np.testing.assert_(out_dir.exists(), msg="images-deimos-spice directory was not created")

    # cleanup
    shutil.rmtree(out_dir)


def test_bennu_tag():
    # headless plotting
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Require kernels; xfail if not available
    spice_root = PROJECT_ROOT / "support-data" / "bennu-tag-spice"
    if not spice_root.exists():
        pytest.skip(f"Missing SPICE kernels: {spice_root}")

    # Load the example module
    df = _load_module_from(EXAMPLES_DIR / "bennu_tag_scenario.py", "spice_scenario")

    # Output dir lives next to the script by its own logic
    base_dir = Path(getattr(df, "current_file_path", EXAMPLES_DIR))
    out_dir = base_dir / "images-bennu-tag"

    # clean slate
    if out_dir.exists():
        shutil.rmtree(out_dir)

    # run
    df.tag_scenario(3)

    # assert (numpy.testing)
    np.testing.assert_(out_dir.exists(), msg="images-bennu-tag directory was not created")

    # cleanup
    shutil.rmtree(out_dir)


def test_bennu():
    # headless plotting
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Require kernels; xfail if not available
    spice_root = PROJECT_ROOT / "support-data" / "bennu-spice"
    if not spice_root.exists():
        pytest.skip(f"Missing SPICE kernels: {spice_root}")

    # Load the example module
    df = _load_module_from(EXAMPLES_DIR / "bennu_scenario.py", "spice_scenario")

    # Output dir lives next to the script by its own logic
    base_dir = Path(getattr(df, "current_file_path", EXAMPLES_DIR))
    out_dir = base_dir / "images-bennu"

    # clean slate
    if out_dir.exists():
        shutil.rmtree(out_dir)

    # run
    df.bennu_scenario(3)

    # assert (numpy.testing)
    np.testing.assert_(out_dir.exists(), msg="images-bennu directory was not created")

    # cleanup
    shutil.rmtree(out_dir)


def test_vesta():
    # headless plotting
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Require kernels; xfail if not available
    spice_root = PROJECT_ROOT / "support-data" / "vesta-spice"
    if not spice_root.exists():
        pytest.skip(f"Missing SPICE kernels: {spice_root}")

    # Load the example module
    df = _load_module_from(EXAMPLES_DIR / "vesta_scenario.py", "spice_scenario")

    # Output dir lives next to the script by its own logic
    base_dir = Path(getattr(df, "current_file_path", EXAMPLES_DIR))
    out_dir = base_dir / "images-vesta"

    # clean slate
    if out_dir.exists():
        shutil.rmtree(out_dir)

    # run
    df.vesta_scenario(3)

    # assert (numpy.testing)
    np.testing.assert_(out_dir.exists(), msg="images-vesta directory was not created")

    # cleanup
    shutil.rmtree(out_dir)


def test_print_protobuffer_content():
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Load the example module
    ppc = _load_module_from(EXAMPLES_DIR / "print_protobuffer_content.py", "print_protobuffer_content")

    # Inputs live under project support-data
    test_dir = PROJECT_ROOT / "support-data" / "protobufs"
    file_name = "bennu_image.bin"
    infile = test_dir / file_name
    if not infile.exists():
        pytest.xfail(f"Missing {infile}")

    # The example does string concatenation, so ensure trailing separator
    test_dir_str = str(test_dir)
    if not test_dir_str.endswith(os.sep):
        test_dir_str += os.sep

    # Output is written next to the script (by its own logic)
    base_dir = Path(getattr(ppc, "current_file_path", EXAMPLES_DIR))
    out_file = base_dir / "bennu_image_decoded.txt"
    if out_file.exists():
        out_file.unlink()

    # Run
    ppc.print_protobuffer_content(test_dir_str, file_name)

    # Assert artifact, then clean up (numpy.testing)
    np.testing.assert_(out_file.exists(), msg="bennu_image_decoded.txt was not created")
    out_file.unlink()


def test_send_protobuffer_file():
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Input file lives under project support-data
    test_dir = PROJECT_ROOT / "support-data" / "protobufs"
    file_name = "bennu_image.bin"
    infile = test_dir / file_name
    if not infile.exists():
        pytest.xfail(f"Missing {infile}")

    out_dir = EXAMPLES_DIR / "bennu_image_images"
    out_file = out_dir / "received_image_0.png"
    if out_file.exists():
        out_file.unlink()

    # Run the example exactly like a user would
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [sys.executable, str(EXAMPLES_DIR / "send_protobuffer_file.py"), "--filename", file_name, "--hide_image"],
        cwd=str(EXAMPLES_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=300,
        check=False,
    )

    # numpy.testing assertions
    np.testing.assert_equal(result.returncode, 0, err_msg=f"send_protobuffer_file.py failed:\n{result.stdout}")
    np.testing.assert_(out_file.exists(), msg="received_image_0.png was not created")

    # Cleanup
    out_file.unlink()
