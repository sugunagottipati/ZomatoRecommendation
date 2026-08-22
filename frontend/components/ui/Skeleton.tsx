interface SkeletonProps {
  height: number;
  className?: string;
}

export function Skeleton({ height, className = "" }: SkeletonProps) {
  return <div className={`skeleton ${className}`.trim()} style={{ height }} aria-hidden="true" />;
}
