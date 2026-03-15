export function Stage({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto min-h-screen max-w-[36rem] px-8 pt-12 pb-24">
      {children}
    </div>
  );
}
