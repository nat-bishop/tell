export interface CharacterPosition {
  x: number; // 0-1 normalized horizontal position
  state: string; // idle, walk, sit, type, point, celebrate, collapse
}

export interface PhaseLayout {
  roomIndex: number;
  brightness: number; // 0-1
  accentColor: number; // 0=cold, 1=warm
  characters: CharacterPosition[]; // Default positions per slot (up to 6)
}

export const PHASE_LAYOUTS: Record<string, PhaseLayout> = {
  lobby: {
    roomIndex: 0,
    brightness: 0.6,
    accentColor: 0,
    characters: [
      { x: 0.2, state: "idle" },
      { x: 0.3, state: "idle" },
      { x: 0.4, state: "idle" },
      { x: 0.5, state: "idle" },
      { x: 0.6, state: "idle" },
      { x: 0.7, state: "idle" },
    ],
  },
  prompt: {
    roomIndex: 1,
    brightness: 0.8,
    accentColor: 0,
    characters: [
      { x: 0.15, state: "sit" },
      { x: 0.3, state: "sit" },
      { x: 0.45, state: "sit" },
      { x: 0.6, state: "sit" },
      { x: 0.75, state: "sit" },
      { x: 0.9, state: "sit" },
    ],
  },
  vote: {
    roomIndex: 3,
    brightness: 0.8,
    accentColor: 0,
    characters: [
      { x: 0.2, state: "idle" },
      { x: 0.35, state: "idle" },
      { x: 0.5, state: "idle" },
      { x: 0.65, state: "idle" },
      { x: 0.8, state: "idle" },
      { x: 0.9, state: "idle" },
    ],
  },
  vote_results: {
    roomIndex: 3,
    brightness: 0.9,
    accentColor: 0,
    characters: [
      { x: 0.2, state: "idle" },
      { x: 0.35, state: "idle" },
      { x: 0.5, state: "idle" },
      { x: 0.65, state: "idle" },
      { x: 0.8, state: "idle" },
      { x: 0.9, state: "idle" },
    ],
  },
  brain_test: {
    roomIndex: 2,
    brightness: 0.9,
    accentColor: 0,
    characters: [
      { x: 0.15, state: "idle" },
      { x: 0.3, state: "idle" },
      { x: 0.45, state: "idle" },
      { x: 0.6, state: "idle" },
      { x: 0.75, state: "idle" },
      { x: 0.9, state: "idle" },
    ],
  },
  brain_test_results: {
    roomIndex: 2,
    brightness: 0.9,
    accentColor: 0,
    characters: [
      { x: 0.15, state: "idle" },
      { x: 0.3, state: "idle" },
      { x: 0.45, state: "idle" },
      { x: 0.6, state: "idle" },
      { x: 0.75, state: "idle" },
      { x: 0.9, state: "idle" },
    ],
  },
  game_over: {
    roomIndex: 4,
    brightness: 1.0,
    accentColor: 1,
    characters: [
      { x: 0.15, state: "idle" },
      { x: 0.3, state: "idle" },
      { x: 0.45, state: "idle" },
      { x: 0.6, state: "idle" },
      { x: 0.75, state: "idle" },
      { x: 0.9, state: "idle" },
    ],
  },
};

export const CHAR_STATES: Record<string, number> = {
  idle: 0,
  walk_right: 1,
  walk_left: 2,
  sit: 3,
  type: 4,
  point: 5,
  think: 6,
  celebrate: 7,
  collapse: 8,
};
