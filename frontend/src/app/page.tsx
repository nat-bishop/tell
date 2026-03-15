import { Stage } from "@/components/Stage";

export default function Home() {
  return (
    <Stage>
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-12">
        <div className="text-center">
          <h1 className="font-[family-name:var(--font-literary)] text-[3rem] font-normal"
            style={{ color: 'var(--ink)' }}>
            tell
          </h1>
          <p className="mt-3 font-[family-name:var(--font-literary)] text-[1.1rem]"
            style={{ color: 'var(--dim)' }}>
            a game of words and suspicion
          </p>
        </div>
        <a href="/game/new"
          className="font-[family-name:var(--font-literary)] text-[1.1rem] transition-colors hover:opacity-70"
          style={{ color: 'var(--ink)' }}>
          new game →
        </a>
      </div>
    </Stage>
  );
}
