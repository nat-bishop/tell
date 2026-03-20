"use client";

import { useGameStore, type PlayerInfo } from "@/hooks/useGameStore";
import { useFacilityContext } from "@/facility/FacilityProvider";
import { Panel } from "@/facility/Panel";

// ─── Robot Voice Archetypes ───

type VoiceId = "clinical" | "bureaucratic" | "military" | "malfunctioning" | "friendly";

interface Voice {
  roundLabel: (n: number, type: string | null) => string;
  typeLabel: (type: string | null) => string;
}

const VOICES: Record<VoiceId, Voice> = {
  clinical: {
    roundLabel: (n, type) => {
      if (type === "wager") return `TEST SEQUENCE ${n} / ESTIMATION PROTOCOL`;
      if (type === "brain_test") return `TEST SEQUENCE ${n} / RAPID ASSESSMENT`;
      if (type === "signal") return `TEST SEQUENCE ${n} / SIGNAL INTERCEPT`;
      return `TEST SEQUENCE ${n} / DETECTION SCAN`;
    },
    typeLabel: (type) => {
      if (type === "wager") return "PLACE YOUR BETS";
      if (type === "brain_test") return "QUICK DRAW";
      if (type === "signal") return "DECODE THE SIGNAL";
      return "IDENTIFY THE HUMAN";
    },
  },
  bureaucratic: {
    roundLabel: (n, type) => {
      if (type === "wager") return `FORM 12C: NUMERICAL ASSESSMENT ${n}`;
      if (type === "brain_test") return `PLEASE PROCEED TO ASSESSMENT ${n}`;
      if (type === "signal") return `ASSESSMENT ${n} / SIGNAL DECODE`;
      return `ASSESSMENT ${n} / VERIFICATION TASK`;
    },
    typeLabel: (type) => {
      if (type === "wager") return "ESTIMATE AND WAGER";
      if (type === "brain_test") return "FORM 9D: RAPID RESPONSE";
      if (type === "signal") return "FORM 12C: SIGNAL ANALYSIS";
      return "FORM 7B: DETECTION PROTOCOL";
    },
  },
  military: {
    roundLabel: (n, type) => {
      if (type === "wager") return `OPERATION ${n} / FIELD ESTIMATION`;
      if (type === "brain_test") return `OPERATION ${n} / SNAP JUDGMENT`;
      if (type === "signal") return `OPERATION ${n} / INTERCEPT`;
      return `OPERATION ${n} / SWEEP SCAN`;
    },
    typeLabel: (type) => {
      if (type === "wager") return "CONFIDENCE CHECK";
      if (type === "brain_test") return "RAPID FIRE";
      if (type === "signal") return "DECODE TRANSMISSION";
      return "WHO DOESN'T BELONG?";
    },
  },
  malfunctioning: {
    roundLabel: (n, type) => {
      if (type === "wager") return `R-R-ROUND ${n} / N-NUMBER... LINE`;
      if (type === "brain_test") return `R-R-ROUND ${n} / Q-QUICK... DRAW`;
      if (type === "signal") return `R-R-ROUND ${n} / S-SIGNAL [garbled]`;
      return `R-R-ROUND ${n} / SC-SCAN [retry]`;
    },
    typeLabel: (type) => {
      if (type === "wager") return "GUESS\u2014 GUESS THE NUMBER. [overflow]";
      if (type === "brain_test") return "PICK\u2014 PICK AN OPTION. [retry]";
      if (type === "signal") return "DECODE THE\u2014 THE SIGNAL. [static]";
      return "FIND THE\u2014 THE HUMAN. [buffer overflow]";
    },
  },
  friendly: {
    roundLabel: (n, type) => {
      if (type === "wager") return `round ${n}! estimation time :)`;
      if (type === "brain_test") return `round ${n}! quick quiz time :)`;
      if (type === "signal") return `round ${n}! signal time :)`;
      return `round ${n}! detection time :)`;
    },
    typeLabel: (type) => {
      if (type === "wager") return "guess and bet!";
      if (type === "brain_test") return "quick draw";
      if (type === "signal") return "decode the signal";
      return "who sounds most human?";
    },
  },
};

const VOICE_ORDER: VoiceId[] = ["clinical", "bureaucratic", "military", "malfunctioning", "friendly"];

function getVoice(roundNumber: number): Voice {
  const idx = (roundNumber - 1) % VOICE_ORDER.length;
  return VOICES[VOICE_ORDER[idx]];
}

// ─── Step Directives ───

interface Directive {
  text: string;
  subtitle: string;
}

function getDirective(component: string | null, roundType: string | null): Directive | null {
  if (component === "vote") {
    return {
      text: "DETECTION SCAN",
      subtitle: "who sounds most human?",
    };
  }
  if (component === "signal_guess") {
    return {
      text: "SIGNAL INTERCEPT",
      subtitle: "decode the transmission",
    };
  }
  if (component === "vote_results" || component === "brain_test_results" ||
      component === "wager_results" || component === "signal_results") {
    return {
      text: "RESULTS INCOMING",
      subtitle: "scan complete",
    };
  }
  return null;
}

// ─── Situation Lines ───

function getSituationLine(
  roundNumber: number,
  totalRounds: number,
  scores?: Record<string, number>,
  players?: PlayerInfo[],
): string | null {
  if (totalRounds > 0 && roundNumber >= totalRounds) {
    return "final round";
  }

  if (roundNumber <= 1) return null;

  if (totalRounds > 0) {
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

export function TransitionOverlay() {
  const { transitionState } = useFacilityContext();
  if (transitionState !== "reconfigure") return null;
  return <TransitionOverlayContent />;
}

function TransitionOverlayContent() {
  const roundNumber = useGameStore((s) => s.roundNumber);
  const roundType = useGameStore((s) => s.roundType);
  const component = useGameStore((s) => s.component);
  const stepName = useGameStore((s) => s.stepName);
  const totalRounds = useGameStore((s) => s.totalRounds);
  const scores = useGameStore((s) => s.scores);
  const players = useGameStore((s) => s.players);

  // Round start = first step of a round (compose steps, challenge_0, guess_0)
  const isRoundStart =
    stepName === "compose" ||
    stepName === "signal_compose" ||
    stepName === "challenge_0" ||
    stepName === "guess_0";

  const voice = getVoice(roundNumber);

  let text: string;
  let subtitle: string | undefined;
  let situationLine: string | null = null;

  if (isRoundStart) {
    text = voice.roundLabel(roundNumber, roundType);
    subtitle = voice.typeLabel(roundType);
    situationLine = getSituationLine(roundNumber, totalRounds, scores, players);
  } else {
    const directive = getDirective(component, roundType);
    if (directive) {
      text = directive.text;
      subtitle = directive.subtitle;
    } else {
      text = (stepName ?? "").toUpperCase();
    }
  }

  return (
    <Panel zone="wall-display">
      <div className="animate-interstitial-in interstitial-scan flex h-full flex-col items-center justify-center gap-4">
        {isRoundStart && situationLine && (
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

        {isRoundStart && subtitle && (
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
    </Panel>
  );
}
