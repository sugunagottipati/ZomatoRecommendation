import { ButtonHTMLAttributes } from "react";

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

export function Chip({ active = false, className = "", ...props }: ChipProps) {
  return <button className={`chip ${active ? "active" : ""} ${className}`.trim()} {...props} />;
}
