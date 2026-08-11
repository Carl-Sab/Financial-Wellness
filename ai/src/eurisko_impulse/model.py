"""Prediction logic for the standalone Eurisko impulse-buying index."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class ImpulsePrediction:
    """Complete, auditable breakdown of one model prediction."""

    t_z: float
    h_z: float
    u_z: float
    n_z: float
    sc_z: float
    marketing_score: float
    pm_proxy: float
    nm_proxy: float
    fixed_base: float
    valence_component: float
    arousal_main_effect: float
    arousal_valence_effect: float
    z_ib: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class ImpulseModel:
    """Configured prediction model containing fixed and fitted coefficients."""

    base_coefficients: Mapping[str, float]
    marketing_scores: Mapping[str, float]
    theta_arousal: float
    theta_arousal_valence: float

    def _validate_number(self, name: str, value: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if not isfinite(numeric):
            raise ValueError(f"{name} must be finite")
        return numeric

    def _validate_range(self, name: str, value: float, low: float, high: float) -> float:
        numeric = self._validate_number(name, value)
        if not low <= numeric <= high:
            raise ValueError(f"{name} must be between {low:g} and {high:g}")
        return numeric

    def _z_score(
        self,
        key: str,
        value: float,
        normalization: Mapping[str, Mapping[str, float]],
    ) -> float:
        if key not in normalization:
            raise ValueError(f"Missing normalization values for {key}")
        values = normalization[key]
        if "mu" not in values or "std" not in values:
            raise ValueError(f"Normalization for {key} requires mu and std")
        mu = self._validate_number(f"{key}.mu", values["mu"])
        std = self._validate_number(f"{key}.std", values["std"])
        if std <= 0:
            raise ValueError(f"{key}.std must be greater than zero")
        return (value - mu) / std

    def predict(
        self,
        *,
        normalization: Mapping[str, Mapping[str, float]],
        buying_impulsiveness: float,
        hedonic_value: float,
        utilitarian_value: float,
        normative_evaluation: float,
        self_control: float,
        store_category: str,
        valence: int,
        arousal_z: float,
    ) -> ImpulsePrediction:
        """Predict Z_IB from raw construct means and contextual inputs."""

        t = self._validate_range("buying_impulsiveness", buying_impulsiveness, 1, 5)
        h = self._validate_range("hedonic_value", hedonic_value, 1, 7)
        u = self._validate_range("utilitarian_value", utilitarian_value, 1, 7)
        n = self._validate_range("normative_evaluation", normative_evaluation, 1, 5)
        sc = self._validate_range("self_control", self_control, 1, 5)
        a = self._validate_number("arousal_z", arousal_z)

        if isinstance(valence, bool) or valence not in {-2, -1, 0, 1, 2}:
            raise ValueError("valence must be one of -2, -1, 0, 1, or 2")
        if not isinstance(store_category, str) or not store_category.strip():
            raise ValueError("store_category must be a non-empty string")

        t_z = self._z_score("T", t, normalization)
        h_z = self._z_score("H", h, normalization)
        u_z = self._z_score("U", u, normalization)
        n_z = self._z_score("N", n, normalization)
        sc_z = self._z_score("SC", sc, normalization)

        category_lookup = {
            key.casefold(): float(value) for key, value in self.marketing_scores.items()
        }
        marketing_score = category_lookup.get(
            store_category.strip().casefold(), category_lookup["other"]
        )
        pm_proxy = float(max(valence, 0))
        nm_proxy = float(max(-valence, 0))

        fixed_base = (
            self.base_coefficients["T"] * t_z
            + self.base_coefficients["H"] * h_z
            + self.base_coefficients["U"] * u_z
            + self.base_coefficients["N"] * n_z
            + self.base_coefficients["M"] * marketing_score
            + self.base_coefficients["SC"] * sc_z
        )
        valence_component = (
            self.base_coefficients["PM"] * pm_proxy
            + self.base_coefficients["NM"] * nm_proxy
        )
        arousal_main_effect = self.theta_arousal * a
        arousal_valence_effect = self.theta_arousal_valence * a * valence
        z_ib = (
            fixed_base
            + valence_component
            + arousal_main_effect
            + arousal_valence_effect
        )

        return ImpulsePrediction(
            t_z=t_z,
            h_z=h_z,
            u_z=u_z,
            n_z=n_z,
            sc_z=sc_z,
            marketing_score=marketing_score,
            pm_proxy=pm_proxy,
            nm_proxy=nm_proxy,
            fixed_base=fixed_base,
            valence_component=valence_component,
            arousal_main_effect=arousal_main_effect,
            arousal_valence_effect=arousal_valence_effect,
            z_ib=z_ib,
        )
