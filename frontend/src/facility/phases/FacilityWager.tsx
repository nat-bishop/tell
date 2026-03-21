"use client";

import { useState, useCallback, useMemo, useRef } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitWagerGuess, submitWagerBet } from "@/api/actions";
import { Panel } from "@/facility/Panel";
import { SystemText } from "@/components/SystemText";
import { usePlayerColors } from "@/facility/usePlayerColors";

// ─── Number Line ───

interface NumberLineProps {
  min: number;
  max: number;
  unit: string;
  markers?: Array<{ value: number; label: string; color: string; id?: string }>;
  correctAnswer?: number;
  interactive?: boolean;
  value?: number;
  onChange?: (value: number) => void;
  onCommit?: (value: number) => void;
  clickable?: boolean;
  selectedMarkerId?: string | null;
  onMarkerClick?: (id: string) => void;
}

function NumberLine({
  min,
  max,
  unit,
  markers,
  correctAnswer,
  interactive,
  value,
  onChange,
  onCommit,
  clickable,
  selectedMarkerId,
  onMarkerClick,
}: NumberLineProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragValueRef = useRef<number | undefined>(undefined);

  const getValueFromPointer = useCallback(
    (clientX: number) => {
      if (!trackRef.current) return min;
      const rect = trackRef.current.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      return Math.round(min + ratio * (max - min));
    },
    [min, max],
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!interactive || !onChange) return;
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      const newVal = getValueFromPointer(e.clientX);
      dragValueRef.current = newVal;
      onChange(newVal);
    },
    [interactive, onChange, getValueFromPointer],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!interactive || !onChange) return;
      if (!(e.target as HTMLElement).hasPointerCapture(e.pointerId)) return;
      const newVal = getValueFromPointer(e.clientX);
      dragValueRef.current = newVal;
      onChange(newVal);
    },
    [interactive, onChange, getValueFromPointer],
  );

  const handlePointerUp = useCallback(
    (e: React.PointerEvent) => {
      if (!interactive) return;
      (e.target as HTMLElement).releasePointerCapture(e.pointerId);
      const finalValue = dragValueRef.current ?? value;
      if (onCommit && finalValue !== undefined) onCommit(finalValue);
    },
    [interactive, onCommit, value],
  );

  const toPercent = (v: number) => ((v - min) / (max - min)) * 100;

  // Group markers by value so same-value guesses merge into one dot
  const mergedMarkers = useMemo(() => {
    if (!markers?.length) return [];
    const groups = new Map<number, Array<(typeof markers)[0]>>();
    for (const m of markers) {
      const group = groups.get(m.value);
      if (group) group.push(m);
      else groups.set(m.value, [m]);
    }
    return Array.from(groups.entries()).map(([val, group]) => ({
      value: val,
      labels: group.map((m) => m.label),
      ids: group.map((m) => m.id).filter((id): id is string => !!id),
      colors: group.map((m) => m.color),
      color: group.length > 1 ? "var(--dim)" : group[0].color,
    }));
  }, [markers]);

  return (
    <div className="w-full select-none" style={{ touchAction: "none" }}>
      {/* Labels above */}
      <div className="relative h-8 mb-1">
        {mergedMarkers.map((mg, i) => {
          const isSelected = !!selectedMarkerId && mg.ids.includes(selectedMarkerId);
          const isDimmed = !!selectedMarkerId && !isSelected;
          return (
            <div
              key={i}
              className="absolute flex flex-col items-center"
              style={{
                left: `${toPercent(mg.value)}%`,
                transform: "translateX(-50%)",
                bottom: 0,
                opacity: isDimmed ? 0.4 : 1,
                transition: "opacity 200ms",
              }}
            >
              {mg.labels.map((label, li) => (
                <span
                  key={li}
                  className="font-system text-[0.55rem] tracking-wider whitespace-nowrap leading-tight"
                  style={{ color: isSelected ? "var(--cold)" : mg.colors[li] }}
                >
                  {label}
                </span>
              ))}
            </div>
          );
        })}
        {correctAnswer !== undefined && (
          <div
            className="absolute flex flex-col items-center"
            style={{
              left: `${toPercent(correctAnswer)}%`,
              transform: "translateX(-50%)",
              bottom: 0,
            }}
          >
            <span className="font-system text-[0.55rem] tracking-wider text-warm whitespace-nowrap">
              {correctAnswer}
            </span>
          </div>
        )}
      </div>

      {/* Track */}
      <div
        ref={trackRef}
        className="relative h-10 flex items-center"
        style={{ cursor: interactive ? "pointer" : "default" }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        {/* Track line */}
        <div
          className="absolute left-0 right-0"
          style={{ height: "1px", background: "var(--rule)", top: "50%" }}
        />

        {/* Correct answer marker (results only) */}
        {correctAnswer !== undefined && (
          <div
            className="absolute animate-fade-in"
            style={{
              left: `${toPercent(correctAnswer)}%`,
              top: "50%",
              transform: "translate(-50%, -50%)",
              width: "16px",
              height: "16px",
              borderRadius: "50%",
              background: "var(--warm)",
              boxShadow: "0 0 12px var(--warm)",
            }}
          />
        )}

        {/* Markers — clickable buttons in bet mode, plain dots otherwise */}
        {clickable
          ? mergedMarkers.map((mg, i) => {
              const isSelected =
                !!selectedMarkerId && mg.ids.includes(selectedMarkerId);
              const isDimmed = !!selectedMarkerId && !isSelected;
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => !isDimmed && onMarkerClick?.(mg.ids[0])}
                  disabled={!!isDimmed}
                  aria-label={`Bet on ${mg.labels.join(", ")}`}
                  className="absolute"
                  style={{
                    left: `${toPercent(mg.value)}%`,
                    top: "50%",
                    transform: "translate(-50%, -50%)",
                    width: "44px",
                    height: "44px",
                    borderRadius: "50%",
                    background: "transparent",
                    border: "none",
                    cursor: isDimmed ? "default" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    opacity: isDimmed ? 0.4 : 1,
                    transition: "opacity 200ms",
                    padding: 0,
                  }}
                >
                  <div
                    className={isSelected ? "animate-bet-glow" : ""}
                    style={{
                      width: isSelected ? "14px" : "10px",
                      height: isSelected ? "14px" : "10px",
                      borderRadius: "50%",
                      background: isSelected ? "var(--cold)" : mg.color,
                      boxShadow: isSelected
                        ? "0 0 12px var(--cold-glow)"
                        : `0 0 6px ${mg.color}`,
                      transition: "all 200ms",
                    }}
                  />
                </button>
              );
            })
          : mergedMarkers.map((mg, i) => (
              <div
                key={i}
                className="absolute"
                style={{
                  left: `${toPercent(mg.value)}%`,
                  top: "50%",
                  transform: "translate(-50%, -50%)",
                  width: "10px",
                  height: "10px",
                  borderRadius: "50%",
                  background: mg.color,
                  boxShadow: `0 0 6px ${mg.color}`,
                }}
              />
            ))}

        {/* Interactive marker (guess drag) */}
        {interactive && value !== undefined && (
          <div
            className="absolute"
            style={{
              left: `${toPercent(value)}%`,
              top: "50%",
              transform: "translate(-50%, -50%)",
              width: "14px",
              height: "14px",
              borderRadius: "50%",
              background: "var(--cold)",
              boxShadow: "0 0 8px var(--cold-glow)",
              minWidth: "44px",
              minHeight: "44px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                width: "14px",
                height: "14px",
                borderRadius: "50%",
                background: "var(--cold)",
              }}
            />
          </div>
        )}
      </div>

      {/* Range labels + unit */}
      <div className="flex justify-between mt-1">
        <span className="font-system text-[0.65rem] text-dim">{min}</span>
        <span className="font-system text-[0.6rem] text-dim tracking-wider">{unit}</span>
        <span className="font-system text-[0.65rem] text-dim">{max}</span>
      </div>
    </div>
  );
}

// ─── Wager Component ───

export function FacilityWager() {
  const gameId = useGameStore((s) => s.gameId);
  const playerId = useGameStore((s) => s.playerId);
  const subRoundPayload = useGameStore((s) => s.subRoundPayload);
  const roundResults = useGameStore((s) => s.roundResults);
  const roundScores = useGameStore((s) => s.roundScores);
  const players = useGameStore((s) => s.players);
  const scores = useGameStore((s) => s.scores);
  const playerColors = usePlayerColors();

  const isWager = subRoundPayload?.round_type === "wager";

  const [guessValues, setGuessValues] = useState<Record<number, number>>({});
  const [currentGuess, setCurrentGuess] = useState<number | null>(null);
  const [betTargets, setBetTargets] = useState<Record<number, string>>({});

  const aliasById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const p of players) map[p.id] = p.alias;
    return map;
  }, [players]);

  const handleGuessCommit = useCallback(
    async (value: number) => {
      if (!gameId || !playerId || !isWager) return;
      const qi = subRoundPayload.question_index;
      try {
        await submitWagerGuess(gameId, playerId, qi, value);
        setGuessValues((prev) => ({ ...prev, [qi]: value }));
        setCurrentGuess(null);
      } catch {
        // Silently handle
      }
    },
    [gameId, playerId, isWager, subRoundPayload],
  );

  const handleBet = useCallback(
    async (targetId: string) => {
      if (!gameId || !playerId || !isWager) return;
      const qi = subRoundPayload.question_index;
      try {
        await submitWagerBet(gameId, playerId, qi, targetId);
        setBetTargets((prev) => ({ ...prev, [qi]: targetId }));
      } catch {
        // Silently handle
      }
    },
    [gameId, playerId, isWager, subRoundPayload],
  );

  // ─── Results View ───

  if (roundResults?.round_type === "wager") {
    const { questions } = roundResults;

    return (
      <Panel zone="full-screen">
        <div className="flex flex-col gap-5 pt-3 overflow-y-auto" style={{ maxHeight: "100%" }}>
          <p className="text-center font-system text-[0.85rem] text-dim tracking-wider uppercase">
            wager results
          </p>

          {questions.map((q, qi) => (
            <div key={qi} className="card p-4">
              <p className="font-literary text-[0.95rem] text-ink mb-1">{q.question}</p>
              <p className="font-system text-[0.6rem] text-cold tracking-wider mb-3">
                answer: {q.correct_answer} {q.unit}
              </p>

              <NumberLine
                min={q.range_min}
                max={q.range_max}
                unit={q.unit}
                correctAnswer={q.correct_answer}
                markers={Object.entries(q.guesses).map(([pid, val]) => ({
                  value: val,
                  label: aliasById[pid] || pid,
                  color: q.closest_ids.includes(pid)
                    ? "var(--cold)"
                    : playerColors[pid] || "var(--dim)",
                }))}
              />

              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(q.bets).map(([pid, target]) => (
                  <span
                    key={pid}
                    className="font-system text-[0.55rem] text-dim tracking-wider"
                  >
                    {aliasById[pid] || pid} {"→"} {aliasById[target] || target}
                    {q.closest_ids.includes(target) ? " \u2713" : ""}
                  </span>
                ))}
              </div>
            </div>
          ))}

          {/* Score summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {Object.entries(roundScores || {})
              .sort(([, a], [, b]) => b - a)
              .map(([pid, score]) => (
                <div key={pid} className="card p-3 text-center">
                  <p className="font-literary-sc text-[0.75rem] text-dim tracking-wide uppercase">
                    {aliasById[pid] || pid}
                  </p>
                  <span className="font-system text-[0.7rem] tracking-wider text-cold">
                    +{score} ({scores[pid] ?? 0} total)
                  </span>
                </div>
              ))}
          </div>

          <SystemText>scores updated</SystemText>
        </div>
      </Panel>
    );
  }

  // ─── Active: Guess Sub-Round ───

  if (isWager && subRoundPayload.phase === "guess") {
    const qi = subRoundPayload.question_index;
    const alreadySubmitted = guessValues[qi] !== undefined;
    const range_mid = Math.round(
      (subRoundPayload.range_min + subRoundPayload.range_max) / 2,
    );

    return (
      <>
        <Panel zone="main-screen">
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <p className="font-system text-[0.6rem] text-cold tracking-[0.2em] uppercase">
              question {qi + 1} of {subRoundPayload.total_questions} — estimate
            </p>
            <p className="font-literary text-[1.15rem] text-ink text-center leading-[1.6] max-w-md">
              {subRoundPayload.question}
            </p>
          </div>
        </Panel>

        <Panel zone="center-area">
          <div className="flex flex-col items-center justify-center h-full gap-3">
            {alreadySubmitted ? (
              <>
                <NumberLine
                  min={subRoundPayload.range_min}
                  max={subRoundPayload.range_max}
                  unit={subRoundPayload.unit}
                  markers={[
                    {
                      value: guessValues[qi],
                      label: `${guessValues[qi]}`,
                      color: "var(--cold)",
                    },
                  ]}
                />
                <p className="font-system text-[0.65rem] text-dim tracking-wider uppercase">
                  submitted: {guessValues[qi]} {subRoundPayload.unit}
                </p>
              </>
            ) : (
              <>
                <NumberLine
                  min={subRoundPayload.range_min}
                  max={subRoundPayload.range_max}
                  unit={subRoundPayload.unit}
                  interactive
                  value={currentGuess ?? range_mid}
                  onChange={setCurrentGuess}
                  onCommit={handleGuessCommit}
                />
                <p className="font-system text-[0.7rem] text-ink tracking-wider">
                  {currentGuess ?? range_mid} {subRoundPayload.unit}
                </p>
                <button
                  onClick={() => handleGuessCommit(currentGuess ?? range_mid)}
                  className="px-6 py-2 min-h-[44px] rounded font-system text-[0.75rem] text-ink tracking-wider uppercase bg-surface hover:bg-raised transition-colors border border-rule hover:border-cold/40 cursor-pointer"
                >
                  submit guess
                </button>
              </>
            )}
          </div>
        </Panel>
      </>
    );
  }

  // ─── Active: Bet Sub-Round ───

  if (isWager && subRoundPayload.phase === "bet") {
    const qi = subRoundPayload.question_index;
    const guesses = subRoundPayload.guesses || {};
    const alreadyBet = betTargets[qi] !== undefined;
    const guessEntries = Object.entries(guesses);

    return (
      <Panel zone="full-screen">
        <div className="flex flex-col items-center justify-center h-full gap-5">
          <div className="text-center">
            <p className="font-system text-[0.6rem] text-cold tracking-[0.2em] uppercase mb-2">
              question {qi + 1} of {subRoundPayload.total_questions} — place your bet
            </p>
            <p className="font-literary text-[0.95rem] text-ink text-center leading-[1.6] max-w-md">
              {subRoundPayload.question}
            </p>
          </div>

          <div className="w-full max-w-lg">
            <NumberLine
              min={subRoundPayload.range_min}
              max={subRoundPayload.range_max}
              unit={subRoundPayload.unit}
              clickable={!alreadyBet}
              selectedMarkerId={betTargets[qi] ?? null}
              onMarkerClick={(id) => handleBet(id)}
              markers={guessEntries.map(([pid, val]) => ({
                value: val,
                label: aliasById[pid] || pid,
                color: playerColors[pid] || "var(--dim)",
                id: pid,
              }))}
            />
          </div>

          <p className="font-system text-[0.6rem] text-dim tracking-wider uppercase">
            {alreadyBet
              ? `bet placed on ${aliasById[betTargets[qi]] || betTargets[qi]}`
              : "whose guess is closest?"}
          </p>
        </div>
      </Panel>
    );
  }

  // Waiting state
  return (
    <Panel zone="main-screen">
      <div className="flex items-center justify-center h-full">
        <p className="font-system text-[0.85rem] text-dim tracking-wider uppercase">
          waiting for question...
        </p>
      </div>
    </Panel>
  );
}
