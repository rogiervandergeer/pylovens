from datetime import datetime
from zoneinfo import ZoneInfo


def parse_datetimes(data: dict[str], keys: set[str], timezone: ZoneInfo) -> dict[str]:
    """Parse datetimes in a dictionary."""
    return {
        key: datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone) if key in keys else value
        for key, value in data.items()
    }
