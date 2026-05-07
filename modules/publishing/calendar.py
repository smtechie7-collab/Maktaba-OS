"""
Scheduled publishing and content calendars.

This module tracks editorial calendar items and concrete scheduled publication
jobs. It does not push to external channels yet; instead it gives the rest of
the app a durable queue of what is due, what was published, and what needs
attention.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from infrastructure.auth.audit import ComplianceAuditManager
from infrastructure.auth.notifications import NotificationManager


@dataclass
class ContentCalendarItem:
    """Editorial calendar item for a project, book, or campaign."""
    id: int
    organization_id: Optional[int]
    project_id: Optional[int]
    title: str
    description: Optional[str]
    content_type: str
    target_date: datetime
    owner_id: int
    status: str
    created_at: datetime
    is_active: bool


@dataclass
class ScheduledPublication:
    """Publication job scheduled for a channel."""
    id: int
    calendar_item_id: int
    book_id: Optional[int]
    channel: str
    scheduled_for: datetime
    status: str
    created_by: int
    published_at: Optional[datetime]
    failure_reason: Optional[str]
    created_at: datetime


class PublishingCalendarManager:
    """Manages editorial calendars and scheduled publication jobs."""

    def __init__(
        self,
        db_connection: sqlite3.Connection,
        audit_manager: Optional[ComplianceAuditManager] = None,
        notification_manager: Optional[NotificationManager] = None,
    ):
        self.db = db_connection
        self.audit = audit_manager or ComplianceAuditManager(db_connection)
        self.notifications = notification_manager or NotificationManager(db_connection, self.audit)
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure publishing calendar schema exists."""
        with self.db:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS ContentCalendarItems (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER,
                    project_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    content_type TEXT NOT NULL,
                    target_date TIMESTAMP NOT NULL,
                    owner_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'planned',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (owner_id) REFERENCES Users(id)
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS ScheduledPublications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    calendar_item_id INTEGER NOT NULL,
                    book_id INTEGER,
                    channel TEXT NOT NULL,
                    scheduled_for TIMESTAMP NOT NULL,
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    created_by INTEGER NOT NULL,
                    published_at TIMESTAMP,
                    failure_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (calendar_item_id) REFERENCES ContentCalendarItems(id) ON DELETE CASCADE,
                    FOREIGN KEY (created_by) REFERENCES Users(id),
                    UNIQUE(calendar_item_id, channel)
                )
            """)

    def create_calendar_item(
        self,
        title: str,
        content_type: str,
        target_date: datetime,
        owner_id: int,
        organization_id: Optional[int] = None,
        project_id: Optional[int] = None,
        description: Optional[str] = None,
        reminder_before: timedelta = timedelta(days=2),
    ) -> ContentCalendarItem:
        """Create an editorial calendar item and schedule an owner reminder."""
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO ContentCalendarItems
                (organization_id, project_id, title, description, content_type, target_date, owner_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                organization_id,
                project_id,
                title,
                description,
                content_type,
                target_date,
                owner_id,
            ))
            item_id = cursor.lastrowid

            self.audit.record_event(
                action="calendar.item.create",
                resource_type="calendar_item",
                resource_id=item_id,
                user_id=owner_id,
                details=f"Created calendar item '{title}' for {target_date.isoformat()}",
            )
            self.notifications.schedule_deadline_reminder(
                user_id=owner_id,
                resource_type="calendar_item",
                resource_id=item_id,
                title=title,
                due_at=target_date,
                remind_before=reminder_before,
            )

        return self.get_calendar_item(item_id)

    def get_calendar_item(self, item_id: int) -> Optional[ContentCalendarItem]:
        """Get a calendar item by ID."""
        row = self.db.execute("""
            SELECT id, organization_id, project_id, title, description, content_type,
                   target_date, owner_id, status, created_at, is_active
            FROM ContentCalendarItems
            WHERE id = ?
        """, (item_id,)).fetchone()

        return self._row_to_calendar_item(row) if row else None

    def list_calendar_items(
        self,
        organization_id: Optional[int] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> List[ContentCalendarItem]:
        """List active calendar items with optional filters."""
        query = """
            SELECT id, organization_id, project_id, title, description, content_type,
                   target_date, owner_id, status, created_at, is_active
            FROM ContentCalendarItems
            WHERE is_active = 1
        """
        params = []
        if organization_id is not None:
            query += " AND organization_id = ?"
            params.append(organization_id)
        if start is not None:
            query += " AND target_date >= ?"
            params.append(start)
        if end is not None:
            query += " AND target_date <= ?"
            params.append(end)
        if status is not None:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY target_date ASC, id ASC"
        cursor = self.db.execute(query, params)
        return [self._row_to_calendar_item(row) for row in cursor.fetchall()]

    def schedule_publication(
        self,
        calendar_item_id: int,
        channel: str,
        scheduled_for: datetime,
        created_by: int,
        book_id: Optional[int] = None,
    ) -> ScheduledPublication:
        """Schedule a publication job for a channel."""
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO ScheduledPublications
                (calendar_item_id, book_id, channel, scheduled_for, created_by)
                VALUES (?, ?, ?, ?, ?)
            """, (calendar_item_id, book_id, channel, scheduled_for, created_by))
            publication_id = cursor.lastrowid

            self.db.execute("""
                UPDATE ContentCalendarItems
                SET status = 'scheduled'
                WHERE id = ?
            """, (calendar_item_id,))

            self.audit.record_event(
                action="publication.schedule",
                resource_type="scheduled_publication",
                resource_id=publication_id,
                user_id=created_by,
                details=f"Scheduled publication for calendar item {calendar_item_id} on {channel}",
            )

        return self.get_scheduled_publication(publication_id)

    def get_scheduled_publication(self, publication_id: int) -> Optional[ScheduledPublication]:
        """Get a scheduled publication by ID."""
        row = self.db.execute("""
            SELECT id, calendar_item_id, book_id, channel, scheduled_for, status,
                   created_by, published_at, failure_reason, created_at
            FROM ScheduledPublications
            WHERE id = ?
        """, (publication_id,)).fetchone()

        return self._row_to_publication(row) if row else None

    def get_due_publications(self, now: Optional[datetime] = None, limit: int = 100) -> List[ScheduledPublication]:
        """Return scheduled publication jobs that are due."""
        now = now or datetime.now()
        cursor = self.db.execute("""
            SELECT id, calendar_item_id, book_id, channel, scheduled_for, status,
                   created_by, published_at, failure_reason, created_at
            FROM ScheduledPublications
            WHERE status = 'scheduled' AND scheduled_for <= ?
            ORDER BY scheduled_for ASC, id ASC
            LIMIT ?
        """, (now, limit))

        return [self._row_to_publication(row) for row in cursor.fetchall()]

    def mark_published(
        self,
        publication_id: int,
        published_at: Optional[datetime] = None,
    ) -> bool:
        """Mark a scheduled publication as published."""
        publication = self.get_scheduled_publication(publication_id)
        if not publication:
            return False

        published_at = published_at or datetime.now()
        with self.db:
            cursor = self.db.execute("""
                UPDATE ScheduledPublications
                SET status = 'published', published_at = ?, failure_reason = NULL
                WHERE id = ?
            """, (published_at, publication_id))
            if cursor.rowcount == 0:
                return False

            remaining = self.db.execute("""
                SELECT COUNT(*)
                FROM ScheduledPublications
                WHERE calendar_item_id = ? AND status != 'published'
            """, (publication.calendar_item_id,)).fetchone()[0]
            if remaining == 0:
                self.db.execute("""
                    UPDATE ContentCalendarItems
                    SET status = 'published'
                    WHERE id = ?
                """, (publication.calendar_item_id,))

            self.audit.record_event(
                action="publication.publish",
                resource_type="scheduled_publication",
                resource_id=publication_id,
                user_id=publication.created_by,
                details=f"Published scheduled publication {publication_id}",
            )

        return True

    def mark_failed(self, publication_id: int, failure_reason: str) -> bool:
        """Mark a scheduled publication as failed."""
        publication = self.get_scheduled_publication(publication_id)
        if not publication:
            return False

        with self.db:
            cursor = self.db.execute("""
                UPDATE ScheduledPublications
                SET status = 'failed', failure_reason = ?
                WHERE id = ?
            """, (failure_reason, publication_id))
            if cursor.rowcount == 0:
                return False

            self.audit.record_event(
                action="publication.fail",
                resource_type="scheduled_publication",
                resource_id=publication_id,
                user_id=publication.created_by,
                details=f"Publication failed: {failure_reason}",
                severity="warning",
            )

        return True

    def cancel_publication(self, publication_id: int, cancelled_by: int) -> bool:
        """Cancel a scheduled publication."""
        with self.db:
            cursor = self.db.execute("""
                UPDATE ScheduledPublications
                SET status = 'cancelled'
                WHERE id = ? AND status = 'scheduled'
            """, (publication_id,))
            if cursor.rowcount == 0:
                return False

            self.audit.record_event(
                action="publication.cancel",
                resource_type="scheduled_publication",
                resource_id=publication_id,
                user_id=cancelled_by,
                details=f"Cancelled scheduled publication {publication_id}",
            )

        return True

    def _row_to_calendar_item(self, row) -> ContentCalendarItem:
        """Convert a SQLite row or tuple to a calendar item."""
        return ContentCalendarItem(
            id=row[0],
            organization_id=row[1],
            project_id=row[2],
            title=row[3],
            description=row[4],
            content_type=row[5],
            target_date=datetime.fromisoformat(row[6]),
            owner_id=row[7],
            status=row[8],
            created_at=datetime.fromisoformat(row[9]),
            is_active=bool(row[10]),
        )

    def _row_to_publication(self, row) -> ScheduledPublication:
        """Convert a SQLite row or tuple to a scheduled publication."""
        return ScheduledPublication(
            id=row[0],
            calendar_item_id=row[1],
            book_id=row[2],
            channel=row[3],
            scheduled_for=datetime.fromisoformat(row[4]),
            status=row[5],
            created_by=row[6],
            published_at=datetime.fromisoformat(row[7]) if row[7] else None,
            failure_reason=row[8],
            created_at=datetime.fromisoformat(row[9]),
        )
