from context import driver, launcher
from context import cielimMessage_pb2
import numpy as np
import cv2


def default_scene():

    protobuf_message = cielimMessage_pb2.CielimMessage()

    body = protobuf_message.celestialBodies.add()
    body.bodyName = "Plane"
    [body.position.append(item) for item in [0, 0, 0]]
    [body.attitude.append(item) for item in np.eye(3).flatten().tolist()]
    [body.model.inertialToBodyMrp.append(item) for item in [0, 0, 0]]
    body.model.shapeModel = "Plane"
    body.model.meanRadius = 10000

    sun = protobuf_message.celestialBodies.add()
    sun.bodyName = "sun"
    [sun.position.append(item) for item in [0, 0, 0.5 * 1.496e11]]
    [sun.attitude.append(item) for item in [0, 0, 0]]

    protobuf_message.camera.cameraId = 1
    protobuf_message.camera.parentName = "cielim_sat"
    [protobuf_message.camera.lensModel.fieldOfView.append(item) for item in [30 * np.pi / 180, 25 * np.pi / 180]]
    [protobuf_message.camera.bodyFrameToCameraMrp.append(item) for item in [0.0, 0, 0]]
    [protobuf_message.camera.cameraPositionInBody.append(item) for item in [0, 0, 0]]
    [protobuf_message.camera.sensorModel.resolution.append(item) for item in [3000, 3000]]

    protobuf_message.spacecraft.spacecraftName = "cielim_sat"
    [protobuf_message.spacecraft.position.append(item) for item in [0, 0, 10000]]
    [protobuf_message.spacecraft.attitude.append(item) for item in [0, 1, 0]]

    return protobuf_message


if __name__ == "__main__":
    """
    Spawn a Lambertian Diffuse plane for calibration
    """

    connector = driver.Connector()
    connector.connect()

    scene = default_scene()

    connector.send_init_request()
    connector.send_frame(scene)
    image, _, _ = connector.request_image_for_camera_id(1, 1)

    WindowName = f"Image_Client_{connector.identity}"
    cv2.namedWindow(WindowName, cv2.WINDOW_NORMAL)
    cv2.imshow(WindowName, image)
    cv2.resizeWindow(WindowName, 1250, 1000)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
