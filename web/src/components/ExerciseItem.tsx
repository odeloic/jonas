import type { ExerciseItem } from "../api/types";
import CriterionInput from "./CriterionInput";
import MultipleChoiceInput from "./MultipleChoiceInput";
import ReorderInput from "./ReorderInput";

interface Props {
  item: ExerciseItem;
  index: number;
  value: string[];
  onChange: (value: string[]) => void;
  disabled: boolean;
}

export default function ExerciseItemView({
  item,
  index,
  value,
  onChange,
  disabled,
}: Props) {
  return (
    <div className="border border-gray-200 rounded-lg p-4">
      {renderInput({ item, index, value, onChange, disabled })}
    </div>
  );
}

function renderInput(props: Props) {
  const { item } = props;
  switch (item.type) {
    case "MULTIPLE_CHOICE":
      return <MultipleChoiceInput {...props} item={item} />;
    case "REORDER":
      return <ReorderInput {...props} item={item} />;
    case "COMPLETION":
    case "FILL_IN_THE_BLANK":
      return <CriterionInput {...props} item={item} />;
  }
}
