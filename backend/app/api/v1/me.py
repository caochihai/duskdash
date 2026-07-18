"""Current employee endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_principal
from app.auth.principal import CurrentPrincipal
from app.schemas.auth import MeResponse

router = APIRouter(prefix="/me", tags=["current-employee"])


@router.get("", response_model=MeResponse, operation_id="get_current_employee")
async def get_me(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> MeResponse:
    return MeResponse(
        employee_id=principal.employee_id,
        subject=principal.subject,
        branch_id=principal.branch_id,
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions),
        is_admin=principal.is_admin,
    )
