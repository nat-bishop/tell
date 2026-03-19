const LEVELS = { DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3 } as const;
type LevelName = keyof typeof LEVELS;

const configured = (
  process.env.NEXT_PUBLIC_TELL_LOG_LEVEL?.toUpperCase() ?? "INFO"
) as LevelName;
const currentLevel = LEVELS[configured] ?? LEVELS.INFO;

function emit(
  level: number,
  method: "debug" | "info" | "warn" | "error",
  message: string,
  context?: Record<string, unknown>,
) {
  if (level < currentLevel) return;
  if (context) {
    console[method](`[TELL] ${message}`, context);
  } else {
    console[method](`[TELL] ${message}`);
  }
}

export const log = {
  debug: (msg: string, ctx?: Record<string, unknown>) => emit(0, "debug", msg, ctx),
  info: (msg: string, ctx?: Record<string, unknown>) => emit(1, "info", msg, ctx),
  warn: (msg: string, ctx?: Record<string, unknown>) => emit(2, "warn", msg, ctx),
  error: (msg: string, ctx?: Record<string, unknown>) => emit(3, "error", msg, ctx),
};
