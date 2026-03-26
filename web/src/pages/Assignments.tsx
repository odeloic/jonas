import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchAssignments } from "../api/assignments";
import type { AssignmentSummary } from "../api/types";

const dateFmt = new Intl.DateTimeFormat("de-DE", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export default function Assignments() {
  const [assignments, setAssignments] = useState<AssignmentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAssignments()
      .then(setAssignments)
      .catch(() => setError("Aufgaben konnten nicht geladen werden."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-gray-500">Laden…</p>;
  if (error) return <p className="text-sm text-red-700">{error}</p>;

  return (
    <div className="space-y-3">
      <h1 className="text-xl font-bold text-gray-900">Aufgaben</h1>

      {assignments.length === 0 ? (
        <p className="text-sm text-gray-500">Keine Aufgaben vorhanden.</p>
      ) : (
        assignments.map((a) => (
          <Link
            key={a.id}
            to={`/assignments/${a.id}`}
            className="block border border-gray-200 rounded-lg p-4 hover:bg-gray-100 transition-colors"
          >
            <div className="font-medium text-gray-900">{a.topic}</div>
            <div className="text-sm text-gray-500 mt-1">
              {dateFmt.format(new Date(a.created_at))} · {a.type}
            </div>
          </Link>
        ))
      )}
    </div>
  );
}
