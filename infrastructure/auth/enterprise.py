"""
Integration layer combining RBAC and organization management.

This module coordinates role-based access control with organizational structures,
enabling organization-wide permission management and hierarchical access control.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from infrastructure.auth.rbac import GranularAccessControl, ResourcePermission
from infrastructure.auth.organization import OrganizationManager, Organization

logger = logging.getLogger(__name__)


class EnterpriseAccessManager:
    """
    Unified manager for organization-level access control.
    
    Combines RBAC and organization management to provide:
    - Organization-wide permission inheritance
    - Department-based access delegation
    - Role hierarchy within organizations
    - Cross-organization permission boundaries
    """

    def __init__(self, rbac: GranularAccessControl, org_manager: OrganizationManager):
        self.rbac = rbac
        self.org = org_manager

    def grant_organization_permission(
        self,
        organization_id: int,
        user_id: Optional[int] = None,
        role_id: Optional[int] = None,
        access_level: str = "viewer",
        granted_by: int = None,
        reason: Optional[str] = None
    ) -> ResourcePermission:
        """Grant permission on organization resource."""
        return self.rbac.grant_permission(
            resource_type="organization",
            resource_id=organization_id,
            user_id=user_id,
            role_id=role_id,
            access_level=access_level,
            granted_by=granted_by,
            reason=reason
        )

    def can_manage_organization(self, user_id: int, org_id: int) -> bool:
        """Check if user can manage (admin level) organization."""
        member = self.org.get_member(org_id, user_id)
        if member and member.role in ("owner", "admin"):
            return True

        # Also check RBAC for org resource
        return self.rbac.can_perform_action(user_id, "organization", org_id, "admin")

    def can_access_organization(self, user_id: int, org_id: int) -> bool:
        """Check if user can access organization."""
        member = self.org.get_member(org_id, user_id)
        if member and member.is_active:
            return True

        return self.rbac.can_perform_action(user_id, "organization", org_id, "read")

    def get_user_documents(
        self,
        user_id: int,
        org_id: Optional[int] = None
    ) -> List[Dict]:
        """Get all documents accessible to user."""
        documents = []

        if org_id:
            # Get documents in specific organization
            if not self.can_access_organization(user_id, org_id):
                return []

            # TODO: Query documents by organization
            # This would query from document database
            pass
        else:
            # Get documents from all accessible organizations
            orgs = self.org.get_user_organizations(user_id)
            for org in orgs:
                # TODO: Query documents by organization
                # This would query from document database
                pass

        return documents

    def assign_document_to_department(
        self,
        document_id: int,
        organization_id: int,
        department_id: int,
        access_level: str = "editor"
    ) -> bool:
        """Assign document to department for team collaboration."""
        dept = self.org.get_department(department_id)
        if not dept or dept.organization_id != organization_id:
            logger.warning(f"Invalid department {department_id} for org {organization_id}")
            return False

        members = self.org.get_organization_members(organization_id, department_id)
        for member in members:
            self.rbac.grant_permission(
                resource_type="document",
                resource_id=document_id,
                user_id=member.user_id,
                access_level=access_level,
                granted_by=0,  # System action
                reason=f"Department assignment to {dept.name}"
            )

        logger.info(f"Document {document_id} assigned to dept {department_id} with {access_level}")
        return True

    def propagate_org_permission_to_documents(
        self,
        organization_id: int,
        user_id: int,
        access_level: str
    ) -> int:
        """
        Propagate organization permission to all documents in org.
        
        Returns count of documents updated.
        """
        # TODO: Query documents in organization
        # This would need document database integration
        count = 0
        logger.info(f"Propagated {access_level} permission for user {user_id} to {count} documents")
        return count

    def revoke_organization_access(
        self,
        organization_id: int,
        user_id: int,
        revoke_documents: bool = True
    ) -> bool:
        """
        Revoke user's access to organization and optionally all org documents.
        """
        # Remove from organization
        removed = self.org.remove_member(organization_id, user_id)

        if removed and revoke_documents:
            # TODO: Revoke document permissions
            # This would revoke all user's permissions for org documents
            pass

        logger.info(f"Revoked org access for user {user_id} in org {organization_id}")
        return removed

    def get_organization_access_report(self, org_id: int) -> Dict:
        """Generate access report for organization."""
        org = self.org.get_organization(org_id)
        if not org:
            return {}

        members = self.org.get_organization_members(org_id)
        depts = self.org.get_organization_departments(org_id)

        # Get audit logs for organization
        audit_logs = self.rbac.get_permission_audit_log(
            resource_type="organization",
            resource_id=org_id,
            limit=100
        )

        return {
            "organization": org,
            "total_members": len(members),
            "members_by_role": self._count_by_role(members),
            "total_departments": len(depts),
            "recent_audit_logs": audit_logs,
            "last_modified": audit_logs[0].timestamp if audit_logs else None
        }

    def _count_by_role(self, members) -> Dict[str, int]:
        """Count members by role."""
        counts = {}
        for member in members:
            role = member.role
            counts[role] = counts.get(role, 0) + 1
        return counts

    def create_organization_with_hierarchy(
        self,
        org_name: str,
        owner_id: int,
        departments: List[Dict]
    ) -> Organization:
        """Create organization with initial department structure."""
        org = self.org.create_organization(org_name, owner_id)

        for dept_info in departments:
            self.org.create_department(
                org.id,
                name=dept_info["name"],
                description=dept_info.get("description"),
                manager_id=dept_info.get("manager_id")
            )

        logger.info(f"Created organization {org_name} with {len(departments)} departments")
        return org

    def get_effective_permissions(
        self,
        user_id: int,
        resource_type: str,
        resource_id: int
    ) -> Dict:
        """
        Get all effective permissions for a user on a resource.
        
        Combines:
        - Direct user permissions
        - Role-based permissions
        - Organization-level permissions
        - Department-level permissions (if applicable)
        """
        perms = self.rbac.get_resource_permissions(resource_type, resource_id)

        effective = {
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "direct_permissions": [],
            "role_permissions": [],
            "organization_permissions": [],
            "effective_access_level": None
        }

        for perm in perms:
            if perm.user_id == user_id:
                effective["direct_permissions"].append(perm.access_level)
            elif perm.role_id:
                effective["role_permissions"].append(perm.access_level)

        # Get highest access level
        all_levels = ["owner", "admin", "editor", "reviewer", "commenter", "viewer"]
        for level in all_levels:
            if level in effective["direct_permissions"] or level in effective["role_permissions"]:
                effective["effective_access_level"] = level
                break

        return effective
