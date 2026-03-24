from app.extensions import db

from .admin_audit_log import AdminAuditLog  # noqa: F401
from .admin_notification_state import AdminNotificationState  # noqa: F401
from .admin_preference import AdminPreference  # noqa: F401
from .audit_log import AuditLog  # noqa: F401
from .authority import Authority  # noqa: F401
from .authority_user import AuthorityUser  # noqa: F401
from .department_action_log import DepartmentActionLog  # noqa: F401
from .department_contact import DepartmentContact  # noqa: F401
from .incident import Incident  # noqa: F401
from .incident_assignment import IncidentAssignment  # noqa: F401
from .incident_category import IncidentCategory  # noqa: F401
from .incident_dispatch import IncidentDispatch  # noqa: F401
from .incident_event import IncidentEvent  # noqa: F401
from .incident_media import IncidentMedia  # noqa: F401
from .incident_ownership_history import IncidentOwnershipHistory  # noqa: F401
from .incident_update import IncidentUpdate  # noqa: F401
from .location import Location  # noqa: F401
from .notification_log import NotificationLog  # noqa: F401
from .resident_notification_state import ResidentNotificationState  # noqa: F401
from .resident_profile import ResidentProfile  # noqa: F401
from .routing_rule import RoutingRule  # noqa: F401
from .user import User  # noqa: F401

__all__ = [
    "db",
    "User",
    "ResidentProfile",
    "Authority",
    "AuthorityUser",
    "Incident",
    "IncidentCategory",
    "IncidentMedia",
    "IncidentUpdate",
    "IncidentAssignment",
    "DepartmentActionLog",
    "DepartmentContact",
    "IncidentDispatch",
    "IncidentEvent",
    "IncidentOwnershipHistory",
    "RoutingRule",
    "Location",
    "NotificationLog",
    "ResidentNotificationState",
    "AdminAuditLog",
    "AdminNotificationState",
    "AdminPreference",
    "AuditLog",
]
