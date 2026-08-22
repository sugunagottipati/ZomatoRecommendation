import { PropsWithChildren } from "react";

interface PanelProps extends PropsWithChildren {
  className?: string;
}

export function Panel({ className = "", children }: PanelProps) {
  return <section className={`panel ${className}`.trim()}>{children}</section>;
}
