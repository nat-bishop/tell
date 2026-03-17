"use client";

import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import {
  useGameStore,
  type PlayerInfo,
  type ChainRoundData,
} from "@/hooks/useGameStore";
import { castVote, castComedyVote } from "@/api/actions";
import { AnswerCard } from "./AnswerCard";
import { SystemText } from "./SystemText";

function shuffleArray<T>(arr: T[]): T[] {
  const shuffled = [...arr];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

function PlayerCard({
  player,
  voted,
  canVote,
  onToggle,
  disabled,
}: {
  player: PlayerInfo;
  voted: boolean;
  canVote: boolean;
  onToggle: () => void;
  disabled: boolean;
}) {
  const answer = useGameStore((s) => s.answers[player.id]);
  const questions = useGameStore((s) => s.questions);
  const roundType = useGameStore((s) => s.roundType);
  const synthesis = useGameStore((s) => s.synthesis);
  const nominatedId = useGameStore((s) => s.nominatedId);

  const myQuestion = questions.find((q) => q.target_id === player.id);

  const isNominee = roundType === "interrogation" && player.id === nominatedId;
  const questionText = isNominee ? synthesis : myQuestion?.question;
  const responseText = myQuestion?.response;

  return (
    <AnswerCard
      alias={player.alias}
      answer={answer}
      highlighted={voted}
      showVotedLabel={voted}
      as={canVote ? "button" : "div"}
      onClick={onToggle}
      disabled={disabled}
    >
      {questionText && (
        <div className="mt-3 pt-3 border-t border-rule">
          <div className="font-system text-[0.65rem] text-cold tracking-wider uppercase">
            {isNominee ? "synthesis" : "question received"}
          </div>
          <div className="mt-1 font-literary text-[0.95rem] italic leading-[1.5] text-ink">
            {questionText}
          </div>
          {responseText && (
            <>
              <div className="mt-2 font-system text-[0.65rem] text-cold tracking-wider uppercase">
                response
              </div>
              <div className="mt-1 font-literary text-[0.95rem] leading-[1.5] text-ink">
                {responseText}
              </div>
            </>
          )}
        </div>
      )}
    </AnswerCard>
  );
}

function WordChainCard({
  player,
  chainRounds,
  voted,
  canVote,
  onToggle,
  disabled,
}: {
  player: PlayerInfo;
  chainRounds: ChainRoundData[];
  voted: boolean;
  canVote: boolean;
  onToggle: () => void;
  disabled: boolean;
}) {
  return (
    <AnswerCard
      alias={player.alias}
      highlighted={voted}
      showVotedLabel={voted}
      as={canVote ? "button" : "div"}
      onClick={onToggle}
      disabled={disabled}
    >
      <div className="flex flex-col gap-1">
        {chainRounds.map((cr, i) => {
          const response = cr.responses[player.id];
          const wasChosen = cr.chosen_player_id === player.id;
          return (
            <div key={i} className="flex items-baseline gap-2 text-[0.85rem]">
              <span className="font-system text-[0.65rem] text-cold shrink-0 tracking-wide">
                {cr.seed} &rarr;
              </span>
              <span
                className={`font-literary ${
                  wasChosen ? "text-warm" : "text-ink"
                }`}
              >
                {response || "\u2014"}
              </span>
            </div>
          );
        })}
      </div>
    </AnswerCard>
  );
}

export function ReviewPhase({ spectator = false }: { spectator?: boolean }) {
  const {
    gameId,
    playerId,
    players,
    voteCount,
    voteTotalCount,
    roundType,
    promptText,
    chainRounds,
  } = useGameStore();
  const alivePlayers = players.filter((p) => p.is_alive);
  const aliveCount = alivePlayers.length;
  const maxVotes = Math.min(3, Math.max(1, aliveCount - 1));

  // Randomized reveal order — shuffled once on mount
  const revealOrder = useMemo(() => shuffleArray(alivePlayers), [aliveCount]);

  // Spotlight reveal state
  const [revealedCount, setRevealedCount] = useState(0);
  const revealInterval = useMemo(
    () => Math.max(1000, 1500 - (aliveCount - 5) * 100),
    [aliveCount],
  );

  useEffect(() => {
    if (revealedCount >= aliveCount) return;

    // Reveal first card immediately
    if (revealedCount === 0) {
      setRevealedCount(1);
      return;
    }

    const timer = setTimeout(() => setRevealedCount((c) => c + 1), revealInterval);

    return () => clearTimeout(timer);
  }, [revealedCount, aliveCount, revealInterval]);

  const allRevealed = revealedCount >= aliveCount;

  // Build a set of revealed player IDs for quick lookup
  const revealedIds = useMemo(() => {
    const ids = new Set<string>();
    for (let i = 0; i < revealedCount && i < revealOrder.length; i++) {
      ids.add(revealOrder[i].id);
    }
    return ids;
  }, [revealedCount, revealOrder]);

  const [selected, setSelected] = useState<string[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sendVotes = useCallback(
    (targets: string[]) => {
      if (!gameId || !playerId) return;
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        castVote(gameId, playerId, targets).catch(() => {});
      }, 500);
    },
    [gameId, playerId],
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const toggleVote = (pid: string) => {
    if (!allRevealed) return;
    const prev = selected;
    let next: string[];
    if (prev.includes(pid)) {
      next = prev.filter((id) => id !== pid);
    } else if (prev.length < maxVotes) {
      next = [...prev, pid];
    } else {
      return;
    }
    setSelected(next);
    sendVotes(next);
    useGameStore.setState({ myVotes: next });
  };

  // Comedy vote
  const [comedyVote, setComedyVote] = useState<string | null>(null);

  const toggleComedyVote = (pid: string) => {
    if (!allRevealed || !gameId || !playerId) return;
    if (comedyVote === pid) return; // Already selected — no server "unvote"
    setComedyVote(pid);
    castComedyVote(gameId, playerId, pid).catch(() => {});
    useGameStore.setState({ myComedyVote: pid });
  };

  const isWordChain = roundType === "word_chain";
  const isTask = roundType === "task";

  return (
    <div className="flex flex-col gap-6 pt-4">
      {isTask && promptText && (
        <p className="text-center font-literary text-[1rem] italic leading-[1.6] text-dim">
          the task was: {promptText}
        </p>
      )}

      {!isTask && !isWordChain && promptText && (
        <p className="text-center font-literary text-[1rem] italic leading-[1.6] text-dim">
          {promptText}
        </p>
      )}

      {isWordChain && chainRounds.length > 0 && (
        <p className="text-center font-system text-[0.85rem] text-dim tracking-wide">
          {chainRounds.map((cr) => cr.seed).join(" \u2192 ")}
        </p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {alivePlayers.map((p) => {
          const isRevealed = revealedIds.has(p.id);
          if (!isRevealed) {
            return (
              <div key={p.id} className="card-placeholder p-5 h-full min-h-[100px]" />
            );
          }
          return isWordChain ? (
            <WordChainCard
              key={p.id}
              player={p}
              chainRounds={chainRounds}
              voted={selected.includes(p.id)}
              canVote={!spectator && p.id !== playerId}
              onToggle={() => toggleVote(p.id)}
              disabled={!allRevealed}
            />
          ) : (
            <PlayerCard
              key={p.id}
              player={p}
              voted={selected.includes(p.id)}
              canVote={!spectator && p.id !== playerId}
              onToggle={() => toggleVote(p.id)}
              disabled={!allRevealed}
            />
          );
        })}
      </div>

      {allRevealed && (
        <>
          {!spectator ? (
            <div className="animate-fade-in flex flex-col gap-3">
              <p className="animate-reveal-expand text-center font-system text-[0.9rem] text-ink tracking-[0.15em] uppercase">
                IDENTIFY HUMAN
              </p>
              <div className="flex items-center justify-between">
                {/* Vote dots */}
                <div className="flex items-center gap-2">
                  {Array.from({ length: maxVotes }).map((_, i) => (
                    <span
                      key={i}
                      className={`inline-block w-2.5 h-2.5 rounded-full transition-all duration-200 ${
                        i < selected.length
                          ? "scale-110"
                          : "border border-rule"
                      }`}
                      style={i < selected.length ? {
                        backgroundColor: 'var(--warm)',
                        boxShadow: '0 0 8px var(--glow)',
                      } : undefined}
                    />
                  ))}
                </div>
                <SystemText>
                  {voteCount} of {voteTotalCount} voted
                </SystemText>
              </div>

              {/* Comedy vote */}
              <div className="flex items-center gap-3 mt-2">
                <span className="font-system text-[0.65rem] text-dim tracking-wider uppercase shrink-0">
                  funniest
                </span>
                <div className="flex flex-wrap gap-2">
                  {alivePlayers.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => toggleComedyVote(p.id)}
                      className={`font-system text-[0.6rem] tracking-wider uppercase px-2 py-0.5 rounded transition-all ${
                        comedyVote === p.id
                          ? "bg-raised text-ink border border-dim"
                          : "text-dim border border-rule hover:border-dim"
                      }`}
                    >
                      {p.alias}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="animate-fade-in">
              <SystemText>voting in progress</SystemText>
            </div>
          )}
        </>
      )}
    </div>
  );
}
