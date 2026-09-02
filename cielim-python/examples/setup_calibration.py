import cv2
import numpy as np

import cielim


def scene_setup() -> cielim.Scene:
    scene = cielim.Scene()

    scene.set_spacecraft_params(position=(0, 0, 2000), attitude=(0, 1, 0))

    scene.set_lens_params(fov=(10 * np.pi / 180, 10 * np.pi / 180))

    index = scene.add_celestial_body("asteroid")
    scene.set_celestial_body_params(index, mesh_shape="Plane", mesh_brdf="Lambertian", mesh_radius=1000)

    return scene


if __name__ == "__main__":
    """
    Spawn a Lambertian Diffuse plane for calibration
    """

    connector = cielim.Connector()
    launcher = cielim.Launcher()
    connector.connect(launcher.launch())
    connector.send_init_request()

    scene = scene_setup()

    connector.send_init_request()
    connector.send_frame(scene.get_scene())
    image, _, _ = connector.request_image_for_camera_id(1, True, False)

    WindowName = f"Image_Client_{connector.identity}"
    cv2.namedWindow(WindowName, cv2.WINDOW_NORMAL)
    cv2.imshow(WindowName, image)
    cv2.resizeWindow(WindowName, 1000, 1000)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    connector.disconnect()
    launcher.terminate()
