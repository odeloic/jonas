interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export default function SearchInput({
  value,
  onChange,
  placeholder = "Suchen…",
}: SearchInputProps) {
  return (
    <div className="relative">
      <svg
        className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none"
        width="15"
        height="15"
        viewBox="0 0 15 15"
        fill="none"
      >
        <path
          d="M10 6.5C10 8.433 8.433 10 6.5 10S3 8.433 3 6.5 4.567 3 6.5 3 10 4.567 10 6.5Zm-.553 4.154a5.5 5.5 0 1 1 .707-.707l3.45 3.449-.708.707-3.449-3.449Z"
          fill="currentColor"
        />
      </svg>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full border border-neutral-200 rounded-lg pl-9 pr-3 py-2 text-[13px] text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:border-neutral-400 focus:ring-1 focus:ring-neutral-200 transition-colors bg-white"
      />
    </div>
  );
}
