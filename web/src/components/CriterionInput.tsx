import type { CriterionExerciseItem } from "../api/types";

interface Props {
  item: CriterionExerciseItem;
  index: number;
  value: string[];
  onChange: (value: string[]) => void;
  disabled: boolean;
}

// Renders one text input per blank, in blank index order. Submission shape is
// one string per blank, aligned by position.
export default function CriterionInput({
  item,
  index,
  value,
  onChange,
  disabled,
}: Props) {
  const blankCount = Math.max(item.blanks.length, 1);
  const padded = Array.from({ length: blankCount }, (_, i) => value[i] ?? "");

  function setBlank(blankIdx: number, next: string) {
    const updated = padded.slice();
    updated[blankIdx] = next;
    onChange(updated);
  }

  return (
    <div className="space-y-3">
      <p className="text-gray-900 leading-relaxed">
        <span className="text-gray-400 text-sm mr-2">{index}.</span>
        {item.question}
      </p>
      <div className="space-y-2">
        {item.blanks.map((blank, i) => (
          <div key={blank.index} className="flex items-center gap-2">
            <span className="text-xs text-gray-400 w-16">
              {blankCount === 1 ? "Antwort" : `Lücke ${blank.index + 1}`}
            </span>
            <input
              type="text"
              value={padded[i]}
              onChange={(e) => setBlank(i, e.target.value)}
              disabled={disabled}
              placeholder="…"
              className="flex-1 px-2 py-1 border-b border-gray-400 focus:border-gray-900 focus:outline-none text-gray-900 placeholder:text-gray-400 disabled:bg-gray-50"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
