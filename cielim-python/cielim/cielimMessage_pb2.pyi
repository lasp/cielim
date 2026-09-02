from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TimeStamp(_message.Message):
    __slots__ = ("frameNumber", "simTimeElapsed")
    FRAMENUMBER_FIELD_NUMBER: _ClassVar[int]
    SIMTIMEELAPSED_FIELD_NUMBER: _ClassVar[int]
    frameNumber: int
    simTimeElapsed: float
    def __init__(self, frameNumber: _Optional[int] = ..., simTimeElapsed: _Optional[float] = ...) -> None: ...

class EpochDateTime(_message.Message):
    __slots__ = ("year", "month", "day", "hours", "minutes", "seconds")
    YEAR_FIELD_NUMBER: _ClassVar[int]
    MONTH_FIELD_NUMBER: _ClassVar[int]
    DAY_FIELD_NUMBER: _ClassVar[int]
    HOURS_FIELD_NUMBER: _ClassVar[int]
    MINUTES_FIELD_NUMBER: _ClassVar[int]
    SECONDS_FIELD_NUMBER: _ClassVar[int]
    year: int
    month: int
    day: int
    hours: int
    minutes: int
    seconds: float
    def __init__(
        self,
        year: _Optional[int] = ...,
        month: _Optional[int] = ...,
        day: _Optional[int] = ...,
        hours: _Optional[int] = ...,
        minutes: _Optional[int] = ...,
        seconds: _Optional[float] = ...,
    ) -> None: ...

class RenderingModel(_message.Message):
    __slots__ = (
        "wavelength1",
        "wavelength2",
        "wavelength3",
        "cosmicRayStdDeviation",
        "strayLight",
        "starField",
        "rendering",
        "enableSmear",
    )
    WAVELENGTH1_FIELD_NUMBER: _ClassVar[int]
    WAVELENGTH2_FIELD_NUMBER: _ClassVar[int]
    WAVELENGTH3_FIELD_NUMBER: _ClassVar[int]
    COSMICRAYSTDDEVIATION_FIELD_NUMBER: _ClassVar[int]
    STRAYLIGHT_FIELD_NUMBER: _ClassVar[int]
    STARFIELD_FIELD_NUMBER: _ClassVar[int]
    RENDERING_FIELD_NUMBER: _ClassVar[int]
    ENABLESMEAR_FIELD_NUMBER: _ClassVar[int]
    wavelength1: float
    wavelength2: float
    wavelength3: float
    cosmicRayStdDeviation: float
    strayLight: float
    starField: bool
    rendering: str
    enableSmear: bool
    def __init__(
        self,
        wavelength1: _Optional[float] = ...,
        wavelength2: _Optional[float] = ...,
        wavelength3: _Optional[float] = ...,
        cosmicRayStdDeviation: _Optional[float] = ...,
        strayLight: _Optional[float] = ...,
        starField: _Optional[bool] = ...,
        rendering: _Optional[str] = ...,
        enableSmear: _Optional[bool] = ...,
    ) -> None: ...

class PerlinNoise(_message.Message):
    __slots__ = ("octaveCount", "baseFrequency", "baseAmplitude", "persistence")
    OCTAVECOUNT_FIELD_NUMBER: _ClassVar[int]
    BASEFREQUENCY_FIELD_NUMBER: _ClassVar[int]
    BASEAMPLITUDE_FIELD_NUMBER: _ClassVar[int]
    PERSISTENCE_FIELD_NUMBER: _ClassVar[int]
    octaveCount: int
    baseFrequency: float
    baseAmplitude: float
    persistence: float
    def __init__(
        self,
        octaveCount: _Optional[int] = ...,
        baseFrequency: _Optional[float] = ...,
        baseAmplitude: _Optional[float] = ...,
        persistence: _Optional[float] = ...,
    ) -> None: ...

class ReflectanceModel(_message.Message):
    __slots__ = ("brdfModel", "isotropicScattering", "reflectanceParameters")
    BRDFMODEL_FIELD_NUMBER: _ClassVar[int]
    ISOTROPICSCATTERING_FIELD_NUMBER: _ClassVar[int]
    REFLECTANCEPARAMETERS_FIELD_NUMBER: _ClassVar[int]
    brdfModel: str
    isotropicScattering: float
    reflectanceParameters: _containers.RepeatedScalarFieldContainer[float]
    def __init__(
        self,
        brdfModel: _Optional[str] = ...,
        isotropicScattering: _Optional[float] = ...,
        reflectanceParameters: _Optional[_Iterable[float]] = ...,
    ) -> None: ...

class MeshModel(_message.Message):
    __slots__ = (
        "shapeModel",
        "meanRadius",
        "geometricAlbedo",
        "principalAxisDistortion",
        "inertialToBodyMrp",
        "refModel",
        "perlinNoise",
        "proceduralRocks",
    )
    SHAPEMODEL_FIELD_NUMBER: _ClassVar[int]
    MEANRADIUS_FIELD_NUMBER: _ClassVar[int]
    GEOMETRICALBEDO_FIELD_NUMBER: _ClassVar[int]
    PRINCIPALAXISDISTORTION_FIELD_NUMBER: _ClassVar[int]
    INERTIALTOBODYMRP_FIELD_NUMBER: _ClassVar[int]
    REFMODEL_FIELD_NUMBER: _ClassVar[int]
    PERLINNOISE_FIELD_NUMBER: _ClassVar[int]
    PROCEDURALROCKS_FIELD_NUMBER: _ClassVar[int]
    shapeModel: str
    meanRadius: float
    geometricAlbedo: float
    principalAxisDistortion: _containers.RepeatedScalarFieldContainer[float]
    inertialToBodyMrp: _containers.RepeatedScalarFieldContainer[float]
    refModel: ReflectanceModel
    perlinNoise: PerlinNoise
    proceduralRocks: float
    def __init__(
        self,
        shapeModel: _Optional[str] = ...,
        meanRadius: _Optional[float] = ...,
        geometricAlbedo: _Optional[float] = ...,
        principalAxisDistortion: _Optional[_Iterable[float]] = ...,
        inertialToBodyMrp: _Optional[_Iterable[float]] = ...,
        refModel: _Optional[_Union[ReflectanceModel, _Mapping]] = ...,
        perlinNoise: _Optional[_Union[PerlinNoise, _Mapping]] = ...,
        proceduralRocks: _Optional[float] = ...,
    ) -> None: ...

class CelestialBody(_message.Message):
    __slots__ = ("bodyName", "position", "velocity", "attitude", "model", "centralBody")
    BODYNAME_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    VELOCITY_FIELD_NUMBER: _ClassVar[int]
    ATTITUDE_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    CENTRALBODY_FIELD_NUMBER: _ClassVar[int]
    bodyName: str
    position: _containers.RepeatedScalarFieldContainer[float]
    velocity: _containers.RepeatedScalarFieldContainer[float]
    attitude: _containers.RepeatedScalarFieldContainer[float]
    model: MeshModel
    centralBody: bool
    def __init__(
        self,
        bodyName: _Optional[str] = ...,
        position: _Optional[_Iterable[float]] = ...,
        velocity: _Optional[_Iterable[float]] = ...,
        attitude: _Optional[_Iterable[float]] = ...,
        model: _Optional[_Union[MeshModel, _Mapping]] = ...,
        centralBody: _Optional[bool] = ...,
    ) -> None: ...

class Spacecraft(_message.Message):
    __slots__ = ("spacecraftName", "position", "velocity", "attitude")
    SPACECRAFTNAME_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    VELOCITY_FIELD_NUMBER: _ClassVar[int]
    ATTITUDE_FIELD_NUMBER: _ClassVar[int]
    spacecraftName: str
    position: _containers.RepeatedScalarFieldContainer[float]
    velocity: _containers.RepeatedScalarFieldContainer[float]
    attitude: _containers.RepeatedScalarFieldContainer[float]
    def __init__(
        self,
        spacecraftName: _Optional[str] = ...,
        position: _Optional[_Iterable[float]] = ...,
        velocity: _Optional[_Iterable[float]] = ...,
        attitude: _Optional[_Iterable[float]] = ...,
    ) -> None: ...

class QuantumEfficiency(_message.Message):
    __slots__ = (
        "integrationWeightFactor",
        "redValue1",
        "redValue2",
        "redValue3",
        "greenValue1",
        "greenValue2",
        "greenValue3",
        "blueValue1",
        "blueValue2",
        "blueValue3",
    )
    INTEGRATIONWEIGHTFACTOR_FIELD_NUMBER: _ClassVar[int]
    REDVALUE1_FIELD_NUMBER: _ClassVar[int]
    REDVALUE2_FIELD_NUMBER: _ClassVar[int]
    REDVALUE3_FIELD_NUMBER: _ClassVar[int]
    GREENVALUE1_FIELD_NUMBER: _ClassVar[int]
    GREENVALUE2_FIELD_NUMBER: _ClassVar[int]
    GREENVALUE3_FIELD_NUMBER: _ClassVar[int]
    BLUEVALUE1_FIELD_NUMBER: _ClassVar[int]
    BLUEVALUE2_FIELD_NUMBER: _ClassVar[int]
    BLUEVALUE3_FIELD_NUMBER: _ClassVar[int]
    integrationWeightFactor: float
    redValue1: float
    redValue2: float
    redValue3: float
    greenValue1: float
    greenValue2: float
    greenValue3: float
    blueValue1: float
    blueValue2: float
    blueValue3: float
    def __init__(
        self,
        integrationWeightFactor: _Optional[float] = ...,
        redValue1: _Optional[float] = ...,
        redValue2: _Optional[float] = ...,
        redValue3: _Optional[float] = ...,
        greenValue1: _Optional[float] = ...,
        greenValue2: _Optional[float] = ...,
        greenValue3: _Optional[float] = ...,
        blueValue1: _Optional[float] = ...,
        blueValue2: _Optional[float] = ...,
        blueValue3: _Optional[float] = ...,
    ) -> None: ...

class LensModel(_message.Message):
    __slots__ = (
        "fieldOfView",
        "focalLength",
        "pointSpreadFunction",
        "apertureRadius",
        "transmission1",
        "transmission2",
        "transmission3",
        "horizontalVignetting",
        "verticalVignetting",
        "distortionK1",
        "distortionK2",
        "distortionK3",
        "distortionP1",
        "distortionP2",
    )
    FIELDOFVIEW_FIELD_NUMBER: _ClassVar[int]
    FOCALLENGTH_FIELD_NUMBER: _ClassVar[int]
    POINTSPREADFUNCTION_FIELD_NUMBER: _ClassVar[int]
    APERTURERADIUS_FIELD_NUMBER: _ClassVar[int]
    TRANSMISSION1_FIELD_NUMBER: _ClassVar[int]
    TRANSMISSION2_FIELD_NUMBER: _ClassVar[int]
    TRANSMISSION3_FIELD_NUMBER: _ClassVar[int]
    HORIZONTALVIGNETTING_FIELD_NUMBER: _ClassVar[int]
    VERTICALVIGNETTING_FIELD_NUMBER: _ClassVar[int]
    DISTORTIONK1_FIELD_NUMBER: _ClassVar[int]
    DISTORTIONK2_FIELD_NUMBER: _ClassVar[int]
    DISTORTIONK3_FIELD_NUMBER: _ClassVar[int]
    DISTORTIONP1_FIELD_NUMBER: _ClassVar[int]
    DISTORTIONP2_FIELD_NUMBER: _ClassVar[int]
    fieldOfView: _containers.RepeatedScalarFieldContainer[float]
    focalLength: float
    pointSpreadFunction: float
    apertureRadius: float
    transmission1: float
    transmission2: float
    transmission3: float
    horizontalVignetting: _containers.RepeatedScalarFieldContainer[float]
    verticalVignetting: _containers.RepeatedScalarFieldContainer[float]
    distortionK1: float
    distortionK2: float
    distortionK3: float
    distortionP1: float
    distortionP2: float
    def __init__(
        self,
        fieldOfView: _Optional[_Iterable[float]] = ...,
        focalLength: _Optional[float] = ...,
        pointSpreadFunction: _Optional[float] = ...,
        apertureRadius: _Optional[float] = ...,
        transmission1: _Optional[float] = ...,
        transmission2: _Optional[float] = ...,
        transmission3: _Optional[float] = ...,
        horizontalVignetting: _Optional[_Iterable[float]] = ...,
        verticalVignetting: _Optional[_Iterable[float]] = ...,
        distortionK1: _Optional[float] = ...,
        distortionK2: _Optional[float] = ...,
        distortionK3: _Optional[float] = ...,
        distortionP1: _Optional[float] = ...,
        distortionP2: _Optional[float] = ...,
    ) -> None: ...

class SensorModel(_message.Message):
    __slots__ = (
        "resolution",
        "renderRate",
        "exposureTime",
        "readNoise",
        "shotNoise",
        "darkCurrent",
        "darkCurrentPattern",
        "darkCurrentStdDeviation",
        "systemGain",
        "sensorWidth",
        "sensorHeight",
        "fullWellCapacity",
        "gamma",
        "qeCurve",
        "isGrayscale",
        "pixelDefectPattern",
        "stuckPixelRate",
        "deadPixelRate",
    )
    RESOLUTION_FIELD_NUMBER: _ClassVar[int]
    RENDERRATE_FIELD_NUMBER: _ClassVar[int]
    EXPOSURETIME_FIELD_NUMBER: _ClassVar[int]
    READNOISE_FIELD_NUMBER: _ClassVar[int]
    SHOTNOISE_FIELD_NUMBER: _ClassVar[int]
    DARKCURRENT_FIELD_NUMBER: _ClassVar[int]
    DARKCURRENTPATTERN_FIELD_NUMBER: _ClassVar[int]
    DARKCURRENTSTDDEVIATION_FIELD_NUMBER: _ClassVar[int]
    SYSTEMGAIN_FIELD_NUMBER: _ClassVar[int]
    SENSORWIDTH_FIELD_NUMBER: _ClassVar[int]
    SENSORHEIGHT_FIELD_NUMBER: _ClassVar[int]
    FULLWELLCAPACITY_FIELD_NUMBER: _ClassVar[int]
    GAMMA_FIELD_NUMBER: _ClassVar[int]
    QECURVE_FIELD_NUMBER: _ClassVar[int]
    ISGRAYSCALE_FIELD_NUMBER: _ClassVar[int]
    PIXELDEFECTPATTERN_FIELD_NUMBER: _ClassVar[int]
    STUCKPIXELRATE_FIELD_NUMBER: _ClassVar[int]
    DEADPIXELRATE_FIELD_NUMBER: _ClassVar[int]
    resolution: _containers.RepeatedScalarFieldContainer[int]
    renderRate: int
    exposureTime: float
    readNoise: float
    shotNoise: bool
    darkCurrent: float
    darkCurrentPattern: int
    darkCurrentStdDeviation: float
    systemGain: float
    sensorWidth: float
    sensorHeight: float
    fullWellCapacity: float
    gamma: float
    qeCurve: QuantumEfficiency
    isGrayscale: bool
    pixelDefectPattern: int
    stuckPixelRate: float
    deadPixelRate: float
    def __init__(
        self,
        resolution: _Optional[_Iterable[int]] = ...,
        renderRate: _Optional[int] = ...,
        exposureTime: _Optional[float] = ...,
        readNoise: _Optional[float] = ...,
        shotNoise: _Optional[bool] = ...,
        darkCurrent: _Optional[float] = ...,
        darkCurrentPattern: _Optional[int] = ...,
        darkCurrentStdDeviation: _Optional[float] = ...,
        systemGain: _Optional[float] = ...,
        sensorWidth: _Optional[float] = ...,
        sensorHeight: _Optional[float] = ...,
        fullWellCapacity: _Optional[float] = ...,
        gamma: _Optional[float] = ...,
        qeCurve: _Optional[_Union[QuantumEfficiency, _Mapping]] = ...,
        isGrayscale: _Optional[bool] = ...,
        pixelDefectPattern: _Optional[int] = ...,
        stuckPixelRate: _Optional[float] = ...,
        deadPixelRate: _Optional[float] = ...,
    ) -> None: ...

class AreaOfInterest(_message.Message):
    __slots__ = ("centerX", "centerY", "width", "height", "threshold")
    CENTERX_FIELD_NUMBER: _ClassVar[int]
    CENTERY_FIELD_NUMBER: _ClassVar[int]
    WIDTH_FIELD_NUMBER: _ClassVar[int]
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    THRESHOLD_FIELD_NUMBER: _ClassVar[int]
    centerX: float
    centerY: float
    width: float
    height: float
    threshold: float
    def __init__(
        self,
        centerX: _Optional[float] = ...,
        centerY: _Optional[float] = ...,
        width: _Optional[float] = ...,
        height: _Optional[float] = ...,
        threshold: _Optional[float] = ...,
    ) -> None: ...

class ImageFormat(_message.Message):
    __slots__ = ("format",)

    class Format(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PNG: _ClassVar[ImageFormat.Format]
        RAW_8: _ClassVar[ImageFormat.Format]
        RAW_12: _ClassVar[ImageFormat.Format]
        RAW_12_PACKED: _ClassVar[ImageFormat.Format]
        RAW_16: _ClassVar[ImageFormat.Format]

    PNG: ImageFormat.Format
    RAW_8: ImageFormat.Format
    RAW_12: ImageFormat.Format
    RAW_12_PACKED: ImageFormat.Format
    RAW_16: ImageFormat.Format
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    format: ImageFormat.Format
    def __init__(self, format: _Optional[_Union[ImageFormat.Format, str]] = ...) -> None: ...

class CameraModel(_message.Message):
    __slots__ = (
        "cameraId",
        "parentName",
        "cameraPositionInBody",
        "bodyFrameToCameraMrp",
        "lensModel",
        "sensorModel",
        "areaOfInterest",
        "imageFormat",
    )
    CAMERAID_FIELD_NUMBER: _ClassVar[int]
    PARENTNAME_FIELD_NUMBER: _ClassVar[int]
    CAMERAPOSITIONINBODY_FIELD_NUMBER: _ClassVar[int]
    BODYFRAMETOCAMERAMRP_FIELD_NUMBER: _ClassVar[int]
    LENSMODEL_FIELD_NUMBER: _ClassVar[int]
    SENSORMODEL_FIELD_NUMBER: _ClassVar[int]
    AREAOFINTEREST_FIELD_NUMBER: _ClassVar[int]
    IMAGEFORMAT_FIELD_NUMBER: _ClassVar[int]
    cameraId: int
    parentName: str
    cameraPositionInBody: _containers.RepeatedScalarFieldContainer[float]
    bodyFrameToCameraMrp: _containers.RepeatedScalarFieldContainer[float]
    lensModel: LensModel
    sensorModel: SensorModel
    areaOfInterest: AreaOfInterest
    imageFormat: ImageFormat
    def __init__(
        self,
        cameraId: _Optional[int] = ...,
        parentName: _Optional[str] = ...,
        cameraPositionInBody: _Optional[_Iterable[float]] = ...,
        bodyFrameToCameraMrp: _Optional[_Iterable[float]] = ...,
        lensModel: _Optional[_Union[LensModel, _Mapping]] = ...,
        sensorModel: _Optional[_Union[SensorModel, _Mapping]] = ...,
        areaOfInterest: _Optional[_Union[AreaOfInterest, _Mapping]] = ...,
        imageFormat: _Optional[_Union[ImageFormat, _Mapping]] = ...,
    ) -> None: ...

class CielimMessage(_message.Message):
    __slots__ = ("epoch", "currentTime", "renderParameters", "celestialBodies", "spacecraft", "camera")
    EPOCH_FIELD_NUMBER: _ClassVar[int]
    CURRENTTIME_FIELD_NUMBER: _ClassVar[int]
    RENDERPARAMETERS_FIELD_NUMBER: _ClassVar[int]
    CELESTIALBODIES_FIELD_NUMBER: _ClassVar[int]
    SPACECRAFT_FIELD_NUMBER: _ClassVar[int]
    CAMERA_FIELD_NUMBER: _ClassVar[int]
    epoch: EpochDateTime
    currentTime: TimeStamp
    renderParameters: RenderingModel
    celestialBodies: _containers.RepeatedCompositeFieldContainer[CelestialBody]
    spacecraft: Spacecraft
    camera: CameraModel
    def __init__(
        self,
        epoch: _Optional[_Union[EpochDateTime, _Mapping]] = ...,
        currentTime: _Optional[_Union[TimeStamp, _Mapping]] = ...,
        renderParameters: _Optional[_Union[RenderingModel, _Mapping]] = ...,
        celestialBodies: _Optional[_Iterable[_Union[CelestialBody, _Mapping]]] = ...,
        spacecraft: _Optional[_Union[Spacecraft, _Mapping]] = ...,
        camera: _Optional[_Union[CameraModel, _Mapping]] = ...,
    ) -> None: ...
