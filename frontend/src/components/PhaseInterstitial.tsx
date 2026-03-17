import type { GamePhase } from "@/hooks/useGameStore";

interface PhaseInterstitialProps {
  phase: GamePhase;
  roundNumber: number;
  roundType: string | null;
  fading: boolean;
  isRoundStart?: boolean;
  spectator?: boolean;
  nominatedAlias?: string | null;
  // Narrative context
  totalRounds?: number;
  alivePlayers?: number;
  humansEliminated?: number;
  aisEliminated?: number;
  lastEliminationWasHuman?: boolean | null;
}

// ─── Robot Voice Archetypes ───

type VoiceId = "clinical" | "bureaucratic" | "military" | "malfunctioning" | "friendly";

interface Voice {
  roundLabel: (n: number, type: string | null) => string;
  typeLabel: (type: string | null, phase: GamePhase) => string;
}

const VOICES: Record<VoiceId, Voice> = {
  clinical: {
    roundLabel: (n, type) => {
      if (type === "chain") return `TEST SEQUENCE ${n} / ASSOCIATION MATRIX`;
      if (type === "interrogation") return `TEST SEQUENCE ${n} / BEHAVIORAL PROBE`;
      return `TEST SEQUENCE ${n} / PERFORMANCE EVAL`;
    },
    typeLabel: (type, phase) => {
      if (phase === "chain") return "WORD ASSOCIATION";
      if (type === "interrogation") return "INTERROGATION";
      return "TASK";
    },
  },
  bureaucratic: {
    roundLabel: (n, type) => {
      if (type === "chain") return `PLEASE PROCEED TO ASSESSMENT ${n}`;
      if (type === "interrogation") return `ASSESSMENT ${n} / COMPLIANCE REVIEW`;
      return `ASSESSMENT ${n} / STANDARD FORM`;
    },
    typeLabel: (type, phase) => {
      if (phase === "chain") return "FORM 12C: WORD ASSOCIATION";
      if (type === "interrogation") return "FORM 7B: BEHAVIORAL INTERVIEW";
      return "FORM 3A: WRITTEN RESPONSE";
    },
  },
  military: {
    roundLabel: (n, type) => {
      if (type === "chain") return `OPERATION ${n} / PATTERN RECON`;
      if (type === "interrogation") return `OPERATION ${n} / THREAT ASSESSMENT`;
      return `OPERATION ${n} / FIELD TEST`;
    },
    typeLabel: (type, phase) => {
      if (phase === "chain") return "ASSOCIATION SWEEP";
      if (type === "interrogation") return "TARGET INTERROGATION";
      return "MISSION BRIEFING";
    },
  },
  malfunctioning: {
    roundLabel: (n, type) => {
      if (type === "chain") return `R-R-ROUND ${n} / WORD... WORD CHAIN`;
      if (type === "interrogation") return `R-R-ROUND ${n} / INTER... INTERROGATION`;
      return `R-R-ROUND ${n} / T-TASK [retry]`;
    },
    typeLabel: (type, phase) => {
      if (phase === "chain") return "WORD— WORD ASSOCIATION";
      if (type === "interrogation") return "SELECT— SELECT TARGET. [retry]";
      return "RESPOND. [buffer overflow]";
    },
  },
  friendly: {
    roundLabel: (n, type) => {
      if (type === "chain") return `round ${n}! word game time :)`;
      if (type === "interrogation") return `round ${n}! time to chat :)`;
      return `round ${n}! here we go :)`;
    },
    typeLabel: (type, phase) => {
      if (phase === "chain") return "word association";
      if (type === "interrogation") return "get to know each other";
      return "creative writing";
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
  spectatorText?: string;
  spectatorSubtitle?: string;
}

function getDirective(
  phase: GamePhase,
  nominatedAlias?: string | null,
): Directive | null {
  switch (phase) {
    case "nominate":
      return {
        text: "SELECT TARGET",
        subtitle: "choose who faces the group",
        spectatorText: "TARGET SELECTION",
        spectatorSubtitle: "a target is chosen",
      };
    case "question":
      return {
        text: "INTERROGATION",
        subtitle: nominatedAlias
          ? `question ${nominatedAlias}`
          : "question the suspect",
        spectatorText: "INTERROGATION",
        spectatorSubtitle: nominatedAlias
          ? `${nominatedAlias} faces the group`
          : "the suspect is questioned",
      };
    case "respond":
      return {
        text: "DEFEND YOURSELF",
        subtitle: "the group awaits your answer",
        spectatorText: "DEFENSE",
        spectatorSubtitle: nominatedAlias
          ? `${nominatedAlias} faces the group`
          : "the suspect responds",
      };
    case "review":
      return {
        text: "IDENTIFY HUMAN",
        subtitle: "cast your suspicions",
        spectatorText: "ANALYSIS",
        spectatorSubtitle: "the group votes",
      };
    case "elimination":
      return {
        text: "VOTE RESULT",
        subtitle: "the group has spoken",
        spectatorText: "VOTE RESULT",
        spectatorSubtitle: "the group has spoken",
      };
    default:
      return null;
  }
}

// ─── Situation Lines ───

function getSituationLine(
  roundNumber: number,
  alivePlayers: number,
  humansEliminated: number,
  aisEliminated: number,
  lastEliminationWasHuman: boolean | null,
  totalRounds: number,
): string | null {
  // Final round
  if (totalRounds > 0 && roundNumber >= totalRounds) {
    return "final round";
  }

  // Round 1 — clean start
  if (roundNumber <= 1) return null;

  // After eliminations
  if (humansEliminated > 0 && aisEliminated === 0) {
    return "the machines grow confident";
  }
  if (aisEliminated > 0 && humansEliminated === 0) {
    return aisEliminated === 1 ? "one impostor found" : `${aisEliminated} impostors found`;
  }
  if (aisEliminated > 0 && humansEliminated > 0) {
    return `${alivePlayers} units remain`;
  }

  // Generic after first elimination
  if (lastEliminationWasHuman !== null) {
    return `${alivePlayers} units remain`;
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
  spectator = false,
  nominatedAlias,
  totalRounds = 0,
  alivePlayers = 0,
  humansEliminated = 0,
  aisEliminated = 0,
  lastEliminationWasHuman = null,
}: PhaseInterstitialProps) {
  const voice = getVoice(roundNumber);
  let text: string;
  let subtitle: string | undefined;
  let situationLine: string | null = null;

  if (phase === "prompt" || phase === "chain") {
    // Round start — use voice archetype
    text = voice.roundLabel(roundNumber, phase === "chain" ? "chain" : roundType);
    subtitle = voice.typeLabel(roundType, phase);
    situationLine = getSituationLine(
      roundNumber,
      alivePlayers,
      humansEliminated,
      aisEliminated,
      lastEliminationWasHuman,
      totalRounds,
    );
  } else {
    // Mid-round phase — use directives
    const directive = getDirective(phase, nominatedAlias);
    if (directive) {
      text = spectator && directive.spectatorText ? directive.spectatorText : directive.text;
      subtitle = spectator && directive.spectatorSubtitle ? directive.spectatorSubtitle : directive.subtitle;
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
