"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useGameStore, type PlayerInfo } from "@/hooks/useGameStore";
import { castVote } from "@/api/actions";
import { SystemText } from "./SystemText";

function PlayerCard({
  player,
  voted,
  canVote,
  onToggle,
  delay,
}: {
  player: PlayerInfo;
  voted: boolean;
  canVote: boolean;
  onToggle: () => void;
  delay: number;
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

  const content = (
    <>
      <div
        className={`font-literary-sc text-[0.85rem] tracking-[0.08em] ${
          voted ? "text-warm" : "text-ink"
        }`}
      >
        {player.alias}
      </div>
      {answer && (
        <div className="mt-1 font-literary text-[1rem] leading-[1.5] text-ink">
          {answer}
        </div>
      )}
      {questionText && (
        <>
          <div className="mt-3 font-system text-[0.7rem] text-dim">
            {isNominee ? "synthesis" : "question received"}
          </div>
          <div className="mt-0.5 font-literary text-[0.95rem] italic leading-[1.5] text-ink">
            {questionText}
          </div>
        </>
      )}
      {responseText && (
        <>
          <div className="mt-2 font-system text-[0.7rem] text-dim">
            response
          </div>
          <div className="mt-0.5 font-literary text-[0.95rem] leading-[1.5] text-ink">
            {responseText}
          </div>
        </>
      )}
    </>
  );

  const baseClass = `border p-4 animate-fade-in transition-colors duration-150 ${
    !voted ? "border-rule" : ""
  }`;
  const style = {
    animationDelay: `${delay}ms`,
    borderColor: voted ? "var(--warm)" : undefined,
  };

  return canVote ? (
    <button
      onClick={onToggle}
      className={`${baseClass} cursor-pointer text-left w-full`}
      style={style}
    >
      {content}
    </button>
  ) : (
    <div className={baseClass} style={style}>
      {content}
    </div>
  );
}

export function ReviewPhase({ spectator = false }: { spectator?: boolean }) {
  const { gameId, playerId, players, voteCount, voteTotalCount } =
    useGameStore();
  const alivePlayers = players.filter((p) => p.is_alive);
  const aliveCount = alivePlayers.length;
  const maxVotes = Math.min(3, Math.max(1, aliveCount - 1));

  const [selected, setSelected] = useState<string[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sendVotes = useCallback(
    (targets: string[]) => {
      if (!gameId || !playerId) return;
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        castVote(gameId, playerId, targets);
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
    setSelected((prev) => {
      let next: string[];
      if (prev.includes(pid)) {
        next = prev.filter((id) => id !== pid);
      } else if (prev.length < maxVotes) {
        next = [...prev, pid];
      } else {
        return prev;
      }
      sendVotes(next);
      useGameStore.setState({ myVotes: next });
      return next;
    });
  };

  return (
    <div className="flex flex-col gap-6 pt-4">
      <SystemText>{spectator ? "review" : "who is human?"}</SystemText>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {alivePlayers.map((p, i) => (
          <PlayerCard
            key={p.id}
            player={p}
            voted={selected.includes(p.id)}
            canVote={!spectator && p.id !== playerId}
            onToggle={() => toggleVote(p.id)}
            delay={i * 60}
          />
        ))}
      </div>

      {!spectator ? (
        <div className="flex items-center justify-between">
          <SystemText>
            {selected.length} of {maxVotes} votes cast
          </SystemText>
          <SystemText>
            {voteCount} of {voteTotalCount} voted
          </SystemText>
        </div>
      ) : (
        <SystemText>voting in progress</SystemText>
      )}
    </div>
  );
}
