import type { ExerciseItem, ItemFeedback } from "../api/types";

interface Props {
  feedback: ItemFeedback;
  item: ExerciseItem;
  index: number;
}

export default function ResultItem({ feedback, item, index }: Props) {
  const borderColor = feedback.correct ? "border-green-700" : "border-red-700";
  const submitted = formatUserAnswer(feedback.user_answer);
  const isCriterion =
    item.type === "COMPLETION" || item.type === "FILL_IN_THE_BLANK";

  return (
    <div className={`border ${borderColor} rounded-lg p-4 space-y-2`}>
      <p className="text-gray-900">
        <span className="text-gray-400 text-sm mr-2">{index}.</span>
        {renderQuestionPreview(item)}
      </p>

      <p className="text-sm">
        <span className="text-gray-500">Deine Antwort: </span>
        <span className={feedback.correct ? "text-green-700" : "text-red-700"}>
          {submitted || "—"}
        </span>
      </p>

      {feedback.correct ? (
        <p className="text-sm text-green-700 font-medium">Richtig!</p>
      ) : (
        <>
          {isCriterion ? (
            <>
              {feedback.blank_feedbacks && feedback.blank_feedbacks.length > 1 ? (
                <div className="space-y-2">
                  {feedback.blank_feedbacks.map((bf) => (
                    <div
                      key={bf.index}
                      className={`text-xs border-l-2 pl-2 ${
                        bf.correct ? "border-green-700" : "border-red-700"
                      }`}
                    >
                      <p className="text-gray-700">
                        <span className="text-gray-500">Lücke {bf.index + 1}: </span>
                        {bf.correct ? "richtig" : "falsch"}
                      </p>
                      {!bf.correct && bf.example_answer && (
                        <p className="text-gray-600">
                          <span className="text-gray-500">Beispiel: </span>
                          {bf.example_answer}
                        </p>
                      )}
                      {!bf.correct && bf.grading_criterion && (
                        <p className="text-gray-500">{bf.grading_criterion}</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <>
                  {feedback.example_answer && (
                    <p className="text-sm">
                      <span className="text-gray-500">Beispielantwort: </span>
                      <span className="text-gray-900 font-medium">
                        {feedback.example_answer}
                      </span>
                    </p>
                  )}
                  {feedback.grading_criterion && (
                    <p className="text-xs text-gray-600">
                      <span className="text-gray-500">Kriterium: </span>
                      {feedback.grading_criterion}
                    </p>
                  )}
                </>
              )}
            </>
          ) : (
            feedback.correct_answer && (
              <p className="text-sm">
                <span className="text-gray-500">Richtige Antwort: </span>
                <span className="text-gray-900 font-medium">
                  {feedback.correct_answer}
                </span>
              </p>
            )
          )}
          {feedback.hint && (
            <p className="text-xs text-gray-500">Hinweis: {feedback.hint}</p>
          )}
        </>
      )}
    </div>
  );
}

function formatUserAnswer(values: string[]): string {
  return values.filter((v) => v.length > 0).join(" / ");
}

function renderQuestionPreview(item: ExerciseItem): string {
  if (item.type === "REORDER") {
    return `(${item.tokens.join(" / ")})`;
  }
  return item.question;
}
