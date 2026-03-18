import type { GamePhase, PlayerInfo } from "@/hooks/useGameStore";

interface PhaseInterstitialProps {
  phase: GamePhase;
  roundNumber: number;
  roundType: string | null;
  fading: boolean;
  isRoundStart?: boolean;
  totalRounds?: number;
  scores?: Record<string, number>;
  players?: PlayerInfo[];
}

// ─── Robot Voice Archetypes ───

type VoiceId = "clinical" | "bureaucratic" | "military" | "malfunctioning" | "friendly";

interface Voice {
  roundLabel: (n: number, type: string | null) => string;
  typeLabel: (type: string | null) => string;
}

const VOICES: Record<VoiceId, Voice> = {
  clinical: {
    roundLabel: (n, type) => {
      if (type === "brain_test") return `TEST SEQUENCE ${n} / RAPID ASSESSMENT`;
      return `TEST SEQUENCE ${n} / PERFORMANCE EVAL`;
    },
    typeLabel: (type) => {
      if (type === "brain_test") return "QUICK DRAW";
      return "MATCHUP";
    },
  },
  bureaucratic: {
    roundLabel: (n, type) => {
      if (type === "brain_test") return `PLEASE PROCEED TO ASSESSMENT ${n}`;
      return `ASSESSMENT ${n} / STANDARD FORM`;
    },
    typeLabel: (type) => {
      if (type === "brain_test") return "FORM 9D: RAPID RESPONSE";
      return "FORM 3A: HEAD TO HEAD";
    },
  },
  military: {
    roundLabel: (n, type) => {
      if (type === "brain_test") return `OPERATION ${n} / SNAP JUDGMENT`;
      return `OPERATION ${n} / FIELD TEST`;
    },
    typeLabel: (type) => {
      if (type === "brain_test") return "RAPID FIRE";
      return "TARGET COMPARISON";
    },
  },
  malfunctioning: {
    roundLabel: (n, type) => {
      if (type === "brain_test") return `R-R-ROUND ${n} / Q-QUICK... DRAW`;
      return `R-R-ROUND ${n} / M-MATCHUP [retry]`;
    },
    typeLabel: (type) => {
      if (type === "brain_test") return "PICK— PICK AN OPTION. [retry]";
      return "COMPARE. [buffer overflow]";
    },
  },
  friendly: {
    roundLabel: (n, type) => {
      if (type === "brain_test") return `round ${n}! quick quiz time :)`;
      return `round ${n}! here we go :)`;
    },
    typeLabel: (type) => {
      if (type === "brain_test") return "quick draw";
      return "who sounds more human?";
    },
  },
};

const VOICE_ORDER: VoiceId[] = ["clinical", "bureaucratic", "military", "malfunctioning", "friendly"];

function getVoice(roundNumber: number): Voice {
  const idx = (roundNumber - 1) % VOICE_ORDER.length;
  return VOICES[VOICE_ORDER[idx]];
}

// ─── Phase Directives + Subtitles ───

interface Directive {
  text: string;
  subtitle: string;
}

function getDirective(phase: GamePhase): Directive | null {
  switch (phase) {
    case "matchup":
      return {
        text: "MATCHUP",
        subtitle: "who sounds more human?",
      };
    default:
      return null;
  }
}

// ─── Situation Lines ───

function getSituationLine(
  roundNumber: number,
  totalRounds: number,
  scores?: Record<string, number>,
  players?: PlayerInfo[],
): string | null {
  // Final round
  if (totalRounds > 0 && roundNumber >= totalRounds) {
    return "final round";
  }

  // Round 1 — clean start
  if (roundNumber <= 1) return null;

  // Show round progress
  if (totalRounds > 0) {
    // Show leader if scores exist
    if (scores && players && Object.keys(scores).length > 0) {
      const maxScore = Math.max(...Object.values(scores));
      if (maxScore > 0) {
        const leaders = players.filter(p => (scores[p.id] ?? 0) === maxScore);
        if (leaders.length === 1) {
          return `${leaders[0].alias} leads with ${maxScore}`;
        }
        return `round ${roundNumber} of ${totalRounds}`;
      }
    }
    return `round ${roundNumber} of ${totalRounds}`;
  }

  return null;
}

// ─── Component ───

export function PhaseInterstitial({
  phase,
  roundNumber,
  roundType,
  fading,
  isRoundStart = false,
  totalRounds = 5,
  scores = {},
  players = [],
}: PhaseInterstitialProps) {
  const voice = getVoice(roundNumber);
  let text: string;
  let subtitle: string | undefined;
  let situationLine: string | null = null;

  if (phase === "prompt" || phase === "brain_test") {
    // Round start — use voice archetype
    text = voice.roundLabel(roundNumber, roundType);
    subtitle = voice.typeLabel(roundType);
    situationLine = getSituationLine(
      roundNumber,
      totalRounds,
      scores,
      players,
    );
  } else {
    // Mid-round phase — use directives
    const directive = getDirective(phase);
    if (directive) {
      text = directive.text;
      subtitle = directive.subtitle;
    } else {
      text = phase.toUpperCase();
    }
  }

  return (
    <div
      className={`relative flex min-h-[60vh] flex-col items-center justify-center gap-4 ${
        fading ? "animate-interstitial-out" : "animate-interstitial-in"
      } ${!fading ? "interstitial-scan" : ""}`}
    >
      {/* Situation line — above the main text */}
      {isRoundStart && situationLine && !fading && (
        <p
          className="animate-fade-in font-system text-[0.65rem] text-dim tracking-[0.2em] uppercase mb-2"
          style={{ animationDelay: "0.3s" }}
        >
          {situationLine}
        </p>
      )}

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
        <p className="font-system text-[0.65rem] text-dim tracking-[0.15em] lowercase mt-1">
          {subtitle}
        </p>
      )}
    </div>
  );
}
