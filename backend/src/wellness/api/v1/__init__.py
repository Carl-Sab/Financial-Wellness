from fastapi import APIRouter

from wellness.api.v1 import (
    analysis,
    arousal_state,
    auth,
    bank_accounts,
    bank_ledger,
    categories,
    checkins,
    goals,
    onboarding,
    questionnaire,
    questionnaire_responses,
    samples,
    transactions,
    user_baseline,
    users,
)

router = APIRouter(prefix="/api/v1")
router.include_router(analysis.router)
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(questionnaire.router)
router.include_router(questionnaire_responses.router)
router.include_router(onboarding.router)
router.include_router(checkins.router)
router.include_router(samples.router)
router.include_router(transactions.router)
router.include_router(goals.router)
router.include_router(bank_accounts.router)
router.include_router(bank_ledger.router)
router.include_router(categories.router)
router.include_router(user_baseline.router)
router.include_router(arousal_state.router)
