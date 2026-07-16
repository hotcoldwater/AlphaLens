from enum import StrEnum


class StrategyStatus(StrEnum):
    DRAFT = "DRAFT"
    NEEDS_INPUT = "NEEDS_INPUT"
    READY_TO_CONFIRM = "READY_TO_CONFIRM"
    CONFIRMED = "CONFIRMED"
    ARCHIVED = "ARCHIVED"
