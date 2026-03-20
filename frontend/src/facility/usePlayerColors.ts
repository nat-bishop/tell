import { useMemo } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { buildColorMap } from "./subjectColors";

export function usePlayerColors() {
  const players = useGameStore((s) => s.players);
  return useMemo(() => buildColorMap(players.map((p) => p.id)), [players]);
}
