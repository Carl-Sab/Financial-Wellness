from fastapi import APIRouter

from wellness.api.v1 import (
    analysis,
    auth,
    bank_accounts,
    categories,
    checkins,
    goals,
    monthly_goals,
    onboarding,
    questionnaire,
    questionnaire_responses,
    spending,
    transactions,
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
router.include_router(transactions.router)
router.include_router(goals.router)
router.include_router(monthly_goals.router)
router.include_router(bank_accounts.router)
router.include_router(categories.router)
router.include_router(spending.router)
