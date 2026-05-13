import type { CriterionExerciseItem } from "../api/types";

interface Props {
  item: CriterionExerciseItem;
  index: number;
  value: string[];
  onChange: (value: string[]) => void;
  disabled: boolean;
}

// Splits a question on each ___ and renders an inline input between segments.
// Submission shape is one string per blank, in document order.
export default function CriterionInput({
  item,
  index,
  value,
  onChange,
  disabled,
}: Props) {
  const segments = item.question.split("___");
  const blankCount = Math.max(segments.length - 1, 1);

  // Pad value to blank count so React sees a stable number of inputs.
  const padded = Array.from({ length: blankCount }, (_, i) => value[i] ?? "");

  function setBlank(blankIdx: number, next: string) {
    const updated = padded.slice();
    updated[blankIdx] = next;
    onChange(updated);
  }

  return (
    <div className="space-y-2">
      <p className="text-gray-900 leading-relaxed">
        <span className="text-gray-400 text-sm mr-2">{index}.</span>
        {segments.map((seg, i) => (
          <span key={i}>
            {seg}
            {i < segments.length - 1 && (
              <input
                type="text"
                value={padded[i]}
                onChange={(e) => setBlank(i, e.target.value)}
                disabled={disabled}
                placeholder="…"
                className="inline-block mx-1 px-2 py-0.5 border-b border-gray-400 focus:border-gray-900 focus:outline-none text-gray-900 placeholder:text-gray-400 disabled:bg-gray-50 min-w-24"
                style={{ width: `${Math.max(padded[i].length, 6)}ch` }}
              />
            )}
          </span>
        ))}
      </p>
    </div>
  );
}
