import enum


class SourceStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ERROR  = "ERROR"


class SourceType(str, enum.Enum):
    MANUAL      = "MANUAL"
    FILE_UPLOAD = "FILE_UPLOAD"
    CSV         = "CSV"
    PDF         = "PDF"
    API_PUSH    = "API_PUSH"
