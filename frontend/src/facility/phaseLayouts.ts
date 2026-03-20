export interface PhaseLayout {
  roomIndex: number;
  brightness: number; // 0-1
  accentColor: number; // 0=cold, 1=warm
}

// Framework layouts (shared phases)
const SHARED_LAYOUTS: Record<string, PhaseLayout> = {
  lobby: { roomIndex: 0, brightness: 0.6, accentColor: 0 },
  prompt: { roomIndex: 1, brightness: 0.8, accentColor: 0 },
  game_over: { roomIndex: 4, brightness: 1.0, accentColor: 1 },
};

// Minigame layouts (active + results per round type)
const ROUND_LAYOUTS: Record<string, Record<string, PhaseLayout>> = {
  task: {
    active: { roomIndex: 3, brightness: 0.8, accentColor: 0 },
    results: { roomIndex: 3, brightness: 0.9, accentColor: 0 },
  },
  brain_test: {
    active: { roomIndex: 2, brightness: 0.9, accentColor: 0 },
    results: { roomIndex: 2, brightness: 0.9, accentColor: 0 },
  },
  wager: {
    active: { roomIndex: 2, brightness: 0.85, accentColor: 0 },
    results: { roomIndex: 2, brightness: 0.9, accentColor: 0 },
  },
  signal: {
    active: { roomIndex: 2, brightness: 0.85, accentColor: 0 },
    results: { roomIndex: 2, brightness: 0.9, accentColor: 0 },
  },
};

export function getPhaseLayout(phase: string, roundType: string | null): PhaseLayout {
  if (SHARED_LAYOUTS[phase]) return SHARED_LAYOUTS[phase];
  if (roundType && ROUND_LAYOUTS[roundType]?.[phase]) {
    return ROUND_LAYOUTS[roundType][phase];
  }
  return SHARED_LAYOUTS.lobby;
}
