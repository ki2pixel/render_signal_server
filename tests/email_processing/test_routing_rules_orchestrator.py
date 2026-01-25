from __future__ import annotations

import re

import sys
import types

from email_processing import orchestrator as orch


class _DummyLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, msg, *args) -> None:  # noqa: D401 - simple helper
        if args:
            self.messages.append(msg % args)
        else:
            self.messages.append(msg)

    def debug(self, *args, **kwargs) -> None:
        return None

    def warning(self, msg, *args) -> None:
        self.info(msg, *args)

    def error(self, msg, *args) -> None:
        self.info(msg, *args)


def _rule(actions: dict | None = None) -> dict:
    return {
        "id": "rule-a",
        "name": "Factures",
        "conditions": [
            {"field": "subject", "operator": "contains", "value": "Facture"},
            {"field": "sender", "operator": "equals", "value": "billing@client.com"},
        ],
        "actions": actions or {"webhook_url": "https://hook.eu2.make.com/bill", "priority": "high"},
    }


def test_match_condition_respects_case_insensitive_contains():
    subject = "FACTURE Mensuelle"
    cond = {"field": "subject", "operator": "contains", "value": "facture", "case_sensitive": False}
    assert orch._match_routing_condition(cond, sender="", subject=subject, body="") is True


def test_match_condition_regex_case_sensitive():
    cond = {"field": "body", "operator": "regex", "value": r"^URGENT", "case_sensitive": True}
    assert orch._match_routing_condition(cond, sender="", subject="", body="URGENT demande") is True
    assert orch._match_routing_condition(cond, sender="", subject="", body="urgent demande") is False


def test_find_matching_routing_rule_returns_first_match():
    rules = [_rule(), _rule({"webhook_url": "https://hook.eu2.make.com/support"})]
    logger = _DummyLogger()

    matched = orch._find_matching_routing_rule(
        rules,
        sender="billing@client.com",
        subject="Facture Janvier",
        body="",
        email_id="123",
        logger=logger,
    )

    assert matched["id"] == "rule-a"
    assert any("Factures" in msg for msg in logger.messages)


def test_find_matching_routing_rule_none_when_no_condition_met():
    rules = [_rule()]
    logger = _DummyLogger()

    matched = orch._find_matching_routing_rule(
        rules,
        sender="ops@client.com",
        subject="Notification",
        body="",
        email_id="456",
        logger=logger,
    )

    assert matched is None
    assert logger.messages == []


def _install_app_render_stub(monkeypatch, mail_instance, *, default_webhook="https://hook.eu2.make.com/default"):
    module = types.ModuleType("app_render")
    logger = _DummyLogger()
    module.app = types.SimpleNamespace(logger=logger)
    module.SENDER_LIST_FOR_POLLING = []
    module.WEBHOOK_URL = default_webhook
    module.ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS = True
    module.PROCESSING_PREFS = {}
    module._rate_limit_allow_send = lambda: True
    module._record_send_event = lambda: None
    module._append_webhook_log = lambda entry: None
    module.create_imap_connection = lambda: mail_instance
    module.close_imap_connection = lambda _mail: None
    module.decode_email_header = lambda value: value
    module.extract_sender_email = lambda raw: raw.split('<')[-1].split('>')[0] if '<' in raw else raw
    module.mark_email_id_as_processed_redis = lambda _email_id: True
    module.is_email_id_processed_redis = lambda _email_id: False
    module.mark_email_as_read_imap = lambda _mail, _num: None
    module.generate_subject_group_id = lambda subj: f"grp-{subj}"
    module.is_subject_group_processed = lambda _grp: False
    module._legacy_check_new_emails_and_trigger_webhook = None
    monkeypatch.setitem(sys.modules, "app_render", module)
    return logger


def _install_pattern_matching_stub(monkeypatch):
    module = types.ModuleType("email_processing.pattern_matching")
    module.check_media_solution_pattern = lambda *args, **kwargs: {"matches": False}
    module.check_desabo_conditions = lambda *args, **kwargs: {"matches": False}
    monkeypatch.setitem(sys.modules, "email_processing.pattern_matching", module)


def _install_link_extraction_stub(monkeypatch):
    module = types.ModuleType("email_processing.link_extraction")
    module.extract_provider_links_from_text = lambda *_: []
    monkeypatch.setitem(sys.modules, "email_processing.link_extraction", module)


def _install_imap_client_stub(monkeypatch):
    module = types.ModuleType("email_processing.imap_client")
    module.generate_email_id = lambda *_: "email-1"
    monkeypatch.setitem(sys.modules, "email_processing.imap_client", module)


def test_orchestrator_routes_to_custom_webhook_when_rule_matches(monkeypatch):
    rules_payload = {"rules": [_rule()], "_updated_at": "ts"}
    monkeypatch.setattr(orch, "_get_routing_rules_payload", lambda: rules_payload)
    monkeypatch.setattr(orch, "_load_webhook_global_time_window", lambda: (None, None))
    monkeypatch.setattr(orch, "_get_webhook_config_dict", lambda: {})
    monkeypatch.setattr(orch, "_is_webhook_sending_enabled", lambda: True)
    _install_pattern_matching_stub(monkeypatch)
    _install_link_extraction_stub(monkeypatch)
    _install_imap_client_stub(monkeypatch)

    sent_calls = []

    def _fake_send(**kwargs):
        sent_calls.append(kwargs)
        return False

    monkeypatch.setattr(orch, "send_custom_webhook_flow", _fake_send)

    class _DummyMail:
        def select(self, *_):
            return ("OK", None)

        def search(self, *_):
            return ("OK", [b"1"])

        def fetch(self, *_):
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["Subject"] = "Facture Janvier"
            msg["From"] = "Billing <billing@client.com>"
            msg.set_content("Bonjour")
            return ("OK", [(None, msg.as_bytes())])

    _install_app_render_stub(monkeypatch, _DummyMail())

    result = orch.check_new_emails_and_trigger_webhook()

    assert result == 2
    assert sent_calls[0]["webhook_url"] == "https://hook.eu2.make.com/bill"


def test_orchestrator_stop_processing_skips_default(monkeypatch):
    rules_payload = {
        "rules": [_rule({"webhook_url": "https://hook.eu2.make.com/stop", "stop_processing": True})],
        "_updated_at": "ts",
    }
    monkeypatch.setattr(orch, "_get_routing_rules_payload", lambda: rules_payload)
    monkeypatch.setattr(orch, "_load_webhook_global_time_window", lambda: (None, None))
    monkeypatch.setattr(orch, "_get_webhook_config_dict", lambda: {})
    monkeypatch.setattr(orch, "_is_webhook_sending_enabled", lambda: True)
    _install_pattern_matching_stub(monkeypatch)
    _install_link_extraction_stub(monkeypatch)
    _install_imap_client_stub(monkeypatch)

    default_calls = []

    def _fake_send(**kwargs):
        if kwargs["webhook_url"] == "https://hook.eu2.make.com/default":
            default_calls.append(kwargs)
        return False

    monkeypatch.setattr(orch, "send_custom_webhook_flow", _fake_send)

    class _DummyMail:
        def select(self, *_):
            return ("OK", None)

        def search(self, *_):
            return ("OK", [b"1"])

        def fetch(self, *_):
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["Subject"] = "Facture"
            msg["From"] = "billing@client.com"
            msg.set_content("Corps")
            return ("OK", [(None, msg.as_bytes())])

    _install_app_render_stub(monkeypatch, _DummyMail())

    orch.check_new_emails_and_trigger_webhook()

    assert default_calls == []
