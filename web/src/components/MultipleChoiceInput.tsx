import type { MultipleChoiceExerciseItem } from "../api/types";

interface Props {
  item: MultipleChoiceExerciseItem;
  index: number;
  value: string[];
  onChange: (value: string[]) => void;
  disabled: boolean;
}

export default function MultipleChoiceInput({
  item,
  index,
  value,
  onChange,
  disabled,
}: Props) {
  const selected = value[0] ?? "";
  return (
    <div className="space-y-3">
      <p className="text-gray-900">
        <span className="text-gray-400 text-sm mr-2">{index}.</span>
        {item.question}
      </p>
      <div className="space-y-1.5">
        {item.options.map((opt) => (
          <label
            key={opt.index}
            className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer"
          >
            <input
              type="radio"
              name={`q-${index}`}
              value={opt.text}
              checked={selected === opt.text}
              onChange={() => onChange([opt.text])}
              disabled={disabled}
              className="accent-gray-900"
            />
            {opt.text}
          </label>
        ))}
      </div>
    </div>
  );
}
