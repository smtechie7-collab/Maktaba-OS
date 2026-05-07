"""
Tests for scheduled publishing and content calendars.
"""

import sqlite3
from datetime import datetime, timedelta

import pytest

from infrastructure.auth.audit import ComplianceAuditManager
from infrastructure.auth.notifications import NotificationManager
from modules.publishing import PublishingCalendarManager


@pytest.fixture
def managers():
    """Create publishing calendar test managers."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)
    conn.execute("INSERT INTO Users (username, email, password_hash) VALUES (?, ?, ?)", ("owner", "owner@example.com", "hash"))
    conn.commit()

    audit = ComplianceAuditManager(conn)
    notifications = NotificationManager(conn, audit)
    calendar = PublishingCalendarManager(conn, audit, notifications)
    return conn, audit, notifications, calendar


def test_create_calendar_item_schedules_owner_reminder(managers):
    """Calendar items should create deadline reminders for their owner."""
    _conn, audit, notifications, calendar = managers
    target_date = datetime.now() + timedelta(days=7)

    item = calendar.create_calendar_item(
        title="Friday Release",
        content_type="article",
        target_date=target_date,
        owner_id=1,
        organization_id=2,
        project_id=3,
    )

    assert item.title == "Friday Release"
    assert item.status == "planned"

    inbox = notifications.get_user_notifications(1)
    assert inbox[0].notification_type == "deadline_reminder"
    assert inbox[0].resource_type == "calendar_item"

    events = audit.get_resource_timeline("calendar_item", item.id)
    assert [event.action for event in events if event.action != "notification.create"] == [
        "calendar.item.create"
    ]


def test_list_calendar_items_by_window_and_status(managers):
    """Calendar list queries should support date and status filters."""
    _conn, _audit, _notifications, calendar = managers
    now = datetime.now()
    first = calendar.create_calendar_item("Draft", "book", now + timedelta(days=1), owner_id=1, organization_id=1)
    calendar.create_calendar_item("Future", "book", now + timedelta(days=20), owner_id=1, organization_id=1)

    calendar.schedule_publication(first.id, "pdf", now + timedelta(days=1), created_by=1, book_id=10)

    items = calendar.list_calendar_items(
        organization_id=1,
        start=now,
        end=now + timedelta(days=2),
        status="scheduled",
    )

    assert [item.title for item in items] == ["Draft"]


def test_schedule_and_query_due_publications(managers):
    """Scheduled publication jobs should become due at their scheduled time."""
    _conn, _audit, _notifications, calendar = managers
    now = datetime.now()
    item = calendar.create_calendar_item("Launch", "book", now + timedelta(days=3), owner_id=1)
    publication = calendar.schedule_publication(
        calendar_item_id=item.id,
        channel="epub",
        scheduled_for=now + timedelta(hours=2),
        created_by=1,
        book_id=12,
    )

    assert publication.status == "scheduled"
    assert calendar.get_due_publications(now=now) == []

    due = calendar.get_due_publications(now=now + timedelta(hours=3))
    assert [job.id for job in due] == [publication.id]
    assert due[0].channel == "epub"


def test_mark_published_updates_calendar_when_all_channels_done(managers):
    """Calendar item should publish once all scheduled channel jobs publish."""
    _conn, audit, _notifications, calendar = managers
    now = datetime.now()
    item = calendar.create_calendar_item("Multi-channel", "book", now + timedelta(days=1), owner_id=1)
    pdf = calendar.schedule_publication(item.id, "pdf", now, created_by=1)
    epub = calendar.schedule_publication(item.id, "epub", now, created_by=1)

    assert calendar.mark_published(pdf.id, published_at=now) is True
    assert calendar.get_calendar_item(item.id).status == "scheduled"

    assert calendar.mark_published(epub.id, published_at=now) is True
    assert calendar.get_calendar_item(item.id).status == "published"
    assert calendar.get_scheduled_publication(epub.id).published_at == now

    events = audit.query_events(resource_type="scheduled_publication")
    assert events[0].action == "publication.publish"


def test_failed_and_cancelled_publications(managers):
    """Publication jobs should support failure and cancellation states."""
    _conn, audit, _notifications, calendar = managers
    now = datetime.now()
    failed_item = calendar.create_calendar_item("Failed", "book", now, owner_id=1)
    failed = calendar.schedule_publication(failed_item.id, "web", now, created_by=1)
    cancelled_item = calendar.create_calendar_item("Cancelled", "book", now, owner_id=1)
    cancelled = calendar.schedule_publication(cancelled_item.id, "pdf", now, created_by=1)

    assert calendar.mark_failed(failed.id, "Export error") is True
    assert calendar.get_scheduled_publication(failed.id).status == "failed"
    assert calendar.get_scheduled_publication(failed.id).failure_reason == "Export error"

    assert calendar.cancel_publication(cancelled.id, cancelled_by=1) is True
    assert calendar.get_scheduled_publication(cancelled.id).status == "cancelled"

    warning_events = audit.query_events(severity="warning")
    assert warning_events[0].action == "publication.fail"
