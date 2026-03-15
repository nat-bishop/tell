export function Stage({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto min-h-screen max-w-[36rem] px-5 pt-12 pb-24 sm:px-8">
      {children}
    </div>
  );
}
