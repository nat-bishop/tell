export function Timer({ remaining, total }: { remaining: number; total: number }) {
  const fraction = total > 0 ? remaining / total : 0;
  const isWarning = remaining <= 10;
  const isUrgent = remaining <= 5;
  const isCritical = remaining <= 3;

  const pulseClass = isCritical
    ? "animate-timer-pulse-fast"
    : isUrgent
      ? "animate-timer-pulse"
      : "";

  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex items-center">
      <div
        className="transition-all duration-1000 ease-linear"
        style={{
          width: `${fraction * 100}%`,
          height: isUrgent ? "3px" : "2px",
          backgroundColor: isWarning ? 'var(--warm)' : 'var(--rule)',
        }}
      />
      <span
        className={`shrink-0 pr-3 pl-1 font-system text-xs ${
          isWarning ? 'text-warm' : 'text-dim'
        } ${pulseClass}`}
      >
        {remaining}
      </span>
    </div>
  );
}
