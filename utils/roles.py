# =============================================================================
# utils/roles.py  —  Small role predicates used across dialogs/views
# =============================================================================


def is_pharmacist(user: dict | None) -> bool:
    """
    Case-insensitive match on the user dict's 'role' field.
    ERPNext role names are typically title-case but misconfig is common,
    so normalise before comparing.
    """
    if not user:
        return False
    role = (user.get("role") or "").strip()
    return role.lower() == "pharmacist"
