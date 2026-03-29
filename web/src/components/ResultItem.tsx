import type { ItemFeedback } from "../api/types";

interface ResultItemProps {
  feedback: ItemFeedback;
  question: string;
  index: number;
}

export default function ResultItem({
  feedback,
  question,
  index,
}: ResultItemProps) {
  const borderColor = feedback.correct ? "border-green-700" : "border-red-700";

  return (
    <div className={`border ${borderColor} rounded-lg p-4 space-y-2`}>
      <p className="text-gray-900">
        <span className="text-gray-400 text-sm mr-2">{index}.</span>
        {question}
      </p>

      <p className="text-sm">
        <span className="text-gray-500">Deine Antwort: </span>
        <span className={feedback.correct ? "text-green-700" : "text-red-700"}>
          {feedback.user_answer || "—"}
        </span>
      </p>

      {feedback.correct ? (
        <p className="text-sm text-green-700 font-medium">Richtig!</p>
      ) : (
        <>
          <p className="text-sm">
            <span className="text-gray-500">Richtige Antwort: </span>
            <span className="text-gray-900 font-medium">
              {feedback.correct_answer}
            </span>
          </p>
          {feedback.hint && (
            <p className="text-xs text-gray-500">Hinweis: {feedback.hint}</p>
          )}
        </>
      )}
    </div>
  );
}
