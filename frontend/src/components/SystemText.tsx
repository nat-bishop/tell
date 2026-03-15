export function SystemText({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-[family-name:var(--font-system)] text-[0.75rem]"
      style={{ color: 'var(--dim)' }}>
      {children}
    </div>
  );
}
