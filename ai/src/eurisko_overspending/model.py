"""Runtime prediction logic for the standalone overspending model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp, isfinite
from typing import Mapping


FEATURE_NAMES = ("z_ib", "p_d", "p_w", "p_m")


@dataclass(frozen=True)
class OverspendingPrediction:
    """Auditable breakdown of one overspending-risk prediction."""

    z_ib: float
    daily_budget: float
    daily_spent_before: float
    weekly_budget: float
    weekly_spent_before: float
    monthly_budget: float
    monthly_spent_before: float
    p_d: float
    p_w: float
    p_m: float
    logit: float
    probability: float
    threshold: float
    above_threshold: bool

    def as_dict(self) -> dict[str, float | bool]:
        return asdict(self)


@dataclass(frozen=True)
class OverspendingModel:
    """A small importable logistic-regression model."""

    intercept: float
    coefficients: Mapping[str, float]
    threshold: float = 0.5

    def __post_init__(self) -> None:
        if set(self.coefficients) != set(FEATURE_NAMES):
            raise ValueError(f"coefficients must contain exactly {FEATURE_NAMES}")
        self._validate_finite("intercept", self.intercept)
        for name, value in self.coefficients.items():
            self._validate_finite(f"coefficient {name}", value)
        threshold = self._validate_finite("threshold", self.threshold)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")

    @staticmethod
    def _validate_finite(name: str, value: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if not isfinite(numeric):
            raise ValueError(f"{name} must be finite")
        return numeric

    @classmethod
    def _validate_budget(cls, name: str, value: float) -> float:
        numeric = cls._validate_finite(name, value)
        if numeric <= 0:
            raise ValueError(f"{name} must be greater than zero")
        return numeric

    @staticmethod
    def _sigmoid(logit: float) -> float:
        if logit >= 0:
            return 1.0 / (1.0 + exp(-logit))
        exponential = exp(logit)
        return exponential / (1.0 + exponential)

    def predict(
        self,
        *,
        z_ib: float,
        daily_budget: float,
        daily_spent_before: float,
        weekly_budget: float,
        weekly_spent_before: float,
        monthly_budget: float,
        monthly_spent_before: float,
    ) -> OverspendingPrediction:
        """Predict overspending risk without re-normalizing ``z_ib``."""

        z = self._validate_finite("z_ib", z_ib)
        d_budget = self._validate_budget("daily_budget", daily_budget)
        w_budget = self._validate_budget("weekly_budget", weekly_budget)
        m_budget = self._validate_budget("monthly_budget", monthly_budget)
        d_spent = self._validate_finite("daily_spent_before", daily_spent_before)
        w_spent = self._validate_finite("weekly_spent_before", weekly_spent_before)
        m_spent = self._validate_finite("monthly_spent_before", monthly_spent_before)

        p_d = d_spent / d_budget
        p_w = w_spent / w_budget
        p_m = m_spent / m_budget
        values = {
            "z_ib": z,
            "p_d": p_d,
            "p_w": p_w,
            "p_m": p_m,
        }
        logit = float(self.intercept) + sum(
            float(self.coefficients[name]) * values[name] for name in FEATURE_NAMES
        )
        probability = self._sigmoid(logit)

        return OverspendingPrediction(
            z_ib=z,
            daily_budget=d_budget,
            daily_spent_before=d_spent,
            weekly_budget=w_budget,
            weekly_spent_before=w_spent,
            monthly_budget=m_budget,
            monthly_spent_before=m_spent,
            p_d=p_d,
            p_w=p_w,
            p_m=p_m,
            logit=logit,
            probability=probability,
            threshold=float(self.threshold),
            above_threshold=probability >= float(self.threshold),
        )
