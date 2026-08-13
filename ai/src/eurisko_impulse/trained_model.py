"""Runtime impulse model with a documented prototype interaction override."""

from eurisko_impulse.model import ImpulseModel


NORMALIZATION = {
    "T": {"mu": 2.661558, "std": 0.831699},
    "H": {"mu": 4.636136363636, "std": 1.022405590475},
    "U": {"mu": 4.276041666667, "std": 1.084810087389},
    "N": {"mu": 2.985884, "std": 0.660152},
    "SC": {"mu": 3.037315, "std": 0.660859},
    "arousal_z": {"mu": 0.0, "std": 1.0},
}


model = ImpulseModel(
    base_coefficients={
        "T": 0.14,
        "H": 0.11,
        "U": 0.54,
        "N": -0.44,
        "M": 0.17,
        "SC": -0.53,
        "PM": 0.33,
        "NM": 0.19,
    },
    theta_arousal=0.307339295779,
    # Product-rule override: negative valence reverses the arousal effect.
    theta_arousal_valence=0.35,
)
