FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY src/eurisko_arousal /app/src/eurisko_arousal
COPY src/eurisko_impulse /app/src/eurisko_impulse
COPY src/eurisko_overspending /app/src/eurisko_overspending
COPY prediction_inputs.py /app/prediction_inputs.py

USER appuser

CMD ["python", "prediction_inputs.py"]
