from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wellness.api.v1 import router as api_v1_router
from wellness.config import get_settings
from wellness.logging import configure_logging

configure_logging()

app = FastAPI(title="Wellness API")
# Scoped to the frontend's own origin, with credentials allowed — required
# for the refresh-token cookie to flow on cross-origin requests (browsers
# reject allow_origins=["*"] + allow_credentials=True outright; wildcard and
# credentialed requests are mutually exclusive by spec, not just discouraged).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_v1_router)
