from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ConsumptionRecord:
    id: Optional[int]  # Database Primary Key
    student_id: str
    name: str
    major: str
    grade: str
    balance: float
    timestamp: datetime
    amount: float
    merchant_type: str
    location: str
    tx_type: str  # 消费/充值等