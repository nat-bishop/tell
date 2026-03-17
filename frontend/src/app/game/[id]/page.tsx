"use client";

import { useEffect, useState, useRef, use } from "react";
import { Stage } from "@/components/Stage";
import { Timer } from "@/components/Timer";
import { PlayerBar } from "@/components/PlayerBar";
import { PhaseInterstitial } from "@/components/PhaseInterstitial";
import { Lobby } from "@/components/Lobby";
import { Prompt } from "@/components/Prompt";
import { QuestionPhase } from "@/components/QuestionPhase";
import { RespondPhase } from "@/components/RespondPhase";
import { NominatePhase } from "@/components/NominatePhase";
import { ReviewPhase } from "@/components/ReviewPhase";
import { WordChainPhase } from "@/components/WordChainPhase";
import { BrainTestPhase } from "@/components/BrainTestPhase";
import { Elimination } from "@/components/Elimination";
import { GameOver } from "@/components/GameOver";
import { Narration } from "@/components/Narration";
import { SystemText } from "@/components/SystemText";
import { joinGame, createGame } from "@/api/actions";
import { useGameStore, type GamePhase } from "@/hooks/useGameStore";
import { useGameEvents } from "@/hooks/useGameEvents";
import { useTimer } from "@/hooks/useTimer";
import { useRouter } from "next/navigation";

function JoinScreen({
  gameId,
  onJoined,
}: {
  gameId: string;
  onJoined: (playerId: string, alias: string) => void;
}) {
  const [name, setName] = useState("");
  const [joining, setJoining] = useState(false);

  const handleJoin = async () => {
    if (!name.trim()) return;
    setJoining(true);
    try {
      const res = await joinGame(gameId, name.trim());
      onJoined(res.player_id, res.alias);
    } catch {
      setJoining(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleJoin();
  };

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-8">
      <h1 className="font-literary text-[3rem] font-normal text-ink">
        tell
      </h1>
      <div className="w-full max-w-xs">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          className="w-full border-b bg-transparent py-2 min-h-[44px] text-center font-literary text-[1.1rem] text-ink outline-none border-rule"
          placeholder="your name"
          autoFocus
        />
      </div>
      <button
        onClick={handleJoin}
        disabled={joining || !name.trim()}
        className="btn-action px-4"
      >
        {joining ? "joining..." : "enter \u2192"}
      </button>
    </div>
  );
}

function EliminatedBanner() {
  const { myAlias } = useGameStore();
  return (
    <div className="mb-6 text-center">
      <p className="font-literary text-[1rem] text-dim">
        {myAlias} was voted off. watching the game unfold.
      </p>
    </div>
  );
}

const INTERSTITIAL_PHASES = new Set<GamePhase>([
  "prompt", "nominate", "question", "respond", "review", "elimination", "chain",
  "brain_test", "brain_test_results",
]);

const ROUND_START_PHASES = new Set<GamePhase>(["prompt", "chain", "brain_test"]);

const FALLBACK_DURATIONS: Partial<Record<GamePhase, number>> = {
  prompt: 45,
  nominate: 15,
  question: 25,
  respond: 30,
  review: 40,
  elimination: 12,
  chain: 8,
  brain_test: 12,
  brain_test_results: 15,
};

function ColdOpen({ playerCount }: { playerCount: number }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const timers = [
      setTimeout(() => setStep(1), 400),
      setTimeout(() => setStep(2), 3000),
    ];
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6">
      {step >= 0 && (
        <p className="animate-fade-in font-system text-[1.2rem] text-ink tracking-[0.2em] uppercase">
          {playerCount} UNITS ASSEMBLED
        </p>
      )}
      {step >= 1 && (
        <p
          className="animate-fade-in font-system text-[0.8rem] text-dim tracking-[0.15em] lowercase"
        >
          some are not what they seem
        </p>
      )}
    </div>
  );
}

function GameContent() {
  const {
    phase, phaseDeadline, phaseDuration, playerId, players,
    roundNumber, roundType, nominatedId, actionStartsAt,
    totalRounds, humansEliminated, aisEliminated, lastEliminationWasHuman,
  } = useGameStore();
  const remaining = useTimer(phaseDeadline);

  const myPlayer = players.find((p) => p.id === playerId);
  const isAlive = myPlayer?.is_alive ?? true;
  const alivePlayers = players.filter((p) => p.is_alive).length;

  // Resolve nominated alias for interstitial subtitles
  const nominatedAlias = nominatedId
    ? players.find((p) => p.id === nominatedId)?.alias ?? null
    : null;

  // Cold open state — show once when game transitions from lobby to first round
  const [showColdOpen, setShowColdOpen] = useState(false);
  const [coldOpenDone, setColdOpenDone] = useState(false);
  const prevPhaseForColdRef = useRef<GamePhase>("lobby");

  useEffect(() => {
    if (
      prevPhaseForColdRef.current === "lobby" &&
      phase !== "lobby" &&
      !coldOpenDone
    ) {
      setShowColdOpen(true);
      const timer = setTimeout(() => {
        setShowColdOpen(false);
        setColdOpenDone(true);
      }, 5500);
      return () => clearTimeout(timer);
    }
    prevPhaseForColdRef.current = phase;
  }, [phase, coldOpenDone]);

  // Phase interstitial state — dismiss timing driven by server's action_starts_at
  const [showInterstitial, setShowInterstitial] = useState(false);
  const [interstitialFading, setInterstitialFading] = useState(false);
  const [isRoundStart, setIsRoundStart] = useState(false);

  useEffect(() => {
    if (!INTERSTITIAL_PHASES.has(phase) || !actionStartsAt || showColdOpen) {
      setShowInterstitial(false);
      setInterstitialFading(false);
      return;
    }

    const holdMs = new Date(actionStartsAt).getTime() - Date.now();
    if (holdMs <= 0) {
      // Already past interstitial (e.g. reconnection) — skip
      setShowInterstitial(false);
      return;
    }

    setIsRoundStart(ROUND_START_PHASES.has(phase));
    setShowInterstitial(true);
    setInterstitialFading(false);

    const fadeMs = 300;
    const t1 = setTimeout(() => setInterstitialFading(true), holdMs);
    const t2 = setTimeout(() => {
      setShowInterstitial(false);
      setInterstitialFading(false);
    }, holdMs + fadeMs);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [phase, actionStartsAt, showColdOpen]);

  const total = phaseDuration ?? FALLBACK_DURATIONS[phase] ?? 0;

  return (
    <>
      <PlayerBar />
      {phase !== "lobby" && phase !== "game_over" && !showColdOpen && !showInterstitial && (
        <Timer remaining={remaining} total={total} />
      )}
      <Narration position="bottom" />
      <Stage>
        {showColdOpen ? (
          <ColdOpen playerCount={players.length} />
        ) : showInterstitial ? (
          <PhaseInterstitial
            phase={phase}
            roundNumber={roundNumber}
            roundType={roundType}
            fading={interstitialFading}
            isRoundStart={isRoundStart}
            spectator={!isAlive}
            nominatedAlias={nominatedAlias}
            totalRounds={totalRounds}
            alivePlayers={alivePlayers}
            humansEliminated={humansEliminated}
            aisEliminated={aisEliminated}
            lastEliminationWasHuman={lastEliminationWasHuman}
          />
        ) : (
          <>
            {!isAlive && phase !== "game_over" && phase !== "elimination" && (
              <EliminatedBanner />
            )}
            {phase === "lobby" && <Lobby />}
            {phase === "prompt" && <Prompt readOnly={!isAlive} />}
            {phase === "nominate" && <NominatePhase spectator={!isAlive} />}
            {phase === "question" && <QuestionPhase spectator={!isAlive} />}
            {phase === "respond" && <RespondPhase spectator={!isAlive} />}
            {phase === "chain" && <WordChainPhase spectator={!isAlive} />}
            {(phase === "brain_test" || phase === "brain_test_results") && (
              <BrainTestPhase spectator={!isAlive} />
            )}
            {phase === "review" && <ReviewPhase spectator={!isAlive} />}
            {phase === "elimination" && <Elimination />}
            {phase === "game_over" && <GameOver />}
          </>
        )}
      </Stage>
    </>
  );
}

export default function GamePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const { setIdentity, playerId } = useGameStore();
  const [joined, setJoined] = useState(false);

  useEffect(() => {
    if (id === "new") {
      createGame().then((res) => router.replace(`/game/${res.game_id}`));
    }
  }, [id, router]);

  useEffect(() => {
    if (id === "new") return;
    const stored = sessionStorage.getItem(`tell-${id}`);
    if (stored) {
      try {
        const { playerId: pid, alias } = JSON.parse(stored);
        setIdentity(id, pid, alias);
        setJoined(true);
      } catch {
        sessionStorage.removeItem(`tell-${id}`);
      }
    }
  }, [id, setIdentity]);

  useGameEvents(joined ? id : "", joined ? playerId || "" : "");

  if (id === "new") {
    return (
      <Stage>
        <div className="flex min-h-[60vh] items-center justify-center">
          <SystemText>creating game...</SystemText>
        </div>
      </Stage>
    );
  }

  if (!joined) {
    return (
      <Stage>
        <JoinScreen
          gameId={id}
          onJoined={(pid, alias) => {
            sessionStorage.setItem(
              `tell-${id}`,
              JSON.stringify({ playerId: pid, alias }),
            );
            setIdentity(id, pid, alias);
            setJoined(true);
          }}
        />
      </Stage>
    );
  }

  return <GameContent />;
}
