"use client";

import { useState, useRef, useEffect } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { startGame, type GameConfig } from "@/api/actions";
import { Panel } from "@/facility/Panel";
import { SystemText } from "@/components/SystemText";

const ROUND_TYPES = [
  { value: "task", label: "task" },
  { value: "brain_test", label: "brain test" },
  { value: "wager", label: "wager" },
  { value: "signal", label: "signal" },
] as const;

export function FacilityLobby() {
  const { gameId, playerId, players, isHost } = useGameStore();
  const playerCount = players.length;
  const canStart = playerCount >= 1;

  const [copied, setCopied] = useState(false);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [configOpen, setConfigOpen] = useState(false);
  const [roundSequence, setRoundSequence] = useState<string[]>([]);
  const [aiCount, setAiCount] = useState(6);
  const [timersDisabled, setTimersDisabled] = useState(false);

  useEffect(() => {
    return () => clearTimeout(copyTimerRef.current);
  }, []);

  const handleStart = async () => {
    if (!gameId || !playerId) return;
    const config: GameConfig = {};
    if (roundSequence.length > 0) config.round_sequence = roundSequence;
    if (aiCount !== 6) config.ai_count = aiCount;
    if (timersDisabled) config.timers_disabled = timersDisabled;
    await startGame(gameId, playerId, config);
  };

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      clearTimeout(copyTimerRef.current);
      copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: silent
    }
  };

  const addRound = (type: string) => {
    setRoundSequence((prev) => [...prev, type]);
  };

  const removeRound = (index: number) => {
    setRoundSequence((prev) => prev.filter((_, i) => i !== index));
  };

  const roundLabel = (value: string) =>
    ROUND_TYPES.find((rt) => rt.value === value)?.label ?? value;

  return (
    <>
      {/* Wall display — title + player list */}
      <Panel zone="wall-display">
        <div className="flex flex-col items-center gap-6 h-full justify-center">
          <h1
            className="font-system text-[2.5rem] font-normal text-ink tracking-[0.15em] uppercase animate-glitch"
            style={{ textShadow: "0 0 40px var(--cold-glow)" }}
          >
            tell
          </h1>

          <div className="flex flex-col items-center gap-2">
            {players.map((p) => (
              <div key={p.id} className="flex items-center gap-2 animate-fade-in">
                <span
                  className={`inline-block w-2 h-2 rounded-full ${p.is_connected ? "bg-cold" : "bg-rule"}`}
                  style={p.is_connected ? { boxShadow: "0 0 6px var(--cold)" } : undefined}
                />
                <span
                  className={`font-system text-[0.85rem] tracking-[0.1em] uppercase ${p.is_connected ? "text-ink" : "text-dim"}`}
                >
                  {p.alias}
                </span>
              </div>
            ))}
          </div>

          <div className="synthesizing-dots font-system text-[0.75rem] text-cold tracking-wide">
            {playerCount} connected
          </div>
        </div>
      </Panel>

      {/* Desk terminal — host controls + copy link */}
      <Panel zone="desk-terminal">
        <div className="flex flex-col items-center gap-4 h-full justify-center">
          {isHost && (
            <>
              <SystemText>{aiCount} AI will join on start</SystemText>

              <button
                onClick={handleStart}
                disabled={!canStart}
                className="btn-action"
              >
                begin
              </button>

              {/* Config toggle */}
              <button
                onClick={() => setConfigOpen((v) => !v)}
                className="font-system text-[0.75rem] text-dim tracking-wide transition-all hover:text-cold"
              >
                {configOpen ? "hide config" : "configure"}
              </button>

              {/* Config panel */}
              {configOpen && (
                <div className="flex flex-col gap-4 w-full max-w-xs animate-fade-in">
                  {/* Round sequence builder */}
                  <div className="flex flex-col gap-2">
                    <span className="font-system text-[0.65rem] text-dim tracking-[0.15em] uppercase text-center">
                      protocol sequence
                    </span>
                    <div className="flex flex-wrap justify-center gap-1.5">
                      {ROUND_TYPES.map((rt) => (
                        <button
                          key={rt.value}
                          onClick={() => addRound(rt.value)}
                          className="font-system text-[0.65rem] text-dim tracking-wide px-2 py-1
                            border border-rule rounded transition-all hover:text-cold hover:border-cold"
                        >
                          + {rt.label}
                        </button>
                      ))}
                    </div>

                    {roundSequence.length > 0 ? (
                      <div className="flex flex-col items-center gap-1 mt-1">
                        {roundSequence.map((rt, i) => (
                          <button
                            key={i}
                            onClick={() => removeRound(i)}
                            className="font-system text-[0.65rem] text-cold tracking-wide
                              hover:text-warm transition-colors group flex items-center gap-2"
                          >
                            <span className="text-dim">{i + 1}.</span>
                            <span>{roundLabel(rt)}</span>
                            <span className="text-dim group-hover:text-warm">&times;</span>
                          </button>
                        ))}
                        <button
                          onClick={() => setRoundSequence([])}
                          className="font-system text-[0.6rem] text-dim tracking-wide mt-1 hover:text-cold transition-colors"
                        >
                          clear
                        </button>
                      </div>
                    ) : (
                      <span className="font-system text-[0.6rem] text-dim tracking-wide text-center">
                        default: 5 random rounds
                      </span>
                    )}
                  </div>

                  {/* AI count */}
                  <div className="flex items-center justify-center gap-3">
                    <span className="font-system text-[0.65rem] text-dim tracking-[0.15em] uppercase">
                      ai subjects
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setAiCount((c) => Math.max(1, c - 1))}
                        disabled={aiCount <= 1}
                        className="font-system text-[0.75rem] text-dim hover:text-cold transition-colors disabled:opacity-30"
                      >
                        &#9666;
                      </button>
                      <span className="font-system text-[0.75rem] text-cold w-4 text-center">
                        {aiCount}
                      </span>
                      <button
                        onClick={() => setAiCount((c) => Math.min(8, c + 1))}
                        disabled={aiCount >= 8}
                        className="font-system text-[0.75rem] text-dim hover:text-cold transition-colors disabled:opacity-30"
                      >
                        &#9656;
                      </button>
                    </div>
                  </div>

                  {/* Timers toggle */}
                  <button
                    onClick={() => setTimersDisabled((v) => !v)}
                    className="flex items-center justify-center gap-2"
                  >
                    <span className="font-system text-[0.65rem] text-dim tracking-[0.15em] uppercase">
                      timers
                    </span>
                    <span className={`font-system text-[0.65rem] tracking-wide ${
                      timersDisabled ? "text-warm" : "text-cold"
                    }`}>
                      {timersDisabled ? "off" : "on"}
                    </span>
                  </button>
                </div>
              )}
            </>
          )}

          {!isHost && <SystemText>waiting for host to begin</SystemText>}

          <button
            onClick={handleCopyLink}
            className="font-system text-[0.75rem] text-dim tracking-wide transition-all hover:text-cold"
          >
            {copied ? "copied" : "copy invite link"}
          </button>
        </div>
      </Panel>
    </>
  );
}
