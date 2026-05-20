"use client";

import { Badge, Button, cn } from "./ui";
import type { ClaimOut } from "../lib/api";

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

function groupClaims(claims: ClaimOut[]) {
  const needsReview: ClaimOut[] = [];
  const suggested: ClaimOut[] = [];
  const byGroup = new Map<string, ClaimOut[]>();

  for (const g of GROUP_ORDER) {
    byGroup.set(g.key, []);
  }

  for (const c of claims) {
    if (c.status === "needs_review") {
      needsReview.push(c);
      continue;
    }
    if (c.status === "suggested") {
      suggested.push(c);
      continue;
    }
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

  return { byGroup, needsReview, suggested };
}

function statusBadge(c: ClaimOut) {
  if (c.status === "approved" && c.source === "extracted") {
    return (
      <Badge variant="secondary" className="text-[10px]">
        Auto-detected
      </Badge>
    );
  }
  if (c.status === "needs_review") {
    return (
      <Badge variant="warning" className="text-[10px]">
        Review
      </Badge>
    );
  }
  if (c.status === "suggested") {
    return (
      <Badge variant="outline" className="text-[10px]">
        Suggested
      </Badge>
    );
  }
  if (c.status === "rejected") {
    return (
      <Badge variant="destructive" className="text-[10px]">
        Rejected
      </Badge>
    );
  }
  return null;
}

type DetectedStoryMemoryProps = {
  claims: ClaimOut[];
  disabled?: boolean;
  onApprove: (claimId: number) => void;
  onReject: (claimId: number) => void;
};

function ClaimCard({
  claim,
  disabled,
  onApprove,
  onReject,
}: {
  claim: ClaimOut;
  disabled?: boolean;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
}) {
  const text =
    claim.claim_text ??
    `${claim.subject} ${claim.predicate}${claim.target ? ` ${claim.target}` : ""}`;

  return (
    <li
      className={cn(
        "rounded-lg border border-border bg-muted/25 p-3",
        claim.status === "rejected" && "opacity-50",
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
      {(claim.status === "needs_review" || claim.status === "suggested") && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="cta"
            disabled={disabled}
            onClick={() => onApprove(claim.id)}
          >
            Approve
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={disabled}
            onClick={() => onReject(claim.id)}
          >
            Reject
          </Button>
        </div>
      )}
    </li>
  );
}

export function DetectedStoryMemory({
  claims,
  disabled,
  onApprove,
  onReject,
}: DetectedStoryMemoryProps) {
  if (claims.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Save your chapter to detect story memory automatically.
      </p>
    );
  }

  const { byGroup, needsReview, suggested } = groupClaims(claims);
  const showGroups = GROUP_ORDER.some((g) => (byGroup.get(g.key)?.length ?? 0) > 0);

  return (
    <div className="space-y-5">
      {needsReview.length > 0 ? (
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-200/90">
            Needs review
          </h4>
          <ul className="space-y-2">
            {needsReview.map((c) => (
              <ClaimCard
                key={c.id}
                claim={c}
                disabled={disabled}
                onApprove={onApprove}
                onReject={onReject}
              />
            ))}
          </ul>
        </section>
      ) : null}

      {suggested.length > 0 ? (
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Suggested only (low confidence)
          </h4>
          <ul className="space-y-2">
            {suggested.map((c) => (
              <ClaimCard
                key={c.id}
                claim={c}
                disabled={disabled}
                onApprove={onApprove}
                onReject={onReject}
              />
            ))}
          </ul>
        </section>
      ) : null}

      {showGroups
        ? GROUP_ORDER.map((g) => {
            const items = byGroup.get(g.key) ?? [];
            if (items.length === 0) return null;
            return (
              <section key={g.key}>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {g.label}
                </h4>
                <ul className="space-y-2">
                  {items.map((c) => (
                    <ClaimCard
                      key={c.id}
                      claim={c}
                      disabled={disabled}
                      onApprove={onApprove}
                      onReject={onReject}
                    />
                  ))}
                </ul>
              </section>
            );
          })
        : null}
    </div>
  );
}
