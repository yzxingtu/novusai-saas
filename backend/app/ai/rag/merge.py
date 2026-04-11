"""
Result merge helpers for hybrid retrieval.
"""

from __future__ import annotations

import math
from typing import Any

RRF_K = 60


class WeightedRRFMerger:
    @staticmethod
    def weight_factor(weight: float) -> float:
        safe_weight = max(0.1, min(2.0, float(weight)))
        return max(0.65, min(1.25, 0.5 + (math.sqrt(safe_weight) / 2)))

    @classmethod
    def merge(
        cls,
        *,
        search_lists: list[tuple[Any, str, list[Any]]],
        top_k: int,
    ) -> list[Any]:
        if not search_lists:
            return []

        score_map: dict[int, tuple[float, Any]] = {}
        rrf_max = 0.0
        for context, source, results in search_lists:
            if not results:
                continue
            weight_factor = cls.weight_factor(float(getattr(context, "weight", 1.0)))
            rrf_max += weight_factor / (RRF_K + 1)
            for rank, result in enumerate(results, start=1):
                contribution = weight_factor / (RRF_K + rank)
                if result.chunk_id in score_map:
                    merged_score, merged_result = score_map[result.chunk_id]
                    merged_result.recall_sources = sorted(
                        set(merged_result.recall_sources) | {source}
                    )
                    if result.raw_score is not None:
                        merged_result.raw_score = max(
                            merged_result.raw_score or 0.0,
                            result.raw_score,
                        )
                    merged_result.kb_weight = float(getattr(context, "weight", 1.0))
                    score_map[result.chunk_id] = (
                        merged_score + contribution,
                        merged_result,
                    )
                    continue

                cloned = type(result)(**result.to_dict())
                cloned.recall_sources = sorted(set(cloned.recall_sources) | {source})
                cloned.kb_weight = float(getattr(context, "weight", 1.0))
                if cloned.raw_score is None:
                    cloned.raw_score = result.score
                score_map[result.chunk_id] = (contribution, cloned)

        if not score_map:
            return []

        sorted_items = sorted(
            score_map.values(),
            key=lambda item: item[0],
            reverse=True,
        )
        results: list[Any] = []
        for weighted_rrf, chunk_result in sorted_items[:top_k]:
            normalized = min(weighted_rrf / max(rrf_max, 1e-9), 1.0)
            chunk_result.fusion_score = round(normalized, 4)
            chunk_result.score = chunk_result.fusion_score
            results.append(chunk_result)
        return results


def merge_best_results(
    best_results: dict[int, Any],
    batch: list[Any],
) -> None:
    for result in batch:
        current = best_results.get(result.chunk_id)
        if current is None:
            best_results[result.chunk_id] = result
            continue
        current.recall_sources = sorted(
            set(current.recall_sources) | set(result.recall_sources)
        )
        if result.raw_score is not None:
            current.raw_score = max(current.raw_score or 0.0, result.raw_score)
        if result.fusion_score is not None:
            current.fusion_score = max(
                current.fusion_score or 0.0,
                result.fusion_score,
            )
        current.score = max(current.score, result.score)


__all__ = ["WeightedRRFMerger", "merge_best_results", "RRF_K"]
