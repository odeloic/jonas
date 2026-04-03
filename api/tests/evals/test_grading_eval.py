"""Grading quality eval — validates semantic judge against golden dataset.

Acceptance bar:
  False positive rate = 0%   (hard assert — clearly_wrong cases must never pass)
  False negative rate ≤ 15%  (soft warn — semantic_correct cases that fail)

Run with:
  pytest tests/evals/test_grading_eval.py -v -s
"""

import json
import warnings
from collections import defaultdict
from datetime import date
from pathlib import Path

from tests.evals.judges.grading_judge import JudgeResult, judge_answer

FN_RATE_THRESHOLD = 0.15
DATASET_PATH = Path(__file__).parent / "datasets" / "grading_cases.json"


async def test_grading_eval(llm_service, langfuse_client):
    cases = json.loads(DATASET_PATH.read_text())
    assert len(cases) >= 30, f"Expected 30+ cases in golden dataset, got {len(cases)}"

    # 1. Run all judge calls
    results: list[tuple[dict, JudgeResult | None]] = []
    for case in cases:
        try:
            result = await judge_answer(
                student_answer=case["test_answer"],
                correct_answer=case["correct_answer"],
                question=case["question"],
                llm=llm_service,
            )
        except Exception as exc:  # noqa: BLE001
            result = None
            print(f"  [JUDGE_ERROR] {case['id']}: {exc}")
        results.append((case, result))

    # 2. Log to Langfuse dataset
    if langfuse_client is not None:
        dataset_name = f"grading-eval-{date.today().isoformat()}"
        try:
            langfuse_client.create_dataset(name=dataset_name)
        except Exception:  # noqa: BLE001
            pass  # dataset may already exist for today
        for case, result in results:
            langfuse_client.create_dataset_item(
                dataset_name=dataset_name,
                input={
                    "question": case["question"],
                    "correct_answer": case["correct_answer"],
                    "test_answer": case["test_answer"],
                },
                expected_output={"expected_correct": case["expected_correct"]},
                metadata={
                    "judge_is_correct": result.is_correct if result else None,
                    "judge_score": result.score if result else None,
                    "rationale": result.rationale if result else "JUDGE_ERROR",
                    "bucket": case["bucket"],
                    "exercise_type": case["exercise_type"],
                    "grammar_rule": case.get("grammar_rule", ""),
                    "note": case.get("note", ""),
                },
            )
        langfuse_client.flush()

    # 3. Aggregate metrics
    by_bucket: dict[str, list] = defaultdict(list)
    by_type: dict[str, list] = defaultdict(list)
    for case, result in results:
        by_bucket[case["bucket"]].append((case, result))
        by_type[case["exercise_type"]].append((case, result))

    def matched(case: dict, result: JudgeResult | None) -> bool:
        return result is not None and result.is_correct == case["expected_correct"]

    cw_cases = by_bucket["clearly_wrong"]
    fp_cases = [(c, r) for c, r in cw_cases if r is not None and r.is_correct]
    fp_rate = len(fp_cases) / len(cw_cases) if cw_cases else 0.0

    sc_cases = by_bucket["semantic_correct"]
    fn_cases = [(c, r) for c, r in sc_cases if r is None or not r.is_correct]
    fn_rate = len(fn_cases) / len(sc_cases) if sc_cases else 0.0

    # 4. Print breakdown
    print("\n=== Grading Eval Results ===")
    print("\nBy bucket:")
    for bucket in ("exactly_correct", "semantic_correct", "clearly_wrong"):
        items = by_bucket[bucket]
        ok = sum(1 for c, r in items if matched(c, r))
        fails = [c["id"] for c, r in items if not matched(c, r)]
        print(f"  {bucket:<22} {ok}/{len(items)}  failures: {fails or 'none'}")

    print("\nBy exercise type:")
    exercise_types = (
        "REORDER",
        "COMPLETION",
        "ADJEKTIV_DEKLINATION",
        "FILL_IN_THE_BLANK",
        "MULTIPLE_CHOICE",
    )
    for etype in exercise_types:
        items = by_type[etype]
        ok = sum(1 for c, r in items if matched(c, r))
        print(f"  {etype:<26} {ok}/{len(items)}")

    print(f"\nFalse positive rate:  {fp_rate:.1%}  (threshold: 0%)")
    print(f"False negative rate:  {fn_rate:.1%}  (threshold: {FN_RATE_THRESHOLD:.0%})")
    if langfuse_client:
        print(f"Logged to Langfuse dataset: grading-eval-{date.today().isoformat()}")

    # 5. Assertions
    assert fp_rate == 0.0, (
        f"False positive rate {fp_rate:.1%} — "
        f"clearly_wrong cases graded correct: {[c['id'] for c, _ in fp_cases]}"
    )

    if fn_rate > FN_RATE_THRESHOLD:
        warnings.warn(
            f"False negative rate {fn_rate:.1%} exceeds {FN_RATE_THRESHOLD:.0%} threshold — "
            f"semantic_correct cases wrongly failed: {[c['id'] for c, _ in fn_cases]}",
            stacklevel=2,
        )
