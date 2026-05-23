"use client";

import type { ReactNode } from "react";
import { Badge, Button, cn } from "./ui";
import type { ClaimOut } from "../lib/api";
import type { ClaimBucket } from "../lib/claimBuckets";
import { filterClaimsByBucket } from "../lib/claimBuckets";

const GROUP_ORDER: { key: string; label: string; types: string[] }[] = [
  {
    key: "characters",
    label: "Characters",
    types: ["character_trait", "character_goal", "character_state"],
  },
  {
    key: "relationships",
    label: "Relationships",
    types: ["relationship_state", "relationship_change"],
  },
  {
    key: "world",
    label: "World rules",
    types: ["world_rule", "power_rule"],
  },
  {
    key: "plot",
    label: "Plotlines & events",
    types: ["plotline_fact", "event", "timeline_fact"],
  },
];

const EMPTY_HINT: Record<ClaimBucket, string> = {
  new: "No claims waiting for review. Run Save & analyze memory on this chapter to extract new story memory.",
  accepted: "No accepted claims yet. Approve suggestions from New claims to add them to your story memory.",
  rejected: "No rejected claims. Items you reject while reviewing are kept here for reference.",
};

function statusBadge(c: ClaimOut) {
  const wrap = (badge: ReactNode) => (
    <span className="text-[10px]">{badge}</span>
  );
  if (c.status === "approved" && c.source === "extracted") {
    return wrap(<Badge variant="secondary">Auto-detected</Badge>);
  }
  if (c.status === "needs_review") {
    return wrap(<Badge variant="warning">Review</Badge>);
  }
  if (c.status === "suggested") {
    return wrap(<Badge variant="outline">Suggested</Badge>);
  }
  if (c.status === "rejected") {
    return wrap(<Badge variant="destructive">Rejected</Badge>);
  }
  return null;
}

function ClaimCard({
  claim,
  bucket,
  disabled,
  isFocused,
  onSelect,
  onApprove,
  onReject,
}: {
  claim: ClaimOut;
  bucket: ClaimBucket;
  disabled?: boolean;
  isFocused?: boolean;
  onSelect?: (claim: ClaimOut) => void;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
}) {
  const text =
    claim.claim_text ??
    `${claim.subject} ${claim.predicate}${claim.target ? ` ${claim.target}` : ""}`;
  const showActions = bucket === "new";

  return (
    <li
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onClick={() => onSelect?.(claim)}
      onKeyDown={(e) => {
        if (!onSelect) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(claim);
        }
      }}
      className={cn(
        "rounded-lg border border-border bg-muted/25 p-3 transition-colors",
        onSelect && "cursor-pointer hover:bg-muted/40",
        isFocused && "border-amber-400/70 bg-amber-500/10 ring-2 ring-amber-400/35",
        bucket === "rejected" && "opacity-70",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="text-sm font-medium leading-snug text-foreground">{text}</p>
        <div className="flex shrink-0 flex-wrap items-center gap-1.5">
          {statusBadge(claim)}
          <span className="text-[10px] text-muted-foreground">
            {Math.round(claim.confidence * 100)}%
          </span>
        </div>
      </div>
      {claim.evidence_text ? (
        <p className="mt-2 text-xs italic leading-5 text-muted-foreground">
          &ldquo;{claim.evidence_text}&rdquo;
        </p>
      ) : null}
      {showActions ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="cta"
            disabled={disabled}
            onClick={(e) => {
              e.stopPropagation();
              onApprove(claim.id);
            }}
          >
            Approve
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={disabled}
            onClick={(e) => {
              e.stopPropagation();
              onReject(claim.id);
            }}
          >
            Reject
          </Button>
        </div>
      ) : null}
    </li>
  );
}

function groupAcceptedClaims(claims: ClaimOut[]) {
  const byGroup = new Map<string, ClaimOut[]>();
  for (const g of GROUP_ORDER) {
    byGroup.set(g.key, []);
  }
  for (const c of claims) {
    const type = c.claim_type ?? c.predicate;
    let placed = false;
    for (const g of GROUP_ORDER) {
      if (g.types.includes(type)) {
        byGroup.get(g.key)!.push(c);
        placed = true;
        break;
      }
    }
    if (!placed) {
      byGroup.get("characters")!.push(c);
    }
  }
  return byGroup;
}

type ClaimsReviewPanelProps = {
  bucket: ClaimBucket;
  claims: ClaimOut[];
  disabled?: boolean;
  focusedClaimId?: number | null;
  onClaimSelect?: (claim: ClaimOut) => void;
  onApprove: (claimId: number) => void;
  onReject: (claimId: number) => void;
};

export function ClaimsReviewPanel({
  bucket,
  claims,
  disabled,
  focusedClaimId,
  onClaimSelect,
  onApprove,
  onReject,
}: ClaimsReviewPanelProps) {
  const filtered = filterClaimsByBucket(claims, bucket);

  if (filtered.length === 0) {
    return (
      <p className="px-4 py-6 text-sm leading-6 text-muted-foreground">
        {EMPTY_HINT[bucket]}
      </p>
    );
  }

  if (bucket === "accepted") {
    const byGroup = groupAcceptedClaims(filtered);
    return (
      <div className="space-y-4 px-3 py-3">
        {GROUP_ORDER.map((g) => {
          const items = byGroup.get(g.key) ?? [];
          if (items.length === 0) return null;
          return (
            <section key={g.key}>
              <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {g.label}
              </h4>
              <ul className="space-y-2">
                {items.map((c) => (
                  <ClaimCard
                    key={c.id}
                    claim={c}
                    bucket={bucket}
                    disabled={disabled}
                    isFocused={focusedClaimId === c.id}
                    onSelect={onClaimSelect}
                    onApprove={onApprove}
                    onReject={onReject}
                  />
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    );
  }

  const sorted =
    bucket === "new"
      ? [...filtered].sort((a, b) => {
          const rank = (s: string) =>
            s === "needs_review" ? 0 : s === "suggested" ? 1 : 2;
          const d = rank(a.status) - rank(b.status);
          if (d !== 0) return d;
          return b.confidence - a.confidence;
        })
      : filtered;

  return (
    <ul className="space-y-2 px-3 py-3">
      {sorted.map((c) => (
        <ClaimCard
          key={c.id}
          claim={c}
          bucket={bucket}
          disabled={disabled}
          isFocused={focusedClaimId === c.id}
          onSelect={onClaimSelect}
          onApprove={onApprove}
          onReject={onReject}
        />
      ))}
    </ul>
  );
}
