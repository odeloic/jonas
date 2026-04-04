"""Intent classification eval — validates LLM classifier against golden dataset.

Acceptance bar:
  Accuracy ≥ 95%  (hard assert — some edge cases are genuinely ambiguous)

Run with:
  pytest tests/evals/test_intent_eval.py -v -s
"""

import json
from collections import defaultdict
from pathlib import Path

import pytest

from services.intent import classify_intent

ACCURACY_THRESHOLD = 0.95
DATASET_PATH = Path(__file__).parent / "datasets" / "intent_cases.json"


@pytest.fixture(scope="module")
def intent_cases():
    cases = json.loads(DATASET_PATH.read_text())
    assert len(cases) >= 30, f"Expected 30+ cases, got {len(cases)}"
    return cases


@pytest.mark.asyncio
async def test_intent_classification_accuracy(intent_cases):
    results: list[tuple[dict, str | None]] = []

    for case in intent_cases:
        try:
            result = await classify_intent(case["input"])
            predicted = result.intent.value
        except Exception as exc:  # noqa: BLE001
            predicted = None
            print(f"  [ERROR] {case['id']}: {exc}")
        results.append((case, predicted))

    # Aggregate by expected intent
    by_intent: dict[str, list] = defaultdict(list)
    for case, predicted in results:
        by_intent[case["expected_intent"]].append((case, predicted))

    # Print breakdown
    print("\n=== Intent Classification Eval ===\n")
    total_correct = 0
    total = len(results)

    for intent in ("PRACTICE", "QUESTION", "IGNORE"):
        items = by_intent[intent]
        correct = sum(1 for c, p in items if p == c["expected_intent"])
        total_correct += correct
        failures = [f"{c['id']}(got:{p})" for c, p in items if p != c["expected_intent"]]
        print(f"  {intent:<12} {correct}/{len(items)}  failures: {failures or 'none'}")

    accuracy = total_correct / total if total else 0.0
    print(f"\nOverall accuracy: {accuracy:.1%}  (threshold: {ACCURACY_THRESHOLD:.0%})")

    assert accuracy >= ACCURACY_THRESHOLD, (
        f"Accuracy {accuracy:.1%} below {ACCURACY_THRESHOLD:.0%} threshold"
    )
