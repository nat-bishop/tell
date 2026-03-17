"use client";

interface AnswerCardProps {
  alias: string;
  answer?: string;
  highlighted?: boolean;
  label?: string;
  showVotedLabel?: boolean;
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
  showVotedLabel = false,
  delay = 0,
  children,
  as = "div",
  onClick,
  disabled,
}: AnswerCardProps) {
  const content = (
    <div className="flex flex-col h-full">
      {/* Answer — the human voice */}
      {answer ? (
        <div className="font-literary text-[1.1rem] leading-[1.6] text-ink">
          {answer}
        </div>
      ) : (
        <div className="font-system text-[0.85rem] text-dim tracking-wide">
          NO RESPONSE
        </div>
      )}

      {/* Children slot — Q&A exchange in ReviewPhase */}
      {children}

      {/* Attribution — name pinned to bottom */}
      <div className="mt-auto pt-3 border-t border-rule flex items-baseline justify-between">
        <div
          className={`font-system text-[0.75rem] tracking-[0.1em] uppercase ${
            highlighted ? "text-warm" : "text-dim"
          }`}
        >
          {alias}
        </div>
        {label && (
          <div className="font-system text-[0.6rem] text-warm tracking-wider uppercase">
            {label}
          </div>
        )}
        {showVotedLabel && (
          <div className="font-system text-[0.6rem] text-warm tracking-wider uppercase">
            voted
          </div>
        )}
      </div>
    </div>
  );

  const baseClass = `card p-5 h-full animate-fade-in ${
    highlighted ? "card-highlighted animate-vote-select" : ""
  } ${as === "button" && !disabled ? "card-interactive" : ""}`;

  const style = {
    animationDelay: delay ? `${delay}ms` : undefined,
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
