#!/usr/bin/env python3
"""Train and evaluate the NovaShip email intent classifier.

The script creates a deterministic, template-group-aware 70/30 split, trains
only on the development partition, evaluates the untouched partition, and
writes the fitted artifact plus split/metrics manifests.

Run from ``backend`` after installing requirements::

    python scripts/train_intent_classifier.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("LLM_PROVIDER", "none")

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import sklearn  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score  # noqa: E402
from sklearn.model_selection import GroupShuffleSplit, train_test_split  # noqa: E402
from sklearn.pipeline import FeatureUnion, Pipeline  # noqa: E402

from app.ai.trained_intent_classifier import model_input, reset_model_cache  # noqa: E402
from app.contracts.schemas import EmailMessage  # noqa: E402

CATEGORIES = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"]


def template_signature(subject: str) -> str:
    """Coarse generator/template family used to keep lookalikes in one split."""
    s = subject.upper().removeprefix("RE_ ").strip()
    families = [
        (r"TO CONFIRM DOCS", "bl:confirm"),
        (r"REQUEST BL DRAFT", "bl:request"),
        (r"DRAFT BL .*AMEND BL", "bl:amend"),
        (r"^(AIE|AFPTME|AFRT|AFEMY)\s*-", "bl:coded"),
        (r"^SI\s*-", "si:coded"),
        (r"CUST SI", "si:customer"),
        (r"REQUEST SI", "si:request"),
        (r"SI NEEDED|LATEST SI", "si:needed"),
        (r"BILLING.*MISSING GR", "invoice:missing-gr"),
        (r"CANCEL INVOICE", "invoice:cancel"),
        (r"LOCAL CHARGES", "invoice:local-charges"),
        (r"D\s*&\s*D CHARGES", "invoice:detention"),
        (r"TOTAL FREIGHT", "invoice:freight"),
        (r"UPDATE SUMMARY", "general:update"),
        (r"BERTHING REPORT", "general:berthing"),
        (r"_REMINDER_", "general:reminder"),
        (r"_RPA_", "general:rpa"),
        (r"OUTSTANDING BL", "general:outstanding"),
        (r"PENDING BL RELEASE", "general:pending"),
    ]
    for pattern, family in families:
        if re.search(pattern, s):
            return family
    # Exact spam/general subjects form natural template groups after volatile
    # numbers are removed. This prevents duplicate phrases crossing the split.
    normalized = re.sub(r"\b\d[\d_.,/-]*\b", "<N>", s)
    normalized = re.sub(r"\s+", " ", normalized)
    return "other:" + normalized[:100]


def stratum(truth: dict[str, Any]) -> str:
    review = truth.get("review_reason") or "none"
    return f"{truth['category']}|{truth.get('status', 'OK')}|{review}"


def load_samples(data_dir: Path) -> list[dict[str, Any]]:
    truth = json.loads((data_dir / "ground_truth.json").read_text(encoding="utf-8"))
    samples: list[dict[str, Any]] = []
    for email_id, label in sorted(truth.items()):
        path = data_dir / "inbox" / f"{email_id}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        has_attachments = bool(raw.get("attachments"))
        samples.append({
            "id": email_id,
            "sender": raw.get("from", ""),
            "subject": raw.get("subject", ""),
            "body": raw.get("body", ""),
            "has_attachments": has_attachments,
            "text": model_input(raw.get("subject", ""), raw.get("body", ""), has_attachments),
            "label": label["category"],
            "stratum": stratum(label),
            "group": template_signature(raw.get("subject", "")),
        })
    return samples


def _distribution_error(samples: list[dict[str, Any]], test_idx: np.ndarray, test_size: float) -> float:
    total = Counter(s["stratum"] for s in samples)
    selected = Counter(samples[int(i)]["stratum"] for i in test_idx)
    size_error = abs(len(test_idx) / len(samples) - test_size) * 4
    dist_error = sum(abs(selected[k] / len(test_idx) - total[k] / len(samples)) for k in total)
    return size_error + dist_error


def split_samples(samples: list[dict[str, Any]], test_size: float, seed: int) -> tuple[list[int], list[int], str]:
    indices = np.arange(len(samples))
    groups = np.array([s["group"] for s in samples])
    all_strata = set(s["stratum"] for s in samples)
    splitter = GroupShuffleSplit(n_splits=1000, test_size=test_size, random_state=seed)
    candidates: list[tuple[float, np.ndarray, np.ndarray]] = []
    for train_idx, test_idx in splitter.split(indices, groups=groups):
        test_fraction = len(test_idx) / len(samples)
        if not 0.25 <= test_fraction <= test_size:
            continue
        train_strata = {samples[int(i)]["stratum"] for i in train_idx}
        test_strata = {samples[int(i)]["stratum"] for i in test_idx}
        train_labels = {samples[int(i)]["label"] for i in train_idx}
        test_labels = {samples[int(i)]["label"] for i in test_idx}
        if train_strata == all_strata and test_strata == all_strata and train_labels == set(CATEGORIES) and test_labels == set(CATEGORIES):
            candidates.append((_distribution_error(samples, test_idx, test_size), train_idx, test_idx))
    if candidates:
        _, train_idx, test_idx = min(candidates, key=lambda item: item[0])
        return sorted(map(int, train_idx)), sorted(map(int, test_idx)), "template_grouped"

    # Very small/custom datasets may not have enough independent template
    # groups. Preserve label/review balance rather than failing training.
    strata = [s["stratum"] for s in samples]
    train_idx, test_idx = train_test_split(indices, test_size=test_size, random_state=seed, stratify=strata)
    return sorted(map(int, train_idx)), sorted(map(int, test_idx)), "stratified_fallback"


def build_pipeline(seed: int) -> Pipeline:
    features = FeatureUnion([
        ("word", TfidfVectorizer(
            ngram_range=(1, 2), min_df=2, max_features=25_000,
            sublinear_tf=True, strip_accents="unicode",
        )),
        ("char", TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=2,
            max_features=20_000, sublinear_tf=True,
        )),
    ])
    classifier = LogisticRegression(
        max_iter=2_000, class_weight="balanced", C=2.0,
        random_state=seed,
    )
    return Pipeline([("features", features), ("classifier", classifier)])


def metric_block(actual: list[str], predicted: list[str]) -> dict[str, Any]:
    return {
        "accuracy": round(float(accuracy_score(actual, predicted)), 6),
        "macro_f1": round(float(f1_score(actual, predicted, labels=CATEGORIES, average="macro", zero_division=0)), 6),
        "classification_report": classification_report(
            actual, predicted, labels=CATEGORIES, output_dict=True, zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(actual, predicted, labels=CATEGORIES).tolist(),
        "confusion_labels": CATEGORIES,
    }


def runtime_predictions(samples: list[dict[str, Any]], enabled: bool, model_path: Path) -> list[str]:
    from app.ai.intent_classifier import classify_intent
    from app.ai.security_precheck import assess_security

    os.environ["INTENT_MODEL_ENABLED"] = "1" if enabled else "0"
    os.environ["INTENT_MODEL_PATH"] = str(model_path)
    reset_model_cache()
    predictions: list[str] = []
    for sample in samples:
        email = EmailMessage(
            id=sample["id"], sender=sample["sender"], subject=sample["subject"], body=sample["body"],
            received_at=datetime.now(timezone.utc),
        )
        security = assess_security(email, [])
        result = classify_intent(email, security, sample["has_attachments"])
        predictions.append(result.hackathon_category.value)
    return predictions


def counts(samples: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(s["label"] for s in samples).items()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "sdoc-hackathon-docker" / "data_v2")
    parser.add_argument("--model-out", type=Path, default=BACKEND / "models" / "intent_classifier.joblib")
    parser.add_argument("--metrics-out", type=Path, default=BACKEND / "models" / "intent_metrics.json")
    parser.add_argument("--split-out", type=Path, default=BACKEND / "models" / "intent_split.json")
    parser.add_argument("--test-size", type=float, default=0.30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 0.25 <= args.test_size <= 0.30:
        parser.error("--test-size must be between 0.25 and 0.30")

    samples = load_samples(args.data.resolve())
    train_idx, test_idx, split_method = split_samples(samples, args.test_size, args.seed)
    train = [samples[i] for i in train_idx]
    test = [samples[i] for i in test_idx]
    pipeline = build_pipeline(args.seed)
    pipeline.fit([s["text"] for s in train], [s["label"] for s in train])

    fingerprint = hashlib.sha256("\n".join(s["id"] for s in train).encode()).hexdigest()[:12]
    model_version = f"tfidf-logreg-v1-{fingerprint}"
    artifact = {
        "pipeline": pipeline,
        "model_version": model_version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_count": len(train),
        "categories": CATEGORIES,
        "library_versions": {
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
            "numpy": np.__version__,
        },
        "seed": args.seed,
        "split_method": split_method,
    }
    args.model_out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, args.model_out)

    actual = [s["label"] for s in test]
    model_pred = list(pipeline.predict([s["text"] for s in test]))
    rule_pred = runtime_predictions(test, enabled=False, model_path=args.model_out.resolve())
    hybrid_pred = runtime_predictions(test, enabled=True, model_path=args.model_out.resolve())
    metrics = {
        "model_version": model_version,
        "split_method": split_method,
        "seed": args.seed,
        "train_count": len(train),
        "test_count": len(test),
        "test_fraction": round(len(test) / len(samples), 6),
        "train_distribution": counts(train),
        "test_distribution": counts(test),
        "rule_baseline": metric_block(actual, rule_pred),
        "trained_model": metric_block(actual, model_pred),
        "hybrid": metric_block(actual, hybrid_pred),
    }
    split_manifest = {
        "seed": args.seed,
        "test_size_requested": args.test_size,
        "test_fraction_actual": round(len(test) / len(samples), 6),
        "split_method": split_method,
        "train_ids": [s["id"] for s in train],
        "test_ids": [s["id"] for s in test],
        "train_template_groups": sorted({s["group"] for s in train}),
        "test_template_groups": sorted({s["group"] for s in test}),
    }
    args.metrics_out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    args.split_out.write_text(json.dumps(split_manifest, indent=2), encoding="utf-8")

    print(f"split={split_method} train={len(train)} test={len(test)}")
    for name in ("rule_baseline", "trained_model", "hybrid"):
        result = metrics[name]
        print(f"{name:16s} accuracy={result['accuracy']:.3f} macro_f1={result['macro_f1']:.3f}")
    print(f"model   -> {args.model_out}")
    print(f"metrics -> {args.metrics_out}")
    print(f"split   -> {args.split_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
