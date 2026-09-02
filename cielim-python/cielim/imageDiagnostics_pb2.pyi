from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class DiagnosticData(_message.Message):
    __slots__ = ("cob_x", "cob_y", "coverage", "totalBrightPixels")
    COB_X_FIELD_NUMBER: _ClassVar[int]
    COB_Y_FIELD_NUMBER: _ClassVar[int]
    COVERAGE_FIELD_NUMBER: _ClassVar[int]
    TOTALBRIGHTPIXELS_FIELD_NUMBER: _ClassVar[int]
    cob_x: float
    cob_y: float
    coverage: float
    totalBrightPixels: int
    def __init__(
        self,
        cob_x: _Optional[float] = ...,
        cob_y: _Optional[float] = ...,
        coverage: _Optional[float] = ...,
        totalBrightPixels: _Optional[int] = ...,
    ) -> None: ...
