from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class AnalyticsConfig:
    service_name: str
    environment: str = "dev"

