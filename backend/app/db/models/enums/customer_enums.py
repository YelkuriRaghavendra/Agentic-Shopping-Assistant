import enum


class CustomerStatus(str, enum.Enum):
    ACTIVE  = "ACTIVE"
    BLOCKED = "BLOCKED"
    GUEST   = "GUEST"
