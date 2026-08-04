from fastapi import FastAPI

from wellness.api.v1 import router as api_v1_router
from wellness.logging import configure_logging

configure_logging()

app = FastAPI(title="Wellness API")
app.include_router(api_v1_router)
