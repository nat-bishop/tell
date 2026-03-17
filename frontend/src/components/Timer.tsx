export function Timer({ remaining, total }: { remaining: number; total: number }) {
  const fraction = total > 0 ? remaining / total : 0;
  const isWarning = remaining <= Math.min(10, Math.floor(total * 0.25));
  const isUrgent = remaining <= Math.min(5, Math.floor(total * 0.15));
  const isCritical = remaining <= Math.min(3, Math.floor(total * 0.1));

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
          backgroundColor: isWarning ? 'var(--warm)' : 'var(--cold)',
          boxShadow: isWarning
            ? '0 0 12px var(--warm), 0 0 24px var(--glow)'
            : '0 0 8px var(--cold-glow)',
        }}
      />
      <span
        className={`shrink-0 pr-3 pl-1 font-system text-xs tracking-wider ${
          isWarning ? 'text-warm' : 'text-cold'
        } ${pulseClass}`}
      >
        {remaining}
      </span>
    </div>
  );
}
