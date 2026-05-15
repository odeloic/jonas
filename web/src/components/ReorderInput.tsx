import type { ReorderExerciseItem } from "../api/types";

interface Props {
  item: ReorderExerciseItem;
  index: number;
  value: string[];
  onChange: (value: string[]) => void;
  disabled: boolean;
}

export default function ReorderInput({
  item,
  index,
  value,
  onChange,
  disabled,
}: Props) {
  // Track consumed bag indices so duplicate tokens ("ich"/"ich") don't both vanish
  // when one is placed.
  const consumed = new Set<number>();
  for (const placed of value) {
    for (let i = 0; i < item.tokens.length; i++) {
      if (item.tokens[i] === placed && !consumed.has(i)) {
        consumed.add(i);
        break;
      }
    }
  }

  function placeToken(bagIdx: number) {
    if (disabled) return;
    onChange([...value, item.tokens[bagIdx]]);
  }

  function removePlaced(slotIdx: number) {
    if (disabled) return;
    onChange(value.filter((_, i) => i !== slotIdx));
  }

  return (
    <div className="space-y-3">
      <p className="text-gray-900">
        <span className="text-gray-400 text-sm mr-2">{index}.</span>
        Bringe die Wörter in die richtige Reihenfolge:
      </p>

      <div className="min-h-[2.5rem] border border-gray-300 rounded p-2 flex flex-wrap gap-1.5 bg-gray-50">
        {value.length === 0 && (
          <span className="text-xs text-gray-400 self-center">
            Tippe ein Wort unten an, um es hier einzufügen.
          </span>
        )}
        {value.map((tok, slotIdx) => (
          <button
            key={slotIdx}
            type="button"
            disabled={disabled}
            onClick={() => removePlaced(slotIdx)}
            className="px-2 py-1 bg-white border border-gray-300 rounded text-sm text-gray-900 hover:bg-gray-50 disabled:opacity-50"
          >
            {tok}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {item.tokens.map((tok, bagIdx) => (
          <button
            key={bagIdx}
            type="button"
            disabled={disabled || consumed.has(bagIdx)}
            onClick={() => placeToken(bagIdx)}
            className="px-2 py-1 border border-gray-300 rounded text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {tok}
          </button>
        ))}
      </div>
    </div>
  );
}
