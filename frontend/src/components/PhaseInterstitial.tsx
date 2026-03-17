import type { GamePhase } from "@/hooks/useGameStore";

interface PhaseInterstitialProps {
  phase: GamePhase;
  roundNumber: number;
  roundType: string | null;
  fading: boolean;
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
}: PhaseInterstitialProps) {
  let text: string;
  let subtitle: string | undefined;

  if (phase === "prompt") {
    text = `ROUND ${roundNumber}`;
    subtitle = roundType?.toUpperCase() || undefined;
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
      {subtitle && (
        <p className="font-system text-[0.7rem] text-cold tracking-[0.25em] uppercase">
          {subtitle}
        </p>
      )}
    </div>
  );
}
