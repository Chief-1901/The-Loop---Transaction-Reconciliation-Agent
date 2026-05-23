from enum import Enum


class Phase(str, Enum):
    PLAN    = "PLAN"
    ACT     = "ACT"
    OBSERVE = "OBSERVE"
    DECIDE  = "DECIDE"
    HALT    = "HALT"
