"""中文: 生产验收容量计划，针对 /ready 执行有界 Locust 压测。

EN: Production-acceptance capacity plan for bounded Locust load on /ready.
"""

from __future__ import annotations

import os

from locust import HttpUser, between, task

_TARGET_PATH = os.getenv("CAPACITY_TARGET_PATH", "/ready")


class ReadyCapacityUser(HttpUser):
    wait_time = between(0, 0)

    @task
    def ready(self) -> None:
        with self.client.get(
            _TARGET_PATH, name="/ready", catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"status={response.status_code}")
                return
            try:
                payload = response.json()
            except ValueError as exc:
                response.failure(f"json={exc}")
                return
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, dict) or data.get("ready") is not True:
                response.failure("ready=false")
