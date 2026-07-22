import type { ReactNode } from "react";
import { CircleHelp } from "lucide-react";

export function SectionHeading({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="section-heading">
      <h3>{title}</h3>
      {subtitle && <p>{subtitle}</p>}
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
  wide = false,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <label className={`field ${wide ? "field--wide" : ""}`}>
      <span className="field__label">
        {label}
        {hint && (
          <span className="tooltip" tabIndex={0} aria-label={hint}>
            <CircleHelp size={14} aria-hidden="true" />
            <span className="tooltip__content" role="tooltip">
              {hint}
            </span>
          </span>
        )}
      </span>
      {children}
    </label>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      className={`toggle ${checked ? "toggle--active" : ""}`}
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
    >
      <span className="toggle__track"><span className="toggle__thumb" /></span>
      <span>{label}</span>
    </button>
  );
}
