import { Stage } from "@/components/Stage";

export default async function GamePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <Stage>
      <p className="font-[family-name:var(--font-system)] text-[0.75rem]"
        style={{ color: 'var(--dim)' }}>
        Game: {id}
      </p>
    </Stage>
  );
}
