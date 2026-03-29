interface BadgeProps {
  children: React.ReactNode;
  active?: boolean;
  onClick?: () => void;
}

export default function Badge({ children, active, onClick }: BadgeProps) {
  const base =
    "inline-flex items-center px-2.5 py-1 rounded-md text-[12px] font-medium transition-colors select-none";
  const interactive = onClick ? "cursor-pointer" : "";
  const variant = active
    ? "bg-neutral-900 text-white"
    : "bg-neutral-100 text-neutral-500 hover:bg-neutral-200 hover:text-neutral-700";

  return (
    <span className={`${base} ${interactive} ${variant}`} onClick={onClick}>
      {children}
    </span>
  );
}
