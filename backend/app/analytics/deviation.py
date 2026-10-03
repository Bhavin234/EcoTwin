"""
Deviation Engine (docs Milestone 3, requirement #4).

Turns (actual, baseline_mean, baseline_stddev) into a z-score, a
percentage deviation, and an absolute deviation — with explicit, documented
handling for the two ways this arithmetic normally breaks: a baseline
standard deviation of (near) zero, and a baseline mean of (near) zero.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.analytics.config import MIN_STDDEV_FLOOR, NEAR_ZERO_MEAN_EPSILON
from app.models.resource import ResourceType


@dataclass(frozen=True)
class DeviationResult:
    z_score: float
    deviation_pct: float | None  # None when the baseline mean is too close to zero for a % to be meaningful
    absolute_deviation: float


def compute_deviation(actual: float, baseline_mean: float, baseline_stddev: float, resource_type: ResourceType) -> DeviationResult:
    """
    Compute deviation metrics for one measurement against its baseline.

    - `z_score` uses a floored standard deviation (`MIN_STDDEV_FLOOR`) so a
      baseline that happens to have near-zero natural variance (e.g. a
      resource that reads almost exactly the same value every closed-hour
      night) doesn't produce an unstable, near-infinite z-score for a
      trivial absolute change — while a genuinely large absolute deviation
      still produces a large z-score.
    - `deviation_pct` is `None` rather than a distorted number when the
      baseline mean itself is below `NEAR_ZERO_MEAN_EPSILON` — dividing by
      a near-zero baseline produces a percentage that looks dramatic
      (e.g. "4000% above baseline") without being a meaningful summary;
      the z-score and absolute deviation remain valid and are used instead.
    """
    floor = MIN_STDDEV_FLOOR[resource_type]
    effective_stddev = max(baseline_stddev, floor)
    z_score = (actual - baseline_mean) / effective_stddev

    epsilon = NEAR_ZERO_MEAN_EPSILON[resource_type]
    deviation_pct = ((actual - baseline_mean) / baseline_mean * 100) if baseline_mean > epsilon else None

    absolute_deviation = actual - baseline_mean

    return DeviationResult(z_score=z_score, deviation_pct=deviation_pct, absolute_deviation=absolute_deviation)
