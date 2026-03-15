export function Timer({ remaining, total }: { remaining: number; total: number }) {
  const fraction = total > 0 ? remaining / total : 0;
  const isWarning = remaining <= 10;

  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex items-center">
      <div className="h-[2px] transition-all duration-1000 ease-linear"
        style={{
          width: `${fraction * 100}%`,
          backgroundColor: isWarning ? 'var(--warm)' : 'var(--rule)',
        }}
      />
      <span className="shrink-0 pr-3 pl-1 font-[family-name:var(--font-system)] text-xs"
        style={{ color: isWarning ? 'var(--warm)' : 'var(--dim)' }}>
        {remaining}
      </span>
    </div>
  );
}
