"use client";

interface AnswerCardProps {
  alias: string;
  answer?: string;
  highlighted?: boolean;
  label?: string;
  delay?: number;
  children?: React.ReactNode;
  as?: "button" | "div";
  onClick?: () => void;
  disabled?: boolean;
}

export function AnswerCard({
  alias,
  answer,
  highlighted = false,
  label,
  delay = 0,
  children,
  as = "div",
  onClick,
  disabled,
}: AnswerCardProps) {
  const content = (
    <div className="flex flex-col h-full">
      {/* Answer — the primary content */}
      {answer ? (
        <div className="font-literary text-[1.05rem] leading-[1.55] text-ink">
          {answer}
        </div>
      ) : (
        <div className="font-literary text-[0.95rem] italic text-dim">
          no answer submitted
        </div>
      )}

      {/* Children slot — Q&A exchange in ReviewPhase */}
      {children}

      {/* Attribution — name pinned to bottom */}
      <div className="mt-auto pt-3 border-t border-rule">
        <div
          className={`font-literary-sc text-[0.8rem] tracking-[0.08em] ${
            highlighted ? "text-warm" : "text-dim"
          }`}
        >
          {alias}
        </div>
        {label && (
          <div className="mt-0.5 font-system text-[0.65rem] text-warm">
            {label}
          </div>
        )}
      </div>
    </div>
  );

  const baseClass = `border p-5 h-full animate-fade-in transition-colors duration-150 ${
    !highlighted ? "border-rule" : ""
  }`;
  const style = {
    animationDelay: delay ? `${delay}ms` : undefined,
    borderColor: highlighted ? "var(--warm)" : undefined,
  };

  if (as === "button") {
    return (
      <button
        onClick={onClick}
        disabled={disabled}
        className={`${baseClass} cursor-pointer text-left w-full`}
        style={style}
      >
        {content}
      </button>
    );
  }

  return (
    <div className={baseClass} style={style}>
      {content}
    </div>
  );
}
