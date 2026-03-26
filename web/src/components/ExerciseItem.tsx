import { useState } from "react";
import type { AssignmentItem, SectionType } from "../api/types";

interface ExerciseItemProps {
  item: AssignmentItem;
  sectionType: SectionType;
  index: number;
}

export default function ExerciseItem({
  item,
  sectionType,
  index,
}: ExerciseItemProps) {
  const [answer, setAnswer] = useState("");
  const [checked, setChecked] = useState(false);
  const [correct, setCorrect] = useState(false);

  function check() {
    const normalise = (s: string) => s.trim().toLowerCase();
    setCorrect(normalise(answer) === normalise(item.correct_answer));
    setChecked(true);
  }

  function reset() {
    setAnswer("");
    setChecked(false);
    setCorrect(false);
  }

  const borderColor = !checked
    ? "border-gray-200"
    : correct
      ? "border-green-700"
      : "border-red-700";

  return (
    <div className={`border ${borderColor} rounded-lg p-4 space-y-3`}>
      <p className="text-gray-900">
        <span className="text-gray-400 text-sm mr-2">{index}.</span>
        {item.question}
      </p>

      {sectionType === "MULTIPLE_CHOICE" && item.options ? (
        <div className="space-y-1.5">
          {item.options.map((opt) => (
            <label
              key={opt}
              className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer"
            >
              <input
                type="radio"
                name={`q-${index}`}
                value={opt}
                checked={answer === opt}
                onChange={() => setAnswer(opt)}
                disabled={checked}
                className="accent-gray-900"
              />
              {opt}
            </label>
          ))}
        </div>
      ) : (
        <input
          type="text"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && answer.trim()) check();
          }}
          disabled={checked}
          placeholder="Antwort eingeben…"
          className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 disabled:bg-gray-50"
        />
      )}

      <div className="flex items-center gap-3">
        {!checked ? (
          <button
            onClick={check}
            disabled={!answer.trim()}
            className="text-sm font-medium text-gray-700 border border-gray-300 rounded px-3 py-1 disabled:opacity-40"
          >
            Prüfen
          </button>
        ) : (
          <button
            onClick={reset}
            className="text-sm font-medium text-gray-700 border border-gray-300 rounded px-3 py-1"
          >
            Nochmal
          </button>
        )}

        {checked && (
          <span className={`text-sm ${correct ? "text-green-700" : "text-red-700"}`}>
            {correct
              ? "Richtig!"
              : `Falsch — ${item.correct_answer}`}
          </span>
        )}
      </div>

      {checked && !correct && item.hint && (
        <p className="text-xs text-gray-500">Hinweis: {item.hint}</p>
      )}
    </div>
  );
}
