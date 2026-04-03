# Grading Feedback Dataset Workflow

## How `grading-feedback` grows

When a student reacts with 👎 on a Jonas grading message in Telegram:

1. The bot flags the submission in Postgres (`flagged_for_review = true`, `flagged_at = now()`).
2. If the submission has a `langfuse_trace_id` (i.e. semantic grading was involved), the trace is queued into the **`grading-feedback`** dataset in Langfuse.
3. The bot replies "Notiert. Ich lerne daraus."

## Labelling an item in Langfuse

1. Open the Langfuse UI and navigate to **Datasets → grading-feedback**.
2. Find the item you want to label.
3. Set `expected_output` → `{"expected_correct": true}` or `{"expected_correct": false}` based on whether the student's answer should have been marked correct.
4. Save.

## Exporting to `grading_cases.json`

1. In the Langfuse UI, export the dataset as JSON (or use the Langfuse SDK to fetch items).
2. For each labelled item, construct a case object matching the schema in `grading_cases.json`:

```json
{
  "id": "feedback_<submission_id>",
  "exercise_type": "<type>",
  "question": "<question text>",
  "grammar_rule": "<rule if known>",
  "correct_answer": "<correct answer>",
  "test_answer": "<student answer>",
  "expected_correct": true,
  "bucket": "semantic_correct",
  "note": "Flagged via Telegram 👎 reaction"
}
```

3. Append the new cases to `grading_cases.json`.

## Re-running the eval

```bash
cd api
source .venv/bin/activate
pytest tests/evals/test_grading_eval.py -v
```

The eval will fail if the judge incorrectly marks any `expected_correct: true` case as wrong (false positive rate must be 0%). A false negative rate above 15% triggers a warning.
