from __future__ import annotations

from finresearch.metrics.definitions import (
    available_metric_values,
    calculate_registered_metrics,
    metric_quality_flags,
)


def calculate_metric_signals(matrix: list[dict[str, object]]) -> dict[str, object]:
    if not matrix:
        return {"quality_flags": ["insufficient_structured_data"], "metrics": {}}

    observations = calculate_registered_metrics(matrix)
    metrics = available_metric_values(matrix)

    if "ocf_to_net_profit" in metrics:
        metrics["cash_conversion"] = metrics["ocf_to_net_profit"]
    return {"quality_flags": metric_quality_flags(observations), "metrics": metrics}
