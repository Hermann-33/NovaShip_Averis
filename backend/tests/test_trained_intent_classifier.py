from datetime import datetime, timezone

from app.ai import intent_classifier
from app.ai.trained_intent_classifier import TrainedIntentPrediction
from app.contracts.schemas import EmailMessage, HackathonCategory, SecurityAssessment, SecurityOutcome


def _email(subject: str, body: str) -> EmailMessage:
    return EmailMessage(
        id="intent-test", sender="person@example.com", subject=subject, body=body,
        received_at=datetime.now(timezone.utc),
    )


SAFE = SecurityAssessment(outcome=SecurityOutcome.SAFE, score=0.0)


def test_trained_model_handles_email_when_rules_are_weak(monkeypatch):
    monkeypatch.setattr(
        intent_classifier,
        "predict_trained_intent",
        lambda *_: TrainedIntentPrediction(HackathonCategory.INVOICE_QUERY, 0.92, "test-v1"),
    )
    result = intent_classifier.classify_intent(
        _email("Question about an amount", "Can you explain this charge?"), SAFE, False,
    )
    assert result.hackathon_category == HackathonCategory.INVOICE_QUERY
    assert result.decided_by == "model"
    assert "test-v1" in result.rationale


def test_model_cannot_overrule_a_stronger_rule_without_margin(monkeypatch):
    monkeypatch.setattr(
        intent_classifier,
        "predict_trained_intent",
        lambda *_: TrainedIntentPrediction(HackathonCategory.GENERAL, 0.90, "test-v1"),
    )
    result = intent_classifier.classify_intent(
        _email("BILLING 5070146000 MISSING GR", "The invoice GR is still missing."), SAFE, False,
    )
    assert result.hackathon_category == HackathonCategory.INVOICE_QUERY
    assert result.decided_by == "rule"


def test_missing_model_keeps_rule_behavior(monkeypatch):
    monkeypatch.setattr(intent_classifier, "predict_trained_intent", lambda *_: None)
    result = intent_classifier.classify_intent(
        _email("REQUEST SI _ 5RSG-1", "Please find shipping instruction for this booking."), SAFE, False,
    )
    assert result.hackathon_category == HackathonCategory.SI_REQUEST
    assert result.decided_by == "rule"
