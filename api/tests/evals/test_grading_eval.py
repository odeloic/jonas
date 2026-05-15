"""Grading quality eval — validates the per-blank judge against a golden dataset.

Each case has 1+ blanks; we call `judge_blank` once per blank and AND the verdicts.

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

from models.assignment_schema import Blank
from services.grading_judge import JudgeResult, judge_blank

FN_RATE_THRESHOLD = 0.15
DATASET_PATH = Path(__file__).parent / "datasets" / "grading_cases.json"


async def _judge_case(case: dict, llm_service) -> list[JudgeResult | None]:
    """Call judge_blank once per blank. Returns per-blank results (None on error)."""
    results: list[JudgeResult | None] = []
    blanks_data = case["blanks"]
    student_answers = case["student_answers"]
    # Pad if student has fewer answers than blanks (mirrors scoring._score_criterion).
    padded = list(student_answers) + [""] * (len(blanks_data) - len(student_answers))
    for blank_data, student_answer in zip(blanks_data, padded[: len(blanks_data)], strict=True):
        blank = Blank(**blank_data)
        try:
            r = await judge_blank(
                question=case["question"],
                blank=blank,
                student_answer=student_answer,
                llm=llm_service,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  [JUDGE_ERROR] {case['id']} blank {blank.index}: {exc}")
            r = None
        results.append(r)
    return results


def _aggregate_verdict(blank_results: list[JudgeResult | None]) -> bool | None:
    """AND across blanks. None if any blank errored."""
    if any(r is None for r in blank_results):
        return None
    return all(r.is_correct for r in blank_results)  # type: ignore[union-attr]


async def test_grading_eval(llm_service, langfuse_client):
    cases = json.loads(DATASET_PATH.read_text())
    assert len(cases) >= 30, f"Expected 30+ cases in golden dataset, got {len(cases)}"

    results: list[tuple[dict, list[JudgeResult | None], bool | None]] = []
    for case in cases:
        blank_results = await _judge_case(case, llm_service)
        results.append((case, blank_results, _aggregate_verdict(blank_results)))

    if langfuse_client is not None:
        dataset_name = f"grading-eval-{date.today().isoformat()}"
        try:
            langfuse_client.create_dataset(name=dataset_name)
        except Exception:  # noqa: BLE001
            pass
        for case, blank_results, item_verdict in results:
            langfuse_client.create_dataset_item(
                dataset_name=dataset_name,
                input={
                    "question": case["question"],
                    "blanks": case["blanks"],
                    "student_answers": case["student_answers"],
                },
                expected_output={"expected_correct": case["expected_correct"]},
                metadata={
                    "judge_is_correct": item_verdict,
                    "blank_rationales": [
                        r.rationale if r else "JUDGE_ERROR" for r in blank_results
                    ],
                    "bucket": case["bucket"],
                    "exercise_type": case["exercise_type"],
                    "grammar_rule": case.get("grammar_rule", ""),
                    "note": case.get("note", ""),
                },
            )
        langfuse_client.flush()

    by_bucket: dict[str, list] = defaultdict(list)
    by_type: dict[str, list] = defaultdict(list)
    for case, _br, verdict in results:
        by_bucket[case["bucket"]].append((case, verdict))
        by_type[case["exercise_type"]].append((case, verdict))

    def matched(case: dict, verdict: bool | None) -> bool:
        return verdict is not None and verdict == case["expected_correct"]

    cw_cases = by_bucket["clearly_wrong"]
    fp_cases = [(c, v) for c, v in cw_cases if v is True]
    fp_rate = len(fp_cases) / len(cw_cases) if cw_cases else 0.0

    sc_cases = by_bucket["semantic_correct"]
    fn_cases = [(c, v) for c, v in sc_cases if v is None or v is False]
    fn_rate = len(fn_cases) / len(sc_cases) if sc_cases else 0.0

    print("\n=== Grading Eval Results ===")
    print("\nBy bucket:")
    for bucket in ("exactly_correct", "semantic_correct", "clearly_wrong"):
        items = by_bucket[bucket]
        ok = sum(1 for c, v in items if matched(c, v))
        fails = [c["id"] for c, v in items if not matched(c, v)]
        print(f"  {bucket:<22} {ok}/{len(items)}  failures: {fails or 'none'}")

    print("\nBy exercise type:")
    for etype in ("COMPLETION", "FILL_IN_THE_BLANK"):
        items = by_type[etype]
        ok = sum(1 for c, v in items if matched(c, v))
        print(f"  {etype:<26} {ok}/{len(items)}")

    print(f"\nFalse positive rate:  {fp_rate:.1%}  (threshold: 0%)")
    print(f"False negative rate:  {fn_rate:.1%}  (threshold: {FN_RATE_THRESHOLD:.0%})")
    if langfuse_client:
        print(f"Logged to Langfuse dataset: grading-eval-{date.today().isoformat()}")

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
