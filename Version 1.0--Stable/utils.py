import logging
from datetime import datetime
from typing import Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

DATE_FMT = "%Y-%m-%d %H:%M:%S"


def parse_datetime(dt_str: str) -> Optional[datetime]:
    try:
        return datetime.strptime(dt_str.strip(), DATE_FMT)
    except Exception:
        return None


def in_range(ts, start, end) -> bool:
    if start and ts < start:
        return False
    if end and ts > end:
        return False
    return True