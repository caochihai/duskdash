"""Effective-dated policy and clause endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_policy_service
from app.auth.dependencies import require_permissions
from app.auth.principal import CurrentPrincipal
from app.schemas.policy import PolicyClauseResponse, PolicyResponse
from app.services.policy_service import PolicyService

router = APIRouter(tags=["policies"])


@router.get("/policies", response_model=list[PolicyResponse])
async def list_policies(
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("policy:read"))],
    service: Annotated[PolicyService, Depends(get_policy_service)],
    as_of: date | None = None,
) -> list[PolicyResponse]:
    return [PolicyResponse.model_validate(row) for row in await service.list(principal, as_of=as_of)]


@router.get("/policies/search", response_model=list[PolicyClauseResponse])
async def search_policies(
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("policy:read"))],
    service: Annotated[PolicyService, Depends(get_policy_service)],
    query: str = Query(min_length=2, max_length=500),
    as_of: date | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[PolicyClauseResponse]:
    return [
        PolicyClauseResponse.model_validate(row)
        for row in await service.search(principal, query=query, as_of=as_of, limit=limit)
    ]


@router.get("/policy-clauses/{clause_id}", response_model=PolicyClauseResponse)
async def get_policy_clause(
    clause_id: UUID,
    principal: Annotated[CurrentPrincipal, Depends(require_permissions("policy:read"))],
    service: Annotated[PolicyService, Depends(get_policy_service)],
    as_of: date | None = None,
) -> PolicyClauseResponse:
    return PolicyClauseResponse.model_validate(
        await service.clause(principal, clause_id, as_of=as_of)
    )
