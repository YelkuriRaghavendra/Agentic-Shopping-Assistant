import enum


class MessageRole(str, enum.Enum):
    USER      = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM    = "SYSTEM"


class GuardrailStatus(str, enum.Enum):
    PASSED  = "PASSED"
    BLOCKED = "BLOCKED"
    WARNED  = "WARNED"
