import { ButtonHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export function Button({ variant = "secondary", className = "", ...props }: ButtonProps) {
  return <button className={`button ${variant === "primary" ? "primary" : ""} ${className}`.trim()} {...props} />;
}
