import { useEffect } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { getPhaseLayout, CHAR_STATES } from "./phaseLayouts";

export function useFacilityCharacters(rive: any | null) {
  const players = useGameStore((s) => s.players);
  const phase = useGameStore((s) => s.phase);
  const roundType = useGameStore((s) => s.roundType);

  useEffect(() => {
    if (!rive) return;
    const config = getPhaseLayout(phase, roundType);
    if (!config) return;

    players.forEach((player, i) => {
      if (i >= 6) return;
      const charConfig = config.characters[i] ?? config.characters[0];
      rive.setNumberInput(`char_${i}_x`, charConfig.x);
      rive.setNumberInput(`char_${i}_state`, CHAR_STATES[charConfig.state] ?? 0);
      rive.setBooleanInput(`char_${i}_visible`, true);
    });

    // Hide unused character slots
    for (let i = players.length; i < 6; i++) {
      rive.setBooleanInput(`char_${i}_visible`, false);
    }

    // Set room configuration
    rive.setNumberInput("room_config", config.roomIndex);
    rive.setNumberInput("ambient_brightness", config.brightness);
    rive.setNumberInput("accent_color", config.accentColor);
  }, [rive, phase, roundType, players]);
}
