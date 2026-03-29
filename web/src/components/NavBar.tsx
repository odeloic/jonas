import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Übersicht", end: true },
  { to: "/grammar", label: "Grammatik" },
  { to: "/vocabulary", label: "Wortschatz" },
  { to: "/assignments", label: "Aufgaben" },
];

export default function NavBar() {
  return (
    <nav className="border-b border-neutral-200 bg-white/80 backdrop-blur-sm sticky top-0 z-40">
      <div className="mx-auto max-w-2xl px-6 flex items-center gap-8 h-14">
        <NavLink
          to="/"
          className="text-[15px] font-semibold tracking-tight text-neutral-900 shrink-0"
        >
          Jonas
        </NavLink>

        <div className="flex items-center gap-1 overflow-x-auto">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md text-[13px] font-medium transition-colors ${
                  isActive
                    ? "text-neutral-900 bg-neutral-100"
                    : "text-neutral-400 hover:text-neutral-600"
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  );
}
