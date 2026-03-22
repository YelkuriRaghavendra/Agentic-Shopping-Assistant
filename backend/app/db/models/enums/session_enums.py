import enum


class SessionStatus(str, enum.Enum):
    ACTIVE    = "ACTIVE"
    ENDED     = "ENDED"
    ABANDONED = "ABANDONED"
    EXPIRED   = "EXPIRED"


class ChannelType(str, enum.Enum):
    WEB      = "WEB"
    MOBILE   = "MOBILE"
    WHATSAPP = "WHATSAPP"
    SDK      = "SDK"


class FeedbackType(str, enum.Enum):
    HELPFUL          = "HELPFUL"
    POOR_SUGGESTIONS = "POOR_SUGGESTIONS"
    INACCURATE       = "INACCURATE"
    BAD_EXPERIENCE   = "BAD_EXPERIENCE"
    OTHER            = "OTHER"
