interface EmptyStateProps {
  title: string;
  description?: string;
}

export default function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-10 h-10 rounded-full bg-neutral-100 flex items-center justify-center mb-4">
        <svg
          width="18"
          height="18"
          viewBox="0 0 15 15"
          fill="none"
          className="text-neutral-400"
        >
          <path
            d="M7.5.877a6.623 6.623 0 1 0 0 13.246A6.623 6.623 0 0 0 7.5.877ZM1.827 7.5a5.673 5.673 0 1 1 11.346 0 5.673 5.673 0 0 1-11.346 0ZM7.5 4a.5.5 0 0 1 .5.5v2.5H10.5a.5.5 0 0 1 0 1H8v2.5a.5.5 0 0 1-1 0V8H4.5a.5.5 0 0 1 0-1H7V4.5a.5.5 0 0 1 .5-.5Z"
            fill="currentColor"
          />
        </svg>
      </div>
      <p className="text-[14px] font-medium text-neutral-900">{title}</p>
      {description && (
        <p className="text-[13px] text-neutral-400 mt-1 max-w-xs">
          {description}
        </p>
      )}
    </div>
  );
}
