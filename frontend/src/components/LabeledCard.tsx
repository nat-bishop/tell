interface LabeledCardProps {
  label: string;
  children: React.ReactNode;
}

export function LabeledCard({ label, children }: LabeledCardProps) {
  return (
    <div className="card p-5">
      <div className="font-system text-[0.65rem] text-cold tracking-wider uppercase mb-2">
        {label}
      </div>
      {children}
    </div>
  );
}
