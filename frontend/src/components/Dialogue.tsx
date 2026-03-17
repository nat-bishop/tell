export function Dialogue({ alias, text, animate = true }: { alias: string; text: string; animate?: boolean }) {
  return (
    <div className={animate ? 'animate-fade-in' : ''}>
      <div className="font-system text-[0.75rem] tracking-[0.1em] uppercase leading-none text-cold">
        {alias}
      </div>
      <div className="mt-1.5 font-literary text-[1.1rem] leading-[1.6] text-ink">
        {text}
      </div>
    </div>
  );
}
