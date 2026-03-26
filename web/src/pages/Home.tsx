import { Link } from "react-router-dom";

export default function Home() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Jonas</h1>
      <div className="text-gray-600">Deutsch Tutor</div>
      <Link
        to="/assignments"
        className="block border border-gray-200 rounded-lg p-4 text-center text-gray-700 hover:bg-gray-100 transition-colors"
      >
        Aufgaben ansehen
      </Link>
    </div>
  );
}
