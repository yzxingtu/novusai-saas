#!/usr/bin/env python3
"""
Inspect LiteLLM registry in Redis / 检查 Redis 中的模型能力注册表

Usage:
    cd backend && python scripts/inspect_registry_redis.py

Reads ai:litellm:registry and reports key count, sample keys, and enrichment hints.
"""

from __future__ import annotations

import json
import sys

# Add backend to path
sys.path.insert(0, ".")

from app.core.config import settings
from app.tasks.scheduled import LITELLM_REDIS_KEY


def main() -> None:
    import redis

    client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    raw = client.get(LITELLM_REDIS_KEY)
    if not raw:
        print("Redis key not found:", LITELLM_REDIS_KEY)
        return

    registry = json.loads(raw)
    if not isinstance(registry, dict):
        print("Registry is not a dict, type:", type(registry))
        return

    keys = list(registry.keys())
    total = len(keys)
    print(f"=== Redis Registry Inspection / Redis 注册表检查 ===\n")
    print(f"Key: {LITELLM_REDIS_KEY}")
    print(f"Total model keys: {total}\n")

    # Sample keys by provider prefix (LLMRing providers: openai, anthropic, google)
    llmring_providers = ("openai/", "anthropic/", "google/")
    by_provider: dict[str, list[str]] = {p: [] for p in llmring_providers}
    other = []
    for k in keys:
        found = False
        for p in llmring_providers:
            if k.startswith(p) or k == p.rstrip("/"):
                by_provider[p].append(k)
                found = True
                break
        if not found:
            other.append(k)

    print("Sample keys by provider prefix:")
    for p in llmring_providers:
        lst = by_provider[p][:5]
        print(f"  {p}: {lst} ... (total {len(by_provider[p])})")
    print(f"  other: {other[:8]} ... (total {len(other)})\n")

    # Sample a few entries to show structure (capability fields)
    print("Sample entry fields (first 3 keys):")
    for k in keys[:3]:
        entry = registry.get(k, {})
        if isinstance(entry, dict):
            fields = list(entry.keys())
            caps = [f for f in fields if "support" in f or "max_" in f or "cost" in f or "mode" in f]
            print(f"  {k}: {caps[:8]}")

    # Check TTL
    ttl = client.ttl(LITELLM_REDIS_KEY)
    print(f"\nTTL: {ttl}s ({ttl // 86400} days)")
    print("\n=== Done / 完成 ===")


if __name__ == "__main__":
    main()
