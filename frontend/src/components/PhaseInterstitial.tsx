import type { GamePhase } from "@/hooks/useGameStore";

interface PhaseInterstitialProps {
  phase: GamePhase;
  roundNumber: number;
  roundType: string | null;
  fading: boolean;
  isRoundStart?: boolean;
}

const DIRECTIVES: Partial<Record<GamePhase, { text: string; subtitle?: string }>> = {
  nominate: { text: "SELECT TARGET" },
  respond: { text: "DEFEND YOURSELF" },
  review: { text: "IDENTIFY HUMAN" },
  elimination: { text: "VOTE RESULT" },
};

export function PhaseInterstitial({
  phase,
  roundNumber,
  roundType,
  fading,
  isRoundStart = false,
}: PhaseInterstitialProps) {
  let text: string;
  let subtitle: string | undefined;

  if (phase === "prompt" || phase === "chain") {
    text = `ROUND ${roundNumber}`;
    subtitle = phase === "chain"
      ? "WORD CHAIN"
      : roundType?.toUpperCase() || undefined;
  } else if (phase === "question") {
    text = roundType === "interrogation" ? "INTERROGATION" : "CROSS-EXAMINE";
  } else {
    const directive = DIRECTIVES[phase];
    text = directive?.text || phase.toUpperCase();
    subtitle = directive?.subtitle;
  }

  return (
    <div
      className={`relative flex min-h-[60vh] flex-col items-center justify-center gap-4 ${
        fading ? "animate-interstitial-out" : "animate-interstitial-in"
      } ${!fading ? "interstitial-scan" : ""}`}
    >
      <p
        className="font-system text-[1.4rem] text-ink tracking-[0.2em] uppercase"
        style={{ textShadow: '0 0 30px var(--cold-glow)' }}
      >
        {text}
      </p>
      {isRoundStart && subtitle && !fading && (
        <>
          <hr
            className="animate-line-draw border-none"
            style={{
              animationDelay: "1s",
              height: "1px",
              background: "var(--rule)",
            }}
          />
          <p
            className="animate-reveal-expand font-system text-[0.7rem] text-cold tracking-[0.25em] uppercase"
            style={{ animationDelay: "1.5s" }}
          >
            {subtitle}
          </p>
        </>
      )}
      {!isRoundStart && subtitle && (
        <p className="font-system text-[0.7rem] text-cold tracking-[0.25em] uppercase">
          {subtitle}
        </p>
      )}
    </div>
  );
}
