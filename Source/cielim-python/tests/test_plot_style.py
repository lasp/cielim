import json

from cielim.utils import plot_style as ps


def test_save_context_writes_json(tmp_path):
    facts = {"exposure_s": 5e-05, "fov_deg": 10, "brdf": "Lambertian"}

    path = ps.save_context("stray_light_flare", facts, files=["a.png", "b.png"], directory=str(tmp_path))

    assert path == str(tmp_path / "stray_light_flare.json")
    record = json.loads((tmp_path / "stray_light_flare.json").read_text())

    # Keys come back in the order they were written: figure, files, then the facts as given, so the
    # record reads the way it was composed rather than alphabetically.
    assert list(record) == ["figure", "files", "exposure_s", "fov_deg", "brdf"]
    assert record["figure"] == "stray_light_flare"
    assert record["files"] == ["a.png", "b.png"]
    assert record["exposure_s"] == 5e-05
    assert record["brdf"] == "Lambertian"


def test_save_context_without_files(tmp_path):
    path = ps.save_context("sensor_effects", {"read_noise": 3000}, directory=str(tmp_path))

    record = json.loads((tmp_path / "sensor_effects.json").read_text())
    assert path is not None
    assert "files" not in record
    assert record == {"figure": "sensor_effects", "read_noise": 3000}


def test_save_context_creates_missing_directory(tmp_path):
    target = tmp_path / "showcase" / "vesta"

    ps.save_context("distant_objects", {"crop_px": "26x26"}, directory=str(target))

    assert (target / "distant_objects.json").exists()


def test_save_context_is_a_noop_without_showcase_dir(tmp_path, monkeypatch):
    # Same opt-in as save_showcase: with nowhere to write, the showcase tests must be able to call
    # this unconditionally and have it do nothing.
    monkeypatch.delenv("showcase_dir", raising=False)

    assert ps.save_context("stray_light_flare", {"fov_deg": 10}) is None
    assert not list(tmp_path.iterdir())


def test_save_context_defaults_to_showcase_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("showcase_dir", str(tmp_path))

    path = ps.save_context("lens_effects", {"psf_sigma": 50})

    assert path == str(tmp_path / "lens_effects.json")
    assert json.loads((tmp_path / "lens_effects.json").read_text())["psf_sigma"] == 50
