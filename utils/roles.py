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


def is_saas_default_admin(user: dict | object | None = None) -> bool:
    """
    Returns True if system mode is 'saas' and the user is the default admin user (PIN 7878 or username 'admin').
    """
    try:
        from services.credentials import get_system_mode
        if get_system_mode() != "saas":
            return False

        if not user:
            return False

        uname = ""
        pin = ""
        if isinstance(user, dict):
            uname = str(user.get("username") or user.get("user_name") or "").strip().lower()
            pin = str(user.get("pin") or "").strip()
        else:
            uname = str(getattr(user, "username", "") or getattr(user, "user_name", "") or "").strip().lower()
            pin = str(getattr(user, "pin", "") or "").strip()

        return (uname == "admin" or pin == "7878")
    except Exception:
        return False


def check_and_warn_saas_sale_eligibility(parent_widget, user: dict | object | None = None) -> bool:
    """
    Checks if default admin user in SaaS mode is attempting to perform a sale.
    Displays warning and returns False if ineligible, otherwise True.
    """
    if user is None and parent_widget:
        user = getattr(parent_widget, "user", getattr(getattr(parent_widget, "parent_window", None), "user", None))

    if is_saas_default_admin(user):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            parent_widget,
            "Action Not Allowed",
            "Please log in with your actual account. This account is not eligible to do a sale."
        )
        return False
    return True

