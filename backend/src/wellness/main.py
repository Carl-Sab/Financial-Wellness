from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wellness.api.v1 import router as api_v1_router
from wellness.logging import configure_logging

configure_logging()

app = FastAPI(title="Wellness API")
# Smoke-test-only CORS, matching the rest of api/v1/'s "no auth yet" posture —
# tighten before this is exposed beyond local dev.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.include_router(api_v1_router)
