import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchAssignment, fetchSubmission } from "../api/assignments";
import type {
  AssignmentDetail,
  SubmissionResult,
} from "../api/types";
import ResultSection from "../components/ResultSection";

export default function AssignmentResults() {
  const { id, submissionId } = useParams<{
    id: string;
    submissionId: string;
  }>();
  const [assignment, setAssignment] = useState<AssignmentDetail | null>(null);
  const [result, setResult] = useState<SubmissionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id || !submissionId) return;
    Promise.all([
      fetchAssignment(Number(id)),
      fetchSubmission(Number(id), Number(submissionId)),
    ])
      .then(([a, r]) => {
        setAssignment(a);
        setResult(r);
      })
      .catch(() => setError("Ergebnisse konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [id, submissionId]);

  if (loading) return <p className="text-sm text-gray-500">Laden…</p>;
  if (error) return <p className="text-sm text-red-700">{error}</p>;
  if (!assignment || !result) return null;

  const pct = Math.round((result.score / result.max_score) * 100);

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

      <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-3">
        <p className="text-2xl font-bold text-gray-900">
          {result.score}/{result.max_score} richtig
        </p>
        <div className="w-full bg-gray-100 rounded-full h-2.5">
          <div
            className={`h-2.5 rounded-full ${pct >= 80 ? "bg-green-600" : pct >= 50 ? "bg-yellow-500" : "bg-red-600"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {result.feedback.sections.map((sectionFeedback, i) => (
        <ResultSection
          key={i}
          section={assignment.content.sections[i]}
          feedback={sectionFeedback}
        />
      ))}

      <div className="flex gap-3">
        <Link
          to={`/assignments/${id}`}
          className="flex-1 text-center border border-gray-300 text-gray-700 rounded-lg py-2.5 text-sm font-medium hover:bg-gray-50"
        >
          Nochmal versuchen
        </Link>
        <Link
          to="/assignments"
          className="flex-1 text-center bg-gray-900 text-white rounded-lg py-2.5 text-sm font-medium"
        >
          Zurück zur Liste
        </Link>
      </div>
    </div>
  );
}
