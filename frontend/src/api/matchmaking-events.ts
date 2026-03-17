import { API_URL } from "./client";

export interface LobbyStatusData {
  event_type: "lobby_status";
  seq: number;
  human_count: number;
  countdown_seconds: number | null;
  message: string;
}

export interface GameAssignedData {
  event_type: "game_assigned";
  seq: number;
  game_id: string;
}

export interface MatchmakingCallbacks {
  onLobbyStatus: (data: LobbyStatusData) => void;
  onGameAssigned: (data: GameAssignedData) => void;
}

export function connectMatchmakingEvents(
  playerId: string,
  callbacks: MatchmakingCallbacks,
): { close: () => void } {
  const url = `${API_URL}/matchmaking/events?player_id=${playerId}`;
  const es = new EventSource(url);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const eventMap: Record<string, (data: any) => void> = {
    lobby_status: callbacks.onLobbyStatus,
    game_assigned: callbacks.onGameAssigned,
  };

  for (const [eventType, handler] of Object.entries(eventMap)) {
    es.addEventListener(eventType, (e: MessageEvent) => {
      try {
        handler(JSON.parse(e.data));
      } catch {
        console.error(`Failed to parse ${eventType} event`, e.data);
      }
    });
  }

  es.onerror = () => {
    console.warn("Matchmaking SSE error, will auto-reconnect");
  };

  return { close: () => es.close() };
}
