import enum


class DocumentStatus(str, enum.Enum):
    PENDING    = "PENDING"
    PROCESSING = "PROCESSING"
    READY      = "READY"
    FAILED     = "FAILED"


class DocumentType(str, enum.Enum):
    PRODUCT  = "PRODUCT"
    FAQ      = "FAQ"
    POLICY   = "POLICY"
    ARTICLE  = "ARTICLE"
    RAW_TEXT = "RAW_TEXT"
    ORDER    = "ORDER"