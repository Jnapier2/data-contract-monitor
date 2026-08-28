from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd


def write_demo_dataset(path: Path, *, valid: bool) -> Path:
    now = datetime.now(UTC)
    if valid:
        frame = pd.DataFrame(
            {
                "order_id": ["ORD-1001", "ORD-1002", "ORD-1003"],
                "customer_id": ["CUS-10", "CUS-11", "CUS-12"],
                "order_date": [now - timedelta(hours=2), now - timedelta(hours=1), now],
                "total_amount": [49.95, 125.0, 9.99],
                "status": ["paid", "paid", "pending"],
                "customer_email": ["a@example.com", "b@example.com", "c@example.com"],
            }
        )
    else:
        frame = pd.DataFrame(
            {
                "order_id": ["ORD-1001", "ORD-1001", None],
                "customer_id": ["CUS-10", None, "CUS-12"],
                "order_date": [now - timedelta(days=8), "not-a-date", now],
                "total_amount": [49.95, -12.0, "unknown"],
                "status": ["paid", "mystery", "pending"],
                "customer_email": ["a@example.com", "not-email", "c@example.com"],
                "customer_ssn": ["123-45-6789", "987-65-4321", "111-22-3333"],
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path
