import type { AssignmentItem, SectionType } from "../api/types";

interface ExerciseItemProps {
  item: AssignmentItem;
  sectionType: SectionType;
  index: number;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}

export default function ExerciseItem({
  item,
  sectionType,
  index,
  value,
  onChange,
  disabled,
}: ExerciseItemProps) {
  return (
    <div className="border border-gray-200 rounded-lg p-4 space-y-3">
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
                checked={value === opt}
                onChange={() => onChange(opt)}
                disabled={disabled}
                className="accent-gray-900"
              />
              {opt}
            </label>
          ))}
        </div>
      ) : (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder="Antwort eingeben…"
          className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm text-gray-900 placeholder:text-gray-400 disabled:bg-gray-50"
        />
      )}
    </div>
  );
}
