"use client";

import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import {
  useGameStore,
  type PlayerInfo,
} from "@/hooks/useGameStore";
import { castVote, castComedyVote, sendDiscussionMessage } from "@/api/actions";
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

type SubPhase = "reveal" | "discuss" | "vote";

function useSubPhase(): SubPhase {
  const discussStartsAt = useGameStore((s) => s.discussStartsAt);
  const voteStartsAt = useGameStore((s) => s.voteStartsAt);
  const [subPhase, setSubPhase] = useState<SubPhase>("reveal");

  useEffect(() => {
    if (!discussStartsAt || !voteStartsAt) {
      setSubPhase("reveal");
      return;
    }

    const check = () => {
      const now = Date.now();
      const discussTime = new Date(discussStartsAt).getTime();
      const voteTime = new Date(voteStartsAt).getTime();

      if (now >= voteTime) {
        setSubPhase("vote");
      } else if (now >= discussTime) {
        setSubPhase("discuss");
      } else {
        setSubPhase("reveal");
      }
    };

    check();
    const interval = setInterval(check, 500);
    return () => clearInterval(interval);
  }, [discussStartsAt, voteStartsAt]);

  return subPhase;
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

function DiscussionChat({ spectator = false, frozen = false }: { spectator?: boolean; frozen?: boolean }) {
  const gameId = useGameStore((s) => s.gameId);
  const playerId = useGameStore((s) => s.playerId);
  const messages = useGameStore((s) => s.discussionMessages);
  const myCount = useGameStore((s) => s.myDiscussionCount);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  const handleSend = useCallback(async () => {
    if (!gameId || !playerId || !input.trim() || myCount >= 3) return;
    const msg = input.trim().slice(0, 120);
    setInput("");
    try {
      await sendDiscussionMessage(gameId, playerId, msg);
    } catch {
      // Silently handle
    }
  }, [gameId, playerId, input, myCount]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = !spectator && !frozen && myCount < 3;

  return (
    <div className="animate-fade-in flex flex-col gap-2">
      <p className="font-system text-[0.65rem] text-cold tracking-[0.2em] uppercase text-center">
        discuss
      </p>

      <div
        ref={scrollRef}
        className="flex flex-col gap-1.5 max-h-[180px] overflow-y-auto px-1"
      >
        {messages.length === 0 && (
          <p className="font-system text-[0.65rem] text-dim text-center py-2">
            ...
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className="flex gap-2 items-baseline">
            <span className="font-system text-[0.6rem] text-dim uppercase tracking-wider shrink-0">
              {m.sender_alias}
            </span>
            <span className="font-literary text-[0.85rem] text-ink">
              {m.message}
            </span>
          </div>
        ))}
      </div>

      {canSend ? (
        <div className="flex gap-2 items-center">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 border-b bg-transparent py-1.5 min-h-[36px] font-literary text-[0.85rem] text-ink outline-none border-rule"
            placeholder={myCount >= 3 ? "" : "say something..."}
            maxLength={120}
            disabled={myCount >= 3}
            autoFocus
          />
          <span className="font-system text-[0.55rem] text-dim">
            {3 - myCount}
          </span>
        </div>
      ) : spectator ? (
        <SystemText>discussion in progress</SystemText>
      ) : (
        <p className="font-system text-[0.55rem] text-dim text-center">
          message limit reached
        </p>
      )}
    </div>
  );
}

function ScanResults() {
  const scanResults = useGameStore((s) => s.scanResults);
  const activeAbilityHolderAlias = useGameStore((s) => s.activeAbilityHolderAlias);
  const activeAbilityType = useGameStore((s) => s.activeAbilityType);

  if (!scanResults || activeAbilityType !== "partial_scan") return null;

  return (
    <div className="animate-fade-in card p-3 border-cold/30">
      <p className="font-system text-[0.6rem] text-cold tracking-[0.15em] uppercase mb-2">
        partial scan &mdash; {activeAbilityHolderAlias}
      </p>
      <div className="flex flex-col gap-1">
        {scanResults.map((r, i) => (
          <div key={i} className="flex gap-2 items-baseline">
            <span className="font-system text-[0.6rem] text-dim uppercase tracking-wider">
              {r.alias}
            </span>
            <span className={`font-literary text-[0.8rem] ${
              r.claimed_role === "human" ? "text-warm" : "text-cold"
            }`}>
              {r.claimed_role}
            </span>
          </div>
        ))}
      </div>
      <p className="font-system text-[0.5rem] text-dim mt-1.5 italic">
        one is verified. one is noise.
      </p>
    </div>
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
  } = useGameStore();
  const subPhase = useSubPhase();
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

  const isVotePhase = subPhase === "vote";

  const sendVotes = useCallback(
    (targets: string[]) => {
      if (!gameId || !playerId) return;
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        const deadline = useGameStore.getState().phaseDeadline;
        if (deadline && Date.now() > new Date(deadline).getTime()) return;
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

  useEffect(() => {
    if (!isVotePhase && debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
  }, [isVotePhase]);

  const toggleVote = (pid: string) => {
    if (!isVotePhase) return;
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
    if (!isVotePhase || !gameId || !playerId) return;
    if (comedyVote === pid) return;
    const deadline = useGameStore.getState().phaseDeadline;
    if (deadline && Date.now() > new Date(deadline).getTime()) return;
    setComedyVote(pid);
    castComedyVote(gameId, playerId, pid).catch(() => {});
    useGameStore.setState({ myComedyVote: pid });
  };

  const isTask = roundType === "task";

  return (
    <div className="flex flex-col gap-6 pt-4">
      {isTask && promptText && (
        <p className="text-center font-literary text-[1rem] italic leading-[1.6] text-dim">
          the task was: {promptText}
        </p>
      )}

      {!isTask && promptText && (
        <p className="text-center font-literary text-[1rem] italic leading-[1.6] text-dim">
          {promptText}
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
          return (
            <PlayerCard
              key={p.id}
              player={p}
              voted={selected.includes(p.id)}
              canVote={isVotePhase && !spectator && p.id !== playerId}
              onToggle={() => toggleVote(p.id)}
              disabled={!isVotePhase}
            />
          );
        })}
      </div>

      {/* DISCUSS / VOTE sub-phases — chat + scan shown for both, frozen during vote */}
      {allRevealed && (subPhase === "discuss" || subPhase === "vote") && (
        <div className={subPhase === "vote" ? "opacity-40 pointer-events-none" : "flex flex-col gap-4"}>
          {subPhase === "discuss" && <ScanResults />}
          <DiscussionChat spectator={spectator} frozen={subPhase === "vote"} />
        </div>
      )}

      {allRevealed && subPhase === "vote" && (
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
