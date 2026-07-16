from enum import StrEnum


class IndicatorType(StrEnum):
    OPEN = "OPEN"
    HIGH = "HIGH"
    LOW = "LOW"
    CLOSE = "CLOSE"
    VOLUME = "VOLUME"
    SMA = "SMA"
    EMA = "EMA"
    RSI = "RSI"
    RETURN = "RETURN"
    N_DAY_RETURN = "N_DAY_RETURN"
    N_DAY_HIGH = "N_DAY_HIGH"
    N_DAY_LOW = "N_DAY_LOW"
    VOLUME_SMA = "VOLUME_SMA"
