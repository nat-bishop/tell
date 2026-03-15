import { useGameStore } from "./useGameStore";

export function useAnswerEntries() {
  const { answers, players } = useGameStore();
  return Object.entries(answers).map(([pid, text]) => {
    const player = players.find((p) => p.id === pid);
    return { alias: player?.alias || "???", text };
  });
}
