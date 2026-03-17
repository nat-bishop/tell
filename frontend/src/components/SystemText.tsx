export function SystemText({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-system text-[0.75rem] text-cold tracking-wide">
      {children}
    </div>
  );
}
