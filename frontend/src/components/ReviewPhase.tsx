"use client";

import { useState, useEffect } from "react";
import { useGameStore, type PlayerInfo } from "@/hooks/useGameStore";
import { Spotlight } from "./Spotlight";
import { Gallery } from "./Gallery";
import { VoteOverlay } from "./VoteOverlay";
import { SystemText } from "./SystemText";

function TripletCard({ player }: { player: PlayerInfo }) {
  const { answers, questions, players, roundType, synthesis, nominatedId } =
    useGameStore();

  const answer = answers[player.id];
  const myQuestion = questions.find((q) => q.target_id === player.id);

  // For interrogation spotlight on nominee: show synthesis instead of individual question
  const isNominee = roundType === "interrogation" && player.id === nominatedId;
  const questionText = isNominee ? synthesis : myQuestion?.question;
  const responseText = myQuestion?.response;

  return (
    <div className="border-b border-rule pb-4">
      <div className="font-literary-sc text-[0.85rem] tracking-[0.08em] text-ink">
        {player.alias}
      </div>
      {answer && (
        <div className="mt-1 font-literary text-[1rem] leading-[1.5] text-ink">
          {answer}
        </div>
      )}
      {questionText && (
        <>
          <div className="mt-3 font-system text-[0.7rem] text-dim">
            {isNominee ? "synthesis" : "question received"}
          </div>
          <div className="mt-0.5 font-literary text-[0.95rem] italic leading-[1.5] text-ink">
            {questionText}
          </div>
        </>
      )}
      {responseText && (
        <>
          <div className="mt-2 font-system text-[0.7rem] text-dim">
            response
          </div>
          <div className="mt-0.5 font-literary text-[0.95rem] leading-[1.5] text-ink">
            {responseText}
          </div>
        </>
      )}
    </div>
  );
}

export function ReviewPhase({ spectator = false }: { spectator?: boolean }) {
  const { players, roundType, nominatedId } = useGameStore();
  const alivePlayers = players.filter((p) => p.is_alive);

  // For interrogation: spotlight on nominee first, then gallery
  const spotlightDuration = alivePlayers.length * 5;
  const [showGallery, setShowGallery] = useState(false);

  useEffect(() => {
    const timer = setTimeout(
      () => setShowGallery(true),
      spotlightDuration * 1000,
    );
    return () => clearTimeout(timer);
  }, [spotlightDuration]);

  // Determine spotlight order: for interrogation, nominee first
  let spotlightPlayers = alivePlayers;
  if (roundType === "interrogation" && nominatedId) {
    const nominee = alivePlayers.find((p) => p.id === nominatedId);
    const rest = alivePlayers.filter((p) => p.id !== nominatedId);
    if (nominee) spotlightPlayers = [nominee, ...rest];
  }

  return (
    <div className="flex flex-col gap-6 pt-4">
      <SystemText>review &amp; vote</SystemText>

      {!showGallery ? (
        <Spotlight
          players={spotlightPlayers}
          renderContent={(p) => <TripletCard player={p} />}
          secondsPerPlayer={5}
        />
      ) : (
        <Gallery
          players={alivePlayers}
          renderCard={(p) => <TripletCard player={p} />}
        />
      )}

      {!spectator && <VoteOverlay />}

      {spectator && (
        <SystemText>voting in progress</SystemText>
      )}
    </div>
  );
}
