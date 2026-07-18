"""Authenticated design endpoints backed only by explicitly synthetic data."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.mock_scenarios import MockScenarioCode, MockScenarioSummary
from app.api.dependencies import PrincipalDep, get_agent_simulation_service
from app.schemas.agent_simulation import AgentSimulationRunRequest
from app.services.access import require_permission
from app.services.agent_simulation_service import (
    AgentSimulationResponse,
    AgentSimulationService,
)

router = APIRouter(prefix="/agent-simulations", tags=["agent-simulations"])


@router.get("/scenarios", response_model=list[MockScenarioSummary])
async def list_agent_simulation_scenarios(
    principal: PrincipalDep,
    service: Annotated[AgentSimulationService, Depends(get_agent_simulation_service)],
) -> list[MockScenarioSummary]:
    require_permission(principal, "loan:analyze")
    return list(service.list_scenarios())


@router.post(
    "/scenarios/{scenario_code}/runs",
    response_model=AgentSimulationResponse,
)
async def run_agent_simulation(
    scenario_code: MockScenarioCode,
    body: AgentSimulationRunRequest,
    principal: PrincipalDep,
    service: Annotated[AgentSimulationService, Depends(get_agent_simulation_service)],
) -> AgentSimulationResponse:
    require_permission(principal, "loan:analyze")
    return await service.run(scenario_code, objective=body.objective)
