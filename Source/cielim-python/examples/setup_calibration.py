import cv2
import math

import cielim


def scene_setup() -> cielim.Scene:
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, 200), attitude=(0, 1, 0))

    scene.set_lens_params(fov=(3.1415 * 110 / 180, 3.1415 * 110 / 180))
    scene.set_sensor_params(exposure=5e-9)

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="Plane", mesh_brdf="Lambertian", mesh_radius=1000)

    return scene


if __name__ == "__main__":
    """
    Spawn a Lambertian Diffuse plane for calibration
    """

    connector = cielim.Connector()
    # launcher = cielim.Launcher()
    # connector.connect(launcher.launch())
    connector.connect()

    connector.send_init_request()

    scene = scene_setup()

    rotations = 1

    for i in range(rotations + 1):
        theta = math.pi * (1 - i / rotations)
        scene.set_spacecraft_params(attitude=(0, math.tan(theta / 4), 0))

        connector.send_frame(scene.get_scene())
        image, _, _ = connector.request_image_for_camera_id(1, True, False)

        WindowName = f"Image_Client_{connector.identity}"
        cv2.namedWindow(WindowName, cv2.WINDOW_NORMAL)
        cv2.imshow(WindowName, image)
        cv2.resizeWindow(WindowName, 1000, 1000)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    connector.disconnect()
    # launcher.terminate()
