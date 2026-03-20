export interface PhaseLayout {
  roomIndex: number;
  brightness: number; // 0-1
  accentColor: number; // 0=cold, 1=warm
}

// Framework layouts (non-round phases)
const SHARED_LAYOUTS: Record<string, PhaseLayout> = {
  lobby: { roomIndex: 0, brightness: 0.6, accentColor: 0 },
  game_over: { roomIndex: 4, brightness: 1.0, accentColor: 1 },
};

// Step-based layouts keyed by component
const STEP_LAYOUTS: Record<string, PhaseLayout> = {
  compose: { roomIndex: 1, brightness: 0.8, accentColor: 0 },
  signal_compose: { roomIndex: 1, brightness: 0.8, accentColor: 0 },
  vote: { roomIndex: 3, brightness: 0.8, accentColor: 0 },
  vote_results: { roomIndex: 3, brightness: 0.9, accentColor: 0 },
  brain_test: { roomIndex: 2, brightness: 0.9, accentColor: 0 },
  brain_test_results: { roomIndex: 2, brightness: 0.9, accentColor: 0 },
  wager: { roomIndex: 2, brightness: 0.85, accentColor: 0 },
  wager_results: { roomIndex: 2, brightness: 0.9, accentColor: 0 },
  signal_guess: { roomIndex: 2, brightness: 0.85, accentColor: 0 },
  signal_results: { roomIndex: 2, brightness: 0.9, accentColor: 0 },
};

export function getPhaseLayout(phase: string, component: string | null): PhaseLayout {
  if (SHARED_LAYOUTS[phase]) return SHARED_LAYOUTS[phase];
  if (component && STEP_LAYOUTS[component]) return STEP_LAYOUTS[component];
  return SHARED_LAYOUTS.lobby;
}
