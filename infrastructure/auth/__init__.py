"""
Authentication and authorization infrastructure for Maktaba-OS.
"""

from .user_manager import UserManager, User, Role, Permission, get_user_manager
from .workspace import WorkspaceManager, Workspace, WorkspaceMember, Project, ProjectMember
from .audit import ComplianceAuditManager, ComplianceAuditEvent
from .workflow import WorkflowManager, Workflow, WorkflowStage, WorkflowRun, WorkflowTransition
from .notifications import NotificationManager, Notification

__all__ = [
    'UserManager',
    'User',
    'Role',
    'Permission',
    'get_user_manager',
    'WorkspaceManager',
    'Workspace',
    'WorkspaceMember',
    'Project',
    'ProjectMember',
    'ComplianceAuditManager',
    'ComplianceAuditEvent',
    'WorkflowManager',
    'Workflow',
    'WorkflowStage',
    'WorkflowRun',
    'WorkflowTransition',
    'NotificationManager',
    'Notification',
]
