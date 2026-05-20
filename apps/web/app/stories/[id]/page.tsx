"use client";

import { notFound } from "next/navigation";
import { use } from "react";
import StoryEditor from "../../StoryEditor";

export default function StoryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const storyId = Number(id);
  if (!Number.isFinite(storyId) || storyId <= 0) notFound();
  return <StoryEditor storyId={storyId} />;
}
