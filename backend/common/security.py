"""Small demo RBAC guard; replace header identity with SSO in a real deployment."""
from fastapi import Header, HTTPException

ROLE_PERMISSIONS = {
    "relationship_manager": {"case:create", "case:run", "case:supplement"},
    "approver": {"case:approve", "case:reject"},
    "operator": {"case:commit"},
    "auditor": {"audit:read"},
    "admin": {"*"},
}

def require(permission: str, x_demo_role: str = Header("relationship_manager")) -> str:
    if permission not in ROLE_PERMISSIONS.get(x_demo_role, set()) and "*" not in ROLE_PERMISSIONS.get(x_demo_role, set()):
        raise HTTPException(status_code=403, detail="RBAC permission denied")
    return x_demo_role


def permission_dependency(permission: str):
    def dependency(x_demo_role: str = Header("relationship_manager")) -> str:
        return require(permission, x_demo_role)
    return dependency
