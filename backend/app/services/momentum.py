from datetime import datetime


def score_momentum(
    arrivals: list[datetime], now: datetime, momentum_half_life_hours: float = 24.0
) -> float:
    if not arrivals:
        return 0.0
    total = 0.0
    for arrival in arrivals:
        age_hours = (now - arrival).total_seconds() / 3600
        weight = 0.5 ** (age_hours / momentum_half_life_hours)
        total += weight
    return total


def is_stale(arrivals: list[datetime], now: datetime, momentum_stale_hours: float) -> bool:
    if not arrivals:
        return True
    newest = max(arrivals)
    return (now - newest).total_seconds() / 3600 >= momentum_stale_hours
