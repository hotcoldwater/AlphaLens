from enum import StrEnum


class LogicType(StrEnum):
    AND = "AND"
    OR = "OR"


class UniverseType(StrEnum):
    SINGLE_STOCK = "SINGLE_STOCK"
    REGIME_SWITCH = "REGIME_SWITCH"
    ALLOCATION_REBALANCE = "ALLOCATION_REBALANCE"


class RebalanceFrequency(StrEnum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"


class DataTimeframe(StrEnum):
    DAILY = "1D"


class PositionSizingMethod(StrEnum):
    AVAILABLE_CASH = "AVAILABLE_CASH"
    PERCENT_OF_EQUITY = "PERCENT_OF_EQUITY"
    FIXED_AMOUNT = "FIXED_AMOUNT"
    FIXED_QUANTITY = "FIXED_QUANTITY"


class SignalTime(StrEnum):
    CLOSE = "CLOSE"


class ExecutionTime(StrEnum):
    NEXT_OPEN = "NEXT_OPEN"
