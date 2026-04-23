interface ProgressBarProps {
  percent: number;
  message: string;
}

function clampPercent(value: number): number {
  if (value < 0) {
    return 0;
  }

  if (value > 100) {
    return 100;
  }

  return value;
}

export function ProgressBar({ percent, message }: ProgressBarProps) {
  const safePercent = clampPercent(percent);

  return (
    <div>
      <div className="progress-bar" aria-hidden="true">
        <div
          className="progress-bar-fill"
          style={{ width: `${safePercent}%` }}
        />
      </div>
      <p className="progress-bar-text">
        {Math.round(safePercent)}% - {message || "處理中"}
      </p>
    </div>
  );
}
