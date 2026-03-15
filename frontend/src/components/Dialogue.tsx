export function Dialogue({ alias, text, animate = true }: { alias: string; text: string; animate?: boolean }) {
  return (
    <div className={animate ? 'animate-fade-in' : ''}>
      <div className="font-literary-sc text-[0.9rem] tracking-[0.08em] leading-none text-ink">
        {alias}
      </div>
      <div className="mt-1 font-literary text-[1.15rem] leading-[1.6] text-ink">
        {text}
      </div>
    </div>
  );
}
