import math
from dataclasses import dataclass, field


@dataclass
class DonationInfo:
    donation_id: str
    food_type: str
    food_name: str
    quantity: float
    unit: str
    latitude: float | None
    longitude: float | None


@dataclass
class NGOProfile:
    user_id: str
    name: str
    latitude: float
    longitude: float
    accepted_food_types: list[str] = field(default_factory=list)
    priority_score: float = 0.0
    capacity_remaining: float = 100.0


@dataclass
class MatchResult:
    ngo_id: str
    ngo_name: str
    donation_id: str
    score: float
    distance_km: float
    food_type_match: bool
    quantity_match: bool


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_match_score(
    donation: DonationInfo,
    ngo: NGOProfile,
    max_distance_km: float = 50.0,
) -> MatchResult:
    food_type_match = donation.food_type.lower() in [ft.lower() for ft in ngo.accepted_food_types]
    if not food_type_match:
        food_type_match = donation.food_type.lower() in ["any", "general", "mixed"]

    quantity_match = donation.quantity <= ngo.capacity_remaining

    distance_km = 0.0
    if donation.latitude and donation.longitude and ngo.latitude and ngo.longitude:
        distance_km = haversine_distance(
            donation.latitude, donation.longitude,
            ngo.latitude, ngo.longitude,
        )

    food_type_score = 1.0 if food_type_match else 0.0
    quantity_score = 1.0 if quantity_match else 0.5
    distance_score = max(0.0, 1.0 - (distance_km / max_distance_km)) if distance_km > 0 else 1.0
    priority_score = ngo.priority_score / 100.0 if ngo.priority_score > 0 else 0.5

    W_FOOD_TYPE = 0.35
    W_QUANTITY = 0.15
    W_DISTANCE = 0.35
    W_PRIORITY = 0.15

    score = (
        W_FOOD_TYPE * food_type_score
        + W_QUANTITY * quantity_score
        + W_DISTANCE * distance_score
        + W_PRIORITY * priority_score
    )

    return MatchResult(
        ngo_id=ngo.user_id,
        ngo_name=ngo.name,
        donation_id=donation.donation_id,
        score=round(score, 4),
        distance_km=round(distance_km, 2),
        food_type_match=food_type_match,
        quantity_match=quantity_match,
    )


def find_best_matches(
    donation: DonationInfo,
    ngos: list[NGOProfile],
    top_n: int = 5,
) -> list[MatchResult]:
    if not ngos:
        return []

    matches = []
    for ngo in ngos:
        result = calculate_match_score(donation, ngo)
        if result.score > 0.0:
            matches.append(result)

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:top_n]


def get_pending_matches() -> list[dict]:
    return [
        {
            "donation_id": "DON-EXAMPLE",
            "status": "pending",
            "matches_found": 0,
            "message": "No pending matches in local memory",
        }
    ]
