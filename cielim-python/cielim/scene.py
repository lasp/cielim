import numpy as np

from . import cielimMessage_pb2 as cielimProto
from .cielimMessage_pb2 import CielimMessage


class Scene(object):
    """
    A class to represent a scene; acts as a wrapper for cielim message object.
    """

    def __init__(self):
        # Cielim message object
        self.cielim_message = CielimMessage()

        # Physical parameters
        self.gravitational_parameter: float = 0
        self.target_name: str = ""

        # Setup basic default scene

        self.cielim_message.renderParameters.wavelength1 = 650  # nm
        self.cielim_message.renderParameters.wavelength2 = 550  # nm
        self.cielim_message.renderParameters.wavelength3 = 450  # nm

        self.cielim_message.spacecraft.spacecraftName = "cielim_sat"
        self.cielim_message.spacecraft.position.extend([0, 0, 0])
        self.cielim_message.spacecraft.velocity.extend([0, 0, 0])
        self.cielim_message.spacecraft.attitude.extend([0, 0, 0])

        self.cielim_message.camera.cameraId = 1
        self.cielim_message.camera.parentName = "cielim_sat"
        self.cielim_message.camera.cameraPositionInBody.extend([0, 0, 0])
        self.cielim_message.camera.bodyFrameToCameraMrp.extend([0, 0, 0])
        self.cielim_message.camera.lensModel.fieldOfView.extend([np.pi / 2, np.pi / 2])
        self.cielim_message.camera.lensModel.focalLength = 0.16  # meters
        self.cielim_message.camera.lensModel.apertureRadius = 0.005  # meters
        self.cielim_message.camera.lensModel.transmission1 = 1
        self.cielim_message.camera.lensModel.transmission2 = 1
        self.cielim_message.camera.lensModel.transmission3 = 1
        self.cielim_message.camera.sensorModel.resolution.extend([1000, 1000])
        self.cielim_message.camera.sensorModel.exposureTime = 0.001  # seconds
        self.cielim_message.camera.sensorModel.sensorWidth = 0.036  # meters
        self.cielim_message.camera.sensorModel.sensorHeight = 0.024
        self.cielim_message.camera.sensorModel.fullWellCapacity = 50000  # electrons
        self.cielim_message.camera.sensorModel.gamma = 2.2
        self.cielim_message.camera.sensorModel.systemGain = 1
        self.cielim_message.camera.sensorModel.qeCurve.redValue1 = 1
        self.cielim_message.camera.sensorModel.qeCurve.redValue2 = 1
        self.cielim_message.camera.sensorModel.qeCurve.redValue3 = 1
        self.cielim_message.camera.sensorModel.qeCurve.greenValue1 = 1
        self.cielim_message.camera.sensorModel.qeCurve.greenValue2 = 1
        self.cielim_message.camera.sensorModel.qeCurve.greenValue3 = 1
        self.cielim_message.camera.sensorModel.qeCurve.blueValue1 = 1
        self.cielim_message.camera.sensorModel.qeCurve.blueValue2 = 1
        self.cielim_message.camera.sensorModel.qeCurve.blueValue3 = 1
        self.cielim_message.camera.sensorModel.qeCurve.integrationWeightFactor = 1

        sun = self.cielim_message.celestialBodies.add()
        sun.bodyName = "sun"
        sun.position.extend([0, 0, 1.496e11])  # 1 AU from origin
        sun.velocity.extend([0, 0, 0])
        sun.attitude.extend([0, 0, 0])

    def set_existing_message(self, message: CielimMessage) -> None:
        """
        Set scene to existing message.

        Args:
            message (CielimMessage): CielimMessage instance to set scene to.
        """
        self.cielim_message = message

    def get_scene(self) -> CielimMessage:
        """
        Returns the current cielim message object.
        """
        return self.cielim_message

    def set_render_params(
        self,
        wavelength1: float | None = None,
        wavelength2: float | None = None,
        wavelength3: float | None = None,
    ) -> None:
        """
        Set render parameters.

        Args:
            wavelength1 (float, optional): Longest wavelength in nanometers.
            wavelength2 (float, optional): Middle wavelength in nanometers.
            wavelength3 (float, optional): Shortest wavelength in nanometers.
        """
        if wavelength1 is not None and wavelength1 > 0:
            self.cielim_message.renderParameters.wavelength1 = wavelength1  # nm

        if wavelength2 is not None and wavelength2 > 0:
            self.cielim_message.renderParameters.wavelength2 = wavelength2  # nm

        if wavelength3 is not None and wavelength3 > 0:
            self.cielim_message.renderParameters.wavelength3 = wavelength3  # nm

    def set_spacecraft_params(
        self,
        name: str | None = None,
        position: tuple[float, float, float] | None = None,
        velocity: tuple[float, float, float] | None = None,
        attitude: tuple[float, float, float] | None = None,
    ) -> None:
        """
        Set spacecraft parameters.

        Args:
            name (str, optional): Name of the spacecraft.
            position (tuple[float, float, float], optional): Position of the spacecraft.
            velocity (tuple[float, float, float], optional): Velocity of the spacecraft.
            attitude (tuple[float, float, float], optional): Attitude of the spacecraft as MRP.
        """
        if name:
            self.cielim_message.spacecraft.spacecraftName = name

        if position is not None:
            del self.cielim_message.spacecraft.position[:]
            self.cielim_message.spacecraft.position.extend(position)

        if velocity is not None:
            del self.cielim_message.spacecraft.velocity[:]
            self.cielim_message.spacecraft.velocity.extend(velocity)

        if attitude is not None:
            del self.cielim_message.spacecraft.attitude[:]
            self.cielim_message.spacecraft.attitude.extend(attitude)

    def set_camera_params(
        self,
        name: str | None = None,
        position: tuple[float, float, float] | None = None,
        attitude: tuple[float, float, float] | None = None,
        image_format: cielimProto.ImageFormat.Format | None = None,
        grayscale: bool | None = None,
    ) -> None:
        """
        Set parameters of camera object.

        Args:
            name (str, optional): Name of the spacecraft to which the camera is attached.
            position (tuple[float, float, float], optional): Position of the camera relative to the spacecraft.
            attitude (tuple[float, float, float], optional): Attitude of the camera relative to the spacecraft as MRP.
            image_format (ImageFormat.Format, optional): Image format to use when exporting image data.
            grayscale (bool, optional): Whether the image is grayscale or not.
        """
        if name:
            self.cielim_message.camera.parentName = name

        if position is not None:
            del self.cielim_message.camera.cameraPositionInBody[:]
            self.cielim_message.camera.cameraPositionInBody.extend(position)

        if attitude is not None:
            del self.cielim_message.camera.bodyFrameToCameraMrp[:]
            self.cielim_message.camera.bodyFrameToCameraMrp.extend(attitude)

        if image_format is not None:
            self.cielim_message.camera.imageFormat.format = image_format

        if grayscale is not None:
            self.cielim_message.camera.sensorModel.isGrayscale = grayscale

    def set_lens_params(
        self,
        fov: tuple[float, float] | None = None,
        focal_length: float | None = None,
        aperture_radius: float | None = None,
        transmission: tuple[float, float, float] | None = None,
    ) -> None:
        """
        Set parameters of the camera lens.

        Args:
            fov (tuple[float, float], optional): FOV (X, Y) of the camera.
            focal_length (float, optional): Focal length of the camera in meters.
            aperture_radius (float, optional): Radius of the camera aperture in meters.
            transmission (tuple[float, float, float], optional): Fraction of wavelengths (1,2,3) transmitted through the lens.
        """
        if fov is not None and all(f > 0 for f in fov):
            del self.cielim_message.camera.lensModel.fieldOfView[:]
            self.cielim_message.camera.lensModel.fieldOfView.extend(fov)

        if focal_length is not None and focal_length > 0:
            self.cielim_message.camera.lensModel.focalLength = focal_length  # meters

        if aperture_radius is not None and aperture_radius > 0:
            self.cielim_message.camera.lensModel.apertureRadius = aperture_radius  # meters

        if transmission is not None and all(f > 0 for f in transmission):
            self.cielim_message.camera.lensModel.transmission1 = transmission[0]
            self.cielim_message.camera.lensModel.transmission2 = transmission[1]
            self.cielim_message.camera.lensModel.transmission3 = transmission[2]

    def set_sensor_params(
        self,
        resolution: tuple[int, int] | None = None,
        exposure: float | None = None,
        sensor_dims: tuple[float, float] | None = None,
        well_capacity: int | None = None,
        gamma: float | None = None,
        gain: float | None = None,
        qe_chan1: tuple[float, float, float] | None = None,
        qe_chan2: tuple[float, float, float] | None = None,
        qe_chan3: tuple[float, float, float] | None = None,
        qe_weight: float | None = None,
    ) -> None:
        """
        Set parameters of the camera sensor.

        Args:
            resolution (tuple[int, int], optional): Resolution of the camera sensor in pixels.
            exposure (float, optional): Exposure time of the camera in seconds.
            sensor_dims (tuple[float, float], optional): Dimensions (width,height) of the camera sensor in meters.
            well_capacity (int, optional): Full well capacity of the camera sensor.
            gamma (float, optional): The gamma correction factor of the camera sensor.
            gain (float, optional): The system gain of the camera sensor.
            qe_chan1 (tuple[float, float, float], optional): Quantum efficiency values (channel 1) for wavelengths (1,2,3).
            qe_chan2 (tuple[float, float, float], optional): Quantum efficiency values (channel 2) for wavelengths (1,2,3).
            qe_chan3 (tuple[float, float, float], optional): Quantum efficiency values (channel 3) for wavelengths (1,2,3).
            qe_weight (float, optional): Quantum efficiency integration weight factor.
        """
        if resolution is not None and all(f > 0 for f in resolution):
            del self.cielim_message.camera.sensorModel.resolution[:]
            self.cielim_message.camera.sensorModel.resolution.extend(resolution)

        if exposure is not None and exposure > 0:
            self.cielim_message.camera.sensorModel.exposureTime = exposure  # seconds

        if sensor_dims is not None and all(f > 0 for f in sensor_dims):
            self.cielim_message.camera.sensorModel.sensorWidth = sensor_dims[0]  # meters
            self.cielim_message.camera.sensorModel.sensorHeight = sensor_dims[1]

        if well_capacity is not None and well_capacity > 0:
            self.cielim_message.camera.sensorModel.fullWellCapacity = well_capacity  # electrons

        if gamma is not None and gamma > 0:
            self.cielim_message.camera.sensorModel.gamma = gamma

        if gain is not None and gain > 0:
            self.cielim_message.camera.sensorModel.systemGain = gain

        if qe_chan1 is not None and all(f >= 0 for f in qe_chan1):
            self.cielim_message.camera.sensorModel.qeCurve.redValue1 = qe_chan1[0]
            self.cielim_message.camera.sensorModel.qeCurve.redValue2 = qe_chan1[1]
            self.cielim_message.camera.sensorModel.qeCurve.redValue3 = qe_chan1[2]

        if qe_chan2 is not None and all(f >= 0 for f in qe_chan2):
            self.cielim_message.camera.sensorModel.qeCurve.greenValue1 = qe_chan2[0]
            self.cielim_message.camera.sensorModel.qeCurve.greenValue2 = qe_chan2[1]
            self.cielim_message.camera.sensorModel.qeCurve.greenValue3 = qe_chan2[2]

        if qe_chan3 is not None and all(f >= 0 for f in qe_chan3):
            self.cielim_message.camera.sensorModel.qeCurve.blueValue1 = qe_chan3[0]
            self.cielim_message.camera.sensorModel.qeCurve.blueValue2 = qe_chan3[1]
            self.cielim_message.camera.sensorModel.qeCurve.blueValue3 = qe_chan3[2]

        if qe_weight is not None and qe_weight > 0:
            self.cielim_message.camera.sensorModel.qeCurve.integrationWeightFactor = qe_weight

    def set_corruption_params(
        self,
        dist_radial: tuple[float, float, float] | None = None,
        dist_tangent: tuple[float, float] | None = None,
        psf_sigma: float | None = None,
        shot_noise: bool | None = None,
        dc_rate: float | None = None,
        dc_seed: int | None = None,
        dc_sigma: float | None = None,
        cosmic_rays: float | None = None,
        read_noise: float | None = None,
        defect_seed: int | None = None,
        stuck_px_rate: float | None = None,
        dead_px_rate: float | None = None,
    ) -> None:
        """
        Set camera corruption parameters.

        Args:
            dist_radial (tuple[float, float, float], optional): Radial lens distortion factors (k1, k2, k3).
            dist_tangent (tuple[float, float], optional): Tangential lens distortion factors (p1, p2).
            psf_sigma (float, optional): Point spread function standard deviation.
            shot_noise (bool, optional): Enable shot noise.
            dc_rate (float, optional): Dark current rate in electrons per second.
            dc_seed (int, optional): Dark current random pattern seed.
            dc_sigma (float, optional): Dark current standard deviation in electrons per second.
            cosmic_rays (float, optional): Cosmic rays standard deviation.
            read_noise (float, optional): Read noise standard deviation in electrons.
            defect_seed (int, optional): Pixel defect random pattern seed.
            stuck_px_rate (float, optional): Stuck pixel rate (probability).
            dead_px_rate (float, optional): Dead pixel rate (probability).
        """
        if dist_radial is not None and all(f >= 0 for f in dist_radial):
            self.cielim_message.camera.lensModel.distortionK1 = dist_radial[0]
            self.cielim_message.camera.lensModel.distortionK2 = dist_radial[1]
            self.cielim_message.camera.lensModel.distortionK3 = dist_radial[2]

        if dist_tangent is not None and all(f >= 0 for f in dist_tangent):
            self.cielim_message.camera.lensModel.distortionP1 = dist_tangent[0]
            self.cielim_message.camera.lensModel.distortionP2 = dist_tangent[1]

        if psf_sigma is not None and psf_sigma >= 0:
            self.cielim_message.camera.lensModel.pointSpreadFunction = psf_sigma

        if shot_noise is not None:
            self.cielim_message.camera.sensorModel.shotNoise = shot_noise

        if dc_rate is not None and dc_rate >= 0:
            self.cielim_message.camera.sensorModel.darkCurrent = dc_rate

        if dc_seed is not None and dc_seed >= 0:
            self.cielim_message.camera.sensorModel.darkCurrentPattern = dc_seed

        if dc_sigma is not None and dc_sigma >= 0:
            self.cielim_message.camera.sensorModel.darkCurrentStdDeviation = dc_sigma

        if cosmic_rays is not None and cosmic_rays >= 0:
            self.cielim_message.renderParameters.cosmicRayStdDeviation = cosmic_rays

        if read_noise is not None and read_noise >= 0:
            self.cielim_message.camera.sensorModel.readNoise = read_noise

        if defect_seed is not None and defect_seed >= 0:
            self.cielim_message.camera.sensorModel.pixelDefectPattern = defect_seed

        if stuck_px_rate is not None and stuck_px_rate >= 0:
            self.cielim_message.camera.sensorModel.stuckPixelRate = stuck_px_rate

        if dead_px_rate is not None and dead_px_rate >= 0:
            self.cielim_message.camera.sensorModel.deadPixelRate = dead_px_rate

    def add_celestial_body(self, name: str) -> int:
        """
        Adds a celestial body to the scene.

        Args:
            name (str): Name of the celestial body.

        Returns:
            int: Index of the added celestial body in the scene's celestialBodies list.
        """
        body = self.cielim_message.celestialBodies.add()

        body.bodyName = name

        body.position.extend([0, 0, 0])
        body.velocity.extend([0, 0, 0])
        body.attitude.extend([0, 0, 0])

        body.model.geometricAlbedo = 1  # Set default albedo to 1 (fully reflective)

        return len(self.cielim_message.celestialBodies) - 1  # Return index of the added body

    def get_celestial_body(self, index: int) -> cielimProto.CelestialBody:
        """
        Retrieves a celestial body from the scene.

        Args:
            index (int): Index of the celestial body to retrieve in the scene's celestialBodies list.

        Raises:
            IndexError: If the index is out of range of the celestialBodies list.
        """
        if 0 <= index < len(self.cielim_message.celestialBodies):
            return self.cielim_message.celestialBodies[index]
        else:
            raise IndexError("Celestial body index out of range.")

    def set_celestial_body_params(
        self,
        index: int,
        name: str | None = None,
        position: tuple[float, float, float] | None = None,
        velocity: tuple[float, float, float] | None = None,
        attitude: tuple[float, float, float] | None = None,
        albedo: float | None = None,
        mesh_shape: str | None = None,
        mesh_brdf: str | None = None,
        mesh_radius: float | None = None,
        mesh_attitude: tuple[float, float, float] | None = None,
        mesh_distortions: tuple[float, float, float] | None = None,
    ) -> None:
        """
        Edits a celestial body in the scene.

        Args:
            index (int): Index of the celestial body to edit in the scene's celestialBodies list.
            name (str, optional): Name of the celestial body.
            position (tuple[float, float, float], optional): Position of the celestial body.
            velocity (tuple[float, float, float], optional): Velocity of the celestial body.
            attitude (tuple[float, float, float], optional): Attitude of the celestial body as MRP.
            albedo (float, optional): Geometric albedo of the celestial body (0 to 1).
            mesh_shape (str, optional): Name of the shape model for the celestial body.
            mesh_brdf (str, optional): Name of the BRDF model for the celestial body.
            mesh_radius (float, optional): Mean radius of the shape model in meters.
            mesh_attitude (tuple[float, float, float], optional): Attitude of the shape model relative to the celestial body as MRP.
            mesh_distortions (tuple[float, float, float], optional): Axis (x, y, z) distortions for mesh.

        Raises:
            IndexError: If the index is out of range of the celestialBodies list.
        """
        if 0 <= index < len(self.cielim_message.celestialBodies):
            body = self.cielim_message.celestialBodies[index]
        else:
            raise IndexError("Celestial body index out of range.")

        if name:
            body.bodyName = name

        if position is not None:
            del body.position[:]
            body.position.extend(position)

        if velocity is not None:
            del body.velocity[:]
            body.velocity.extend(velocity)

        if attitude is not None:
            del body.attitude[:]
            body.attitude.extend(attitude)

        if albedo is not None and albedo >= 0:
            body.model.geometricAlbedo = albedo

        if mesh_shape:
            body.model.shapeModel = mesh_shape

        if mesh_brdf:
            body.model.refModel.brdfModel = mesh_brdf

        if mesh_radius is not None and mesh_radius >= 0:
            body.model.meanRadius = mesh_radius

        if mesh_attitude is not None:
            del body.model.inertialToBodyMrp[:]
            body.model.inertialToBodyMrp.extend(mesh_attitude)

        if mesh_distortions is not None and all(f >= 0 for f in mesh_distortions):
            del body.model.principalAxisDistortion[:]
            body.model.principalAxisDistortion.extend(mesh_distortions)

    def delete_celestial_body(self, index: int) -> None:
        """
        Deletes a celestial body from the scene.

        Args:
            index (int): Index of the celestial body to delete in the scene's celestialBodies list.

        Raises:
            IndexError: If the index is out of range of the celestialBodies list.
        """
        if 0 <= index < len(self.cielim_message.celestialBodies):
            del self.cielim_message.celestialBodies[index]
        else:
            raise IndexError("Celestial body index out of range.")
