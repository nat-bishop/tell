import type { GamePhase } from "@/hooks/useGameStore";

interface PhaseInterstitialProps {
  phase: GamePhase;
  roundNumber: number;
  roundType: string | null;
  fading: boolean;
}

const DIRECTIVES: Partial<Record<GamePhase, { text: string; subtitle?: string }>> = {
  nominate: { text: "who should be interrogated?" },
  respond: { text: "defend yourself" },
  review: { text: "who is human?" },
  elimination: { text: "the vote" },
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
    text = `round ${roundNumber}`;
    subtitle = roundType || undefined;
  } else if (phase === "question") {
    text = roundType === "interrogation" ? "the interrogation" : "cross-examine";
  } else {
    const directive = DIRECTIVES[phase];
    text = directive?.text || phase;
    subtitle = directive?.subtitle;
  }

  return (
    <div
      className={`flex min-h-[60vh] flex-col items-center justify-center gap-3 ${
        fading ? "animate-interstitial-out" : "animate-interstitial-in"
      }`}
    >
      <p className="font-literary text-[1.5rem] text-ink text-center">
        {text}
      </p>
      {subtitle && (
        <p className="font-system text-[0.75rem] text-dim tracking-wide">
          {subtitle}
        </p>
      )}
    </div>
  );
}
