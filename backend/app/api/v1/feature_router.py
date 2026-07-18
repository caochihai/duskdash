"""All backend feature routes under the versioned API prefix."""

from fastapi import APIRouter

from app.api.v1 import (
    agent_simulations,
    analyses,
    audit,
    conversations,
    customers,
    documents,
    findings,
    jobs,
    loans,
    notifications,
    policies,
    reports,
)

router = APIRouter()
router.include_router(agent_simulations.router)
router.include_router(customers.router)
router.include_router(documents.router)
router.include_router(loans.router)
router.include_router(conversations.router)
router.include_router(analyses.router)
router.include_router(findings.router)
router.include_router(reports.router)
router.include_router(jobs.router)
router.include_router(notifications.router)
router.include_router(policies.router)
router.include_router(audit.router)
