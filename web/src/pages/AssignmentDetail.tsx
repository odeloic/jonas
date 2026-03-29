import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { fetchAssignment, submitAssignment } from "../api/assignments";
import type { AssignmentDetail as AssignmentDetailType } from "../api/types";
import ExerciseSection from "../components/ExerciseSection";

export default function AssignmentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [assignment, setAssignment] = useState<AssignmentDetailType | null>(
    null,
  );
  const [answers, setAnswers] = useState<string[][]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchAssignment(Number(id))
      .then((data) => {
        setAssignment(data);
        setAnswers(data.content.sections.map((s) => s.items.map(() => "")));
      })
      .catch(() => setError("Aufgabe konnte nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [id]);

  const allFilled =
    answers.length > 0 &&
    answers.every((section) => section.every((a) => a.trim() !== ""));

  async function handleSubmit() {
    if (!id || !allFilled) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await submitAssignment(Number(id), {
        sections: answers.map((items) => ({ items })),
      });
      navigate(`/assignments/${id}/results/${result.id}`);
    } catch {
      setError("Beim Absenden ist ein Fehler aufgetreten.");
      setSubmitting(false);
    }
  }

  if (loading) return <p className="text-sm text-gray-500">Laden…</p>;
  if (error && !assignment)
    return <p className="text-sm text-red-700">{error}</p>;
  if (!assignment) return null;

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/assignments"
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          ← Aufgaben
        </Link>
        <h1 className="text-xl font-bold text-gray-900 mt-2">
          {assignment.topic}
        </h1>
      </div>

      {assignment.content.sections.map((section, i) => (
        <ExerciseSection
          key={i}
          section={section}
          answers={answers[i] ?? []}
          onAnswerChange={(itemIndex, value) => {
            setAnswers((prev) => {
              const next = prev.map((s) => [...s]);
              next[i][itemIndex] = value;
              return next;
            });
          }}
          disabled={submitting}
        />
      ))}

      {error && <p className="text-sm text-red-700">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={!allFilled || submitting}
        className="w-full bg-gray-900 text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-40"
      >
        {submitting ? "Wird gesendet…" : "Abgeben"}
      </button>
    </div>
  );
}
