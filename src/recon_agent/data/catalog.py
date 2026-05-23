from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class CategorySpec:
    name: str
    merchants: list[str]
    amount_min: int
    amount_max: int
    amount_mean: int


CATEGORIES: list[CategorySpec] = [
    CategorySpec("Fashion", ["Myntra", "Ajio", "Puma", "Nykaa"],          500,   5_000,  1_800),
    CategorySpec("Travel",  ["MakeMyTrip", "Goibibo", "Cleartrip", "Uber"], 1_000, 15_000, 4_500),
    CategorySpec("Food",    ["Zomato", "Swiggy", "BigBasket"],             150,     800,    400),
    CategorySpec("Electronics", ["Amazon", "Flipkart", "Croma", "BoAt"],  1_000, 50_000,  6_000),
    CategorySpec("Health",  ["PharmEasy", "Mamaearth", "Lenskart"],        200,   2_000,    800),
]


COUPON_CODES = [
    "FLAT200", "SAVE40", "NEW100", "WELCOME", "MEGA50",
    "WEEKEND", "RAKHI25", "DIWALI60", "MONDAY10", "CRED50",
]


CHANNELS = ["web", "app", "mweb"]
