"""
Unit tests for email_processing/orchestrator.py helper functions, using mocks.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from email_processing import orchestrator as orch


@pytest.mark.skip(reason="presence feature removed")
@pytest.mark.unit
def test_handle_presence_route_valid_day_time_and_url(monkeypatch):
    logger = MagicMock()
    # Force Thursday (weekday=3)
    class FakeDT:
        @classmethod
        def now(cls, tz):
            return datetime(2025, 10, 9, 10, 0, tzinfo=tz)  # Thursday
    monkeypatch.setattr(orch, 'datetime', FakeDT)

    sent_calls = {}
    def fake_send_makecom_webhook(**kwargs):
        sent_calls['called'] = True
        return True

    routed = orch.handle_presence_route(
        subject="Samedi - test",
        full_email_content="... samedi ...",
        email_id="e1",
        sender_raw="from@example.com",
        tz_for_polling=timezone.utc,
        webhooks_time_start_str="09:00",
        webhooks_time_end_str="17:00",
        presence_flag=True,
        presence_true_url="https://hook.eu2.make.com/abc",
        presence_false_url=None,
        is_within_time_window_local=lambda now: True,
        extract_sender_email=lambda s: "from@example.com",
        send_makecom_webhook=fake_send_makecom_webhook,
        logger=logger,
    )
    assert routed is True
    assert sent_calls.get('called') is True


@pytest.mark.unit
def test_handle_desabo_route_matches_and_sends(monkeypatch):
    logger = MagicMock()
    # Force window OK via dependency
    def fake_check_desabo_conditions(subject, text, logger):
        return {"matches": True, "has_dropbox_request": True}
    def fake_build_payload(**kwargs):
        return {"detector": "desabonnement_journee_tarifs"}
    sent = {}
    def fake_send(**kwargs):
        sent['ok'] = True
        return True
    marked = {}
    def fake_mark(group_id):
        marked['gid'] = group_id

    routed = orch.handle_desabo_route(
        subject="Je veux me désabonner",
        full_email_content="se desabonner journée tarifs habituels",
        html_email_content="",
        email_id="e2",
        sender_raw="from@example.com",
        tz_for_polling=timezone.utc,
        webhooks_time_start=None,
        webhooks_time_start_str="09:00",
        webhooks_time_end_str="17:00",
        processing_prefs={},
        extract_sender_email=lambda s: "from@example.com",
        check_desabo_conditions=fake_check_desabo_conditions,
        build_desabo_make_payload=fake_build_payload,
        send_makecom_webhook=fake_send,
        override_webhook_url="https://hook.eu2.make.com/xyz",
        mark_subject_group_processed=fake_mark,
        subject_group_id="sg1",
        is_within_time_window_local=lambda now: True,
        logger=logger,
    )
    assert routed is True
    assert sent.get('ok') is True
    assert marked.get('gid') == "sg1"


@pytest.mark.unit
def test_handle_media_solution_route_excluded_by_keywords():
    logger = MagicMock()
    # Exclude by keyword present in subject
    processing_prefs = {"exclude_keywords_recadrage": ["forbidden"]}
    routed = orch.handle_media_solution_route(
        subject="forbidden",
        full_email_content="body",
        email_id="e3",
        processing_prefs=processing_prefs,
        tz_for_polling=timezone.utc,
        check_media_solution_pattern=lambda s,b,tz,l: {"matches": True, "delivery_time": "09h00"},
        extract_sender_email=lambda s: "from@example.com",
        sender_raw="from@example.com",
        send_makecom_webhook=lambda **kwargs: True,
        mark_subject_group_processed=lambda gid: None,
        subject_group_id=None,
        logger=logger,
    )
    assert routed is False  # excluded


@pytest.mark.unit
def test_handle_media_solution_route_sends_and_marks():
    logger = MagicMock()
    marked = {}
    def fake_mark(gid):
        marked['gid'] = gid
    def fake_send(**kwargs):
        return True

    ok = orch.handle_media_solution_route(
        subject="Média Solution - Missions Recadrage - Lot 5",
        full_email_content="Lien: https://www.dropbox.com/scl/fo/abc",
        email_id="e4",
        processing_prefs={},
        tz_for_polling=timezone.utc,
        check_media_solution_pattern=lambda s,b,tz,l: {"matches": True, "delivery_time": "10h00"},
        extract_sender_email=lambda s: "from@example.com",
        sender_raw="from@example.com",
        send_makecom_webhook=fake_send,
        mark_subject_group_processed=fake_mark,
        subject_group_id="sg2",
        logger=logger,
    )
    assert ok is True
    assert marked.get('gid') == "sg2"
