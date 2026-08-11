# Eurisko Combined Prediction

This inference-only bundle executes three models as one pipeline:

1. The CASE model predicts a continuous arousal rating.
2. The rating is standardized against the emotional CASE training distribution.
3. The impulse model receives that `arousal_z` and calculates `Z_IB`.
4. That exact `Z_IB` is passed directly to the overspending model.
5. The overspending model returns the final probability and decision.

Only the three runtime arousal modules are included. The CASE dataset, feature
extraction, training, model comparison, and export code are deliberately absent.

## Run

Edit the values in `AROUSAL_INPUTS`, `IMPULSE_INPUTS`, and `BUDGET_INPUTS` in
`prediction_inputs.py`, then run:

```powershell
cd C:\Users\uac\Desktop\Combined_Prediction
uv sync
uv run python prediction_inputs.py
```

The user supplies five already-derived neutral-relative features between `-3`
and `3`; they are not raw sensor samples. During warm-up, the pipeline supplies
zero temporal deltas. If values from 30 seconds earlier are provided through
`run_pipeline(arousal_inputs_30_seconds_ago=...)`, it calculates real deltas.
The output includes the CASE score, the standardized arousal value passed to the
impulse model, the impulse calculation, `z_ib_passed`, and the final overspending
probability and decision.
There is deliberately no editable `arousal_z` or `z_ib` field.

## Import the combined pipeline

```python
from prediction_inputs import run_pipeline

result = run_pipeline()
print(result["overspending"]["probability"])
```

All three model packages are namespace packages, so the project contains no `__init__.py` files.

## Prototype interaction rule

The runtime uses a prototype arousal-valence interaction coefficient of `0.35`.
This manually selected rule makes increasing arousal lower predicted risk for
negative valence and raise predicted risk for neutral or positive valence. It has
not been refitted or validated against new overspending outcome data.

## Docker

Start Docker Desktop, then build and run the one-shot prediction container:

```powershell
cd C:\Users\uac\Desktop\Combined_Prediction
docker compose build
docker compose run --rm prediction
```

After editing `prediction_inputs.py`, rebuild before running again:

```powershell
docker compose build
docker compose run --rm prediction
```

The image contains only `prediction_inputs.py` and the three inference packages
under `src/`. It does not contain the local virtual environment or training data.
