import enum


class JobStatus(str, enum.Enum):
    QUEUED    = "QUEUED"
    CHUNKING  = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    DONE      = "DONE"
    FAILED    = "FAILED"
