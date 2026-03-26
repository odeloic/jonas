import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchAssignment } from "../api/assignments";
import type { AssignmentDetail as AssignmentDetailType } from "../api/types";
import ExerciseSection from "../components/ExerciseSection";

export default function AssignmentDetail() {
  const { id } = useParams<{ id: string }>();
  const [assignment, setAssignment] = useState<AssignmentDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchAssignment(Number(id))
      .then(setAssignment)
      .catch(() => setError("Aufgabe konnte nicht geladen werden."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="text-sm text-gray-500">Laden…</p>;
  if (error) return <p className="text-sm text-red-700">{error}</p>;
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
        <ExerciseSection key={i} section={section} />
      ))}
    </div>
  );
}
