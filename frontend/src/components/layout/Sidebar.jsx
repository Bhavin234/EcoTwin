import { NavLink } from "react-router-dom";
import "./Sidebar.css";

const NAV_ITEMS = [
  { to: "/", label: "Overview", end: true },
  { to: "/resources", label: "Resources" },
  { to: "/investigations", label: "Investigations" },
  { to: "/impact", label: "Impact" },
  { to: "/data", label: "Data" },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <span className="sidebar__brand-mark" aria-hidden="true" />
        <div>
          <p className="sidebar__brand-name">EcoTwin</p>
          <p className="sidebar__brand-tagline">Sustainability Intelligence</p>
        </div>
      </div>
      <nav className="sidebar__nav" aria-label="Primary">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `sidebar__link${isActive ? " sidebar__link--active" : ""}`}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
