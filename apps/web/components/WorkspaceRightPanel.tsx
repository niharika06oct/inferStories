"use client";

import { forwardRef, useImperativeHandle, useState } from "react";
import { Badge, Button, Spinner, cn } from "./ui";
import { ClaimsReviewPanel } from "./ClaimsReviewPanel";
import { RightPanelAccordionRow } from "./RightPanelAccordion";
import type { ClaimOut, ValidationIssueOut } from "../lib/api";
import { claimBucketCounts } from "../lib/claimBuckets";

export type RightPanelSection =
  | "continuity"
  | "newClaims"
  | "acceptedClaims"
  | "rejectedClaims";

export type WorkspaceRightPanelHandle = {
  expandSection: (section: RightPanelSection) => void;
};

type WorkspaceRightPanelProps = {
  storyLoading: boolean;
  busy: boolean;
  chapterDisabled: boolean;
  claims: ClaimOut[];
  focusedClaimId?: number | null;
  onClaimSelect?: (claim: ClaimOut) => void;
  onClaimApprove: (claimId: number) => void;
  onClaimReject: (claimId: number) => void;
  continuityIssues: ValidationIssueOut[];
  continuityLoading: boolean;
  continuityLoadedAt: string | null;
  onRefreshContinuity: () => void;
};

export const WorkspaceRightPanel = forwardRef<
  WorkspaceRightPanelHandle,
  WorkspaceRightPanelProps
>(function WorkspaceRightPanel(
  {
    storyLoading,
    busy,
    chapterDisabled,
    claims,
    focusedClaimId,
    onClaimSelect,
    onClaimApprove,
    onClaimReject,
    continuityIssues,
    continuityLoading,
    continuityLoadedAt,
    onRefreshContinuity,
  },
  ref,
) {
  const [expandedSection, setExpandedSection] =
    useState<RightPanelSection | null>(null);

  useImperativeHandle(ref, () => ({
    expandSection(section: RightPanelSection) {
      setExpandedSection(section);
    },
  }));

  const refreshDisabled = storyLoading || busy || chapterDisabled;
  const counts = claimBucketCounts(claims);

  function toggle(section: RightPanelSection) {
    setExpandedSection((prev) => (prev === section ? null : section));
  }

  return (
    <div className="right-panel-accordion flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0 border-b border-border px-3 py-2.5">
        <p className="text-xs font-medium text-foreground">Chapter checks</p>
        <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">
          Expand a section below. Only one stays open at a time.
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <RightPanelAccordionRow
          id="continuity"
          title="Continuity"
          description="Contradictions vs earlier chapters"
          count={continuityIssues.length}
          expanded={expandedSection === "continuity"}
          onToggle={() => toggle("continuity")}
        >
          <div className="border-b border-border/60 bg-secondary/25 px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11px] text-muted-foreground">
                {continuityLoadedAt
                  ? `Updated ${new Date(continuityLoadedAt).toLocaleTimeString()}`
                  : "Click Refresh to load"}
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={refreshDisabled || continuityLoading}
                onClick={onRefreshContinuity}
              >
                {continuityLoading ? (
                  <>
                    <Spinner /> …
                  </>
                ) : (
                  "Refresh"
                )}
              </Button>
            </div>
          </div>
          <div className="max-h-[min(36vh,18rem)] overflow-y-auto overscroll-contain p-3">
            {storyLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : continuityLoading && continuityIssues.length === 0 ? (
              <div className="space-y-2">
                {[1, 2].map((n) => (
                  <div
                    key={n}
                    className="h-14 animate-pulse rounded-lg bg-muted"
                  />
                ))}
              </div>
            ) : continuityIssues.length === 0 ? (
              <p className="rounded-lg border border-dashed border-border bg-muted/20 px-3 py-6 text-center text-sm text-muted-foreground">
                No continuity issues yet.
              </p>
            ) : (
              <ul className="space-y-2">
                {continuityIssues.map((iss) => (
                  <li
                    key={iss.id}
                    className="rounded-lg border border-border bg-background/60 p-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        variant={
                          iss.severity === "high" ? "destructive" : "warning"
                        }
                      >
                        {iss.severity}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        Ch. {iss.scene_number}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6">{iss.message}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </RightPanelAccordionRow>

        <RightPanelAccordionRow
          id="new-claims"
          title="New claims"
          description="Needs your approve or reject"
          count={counts.new}
          expanded={expandedSection === "newClaims"}
          onToggle={() => toggle("newClaims")}
        >
          <div
            className={cn(
              "max-h-[min(40vh,20rem)] overflow-y-auto overscroll-contain",
            )}
          >
            <ClaimsReviewPanel
              bucket="new"
              claims={claims}
              disabled={chapterDisabled}
              focusedClaimId={focusedClaimId}
              onClaimSelect={onClaimSelect}
              onApprove={onClaimApprove}
              onReject={onClaimReject}
            />
          </div>
        </RightPanelAccordionRow>

        <RightPanelAccordionRow
          id="accepted-claims"
          title="Accepted claims"
          description="Approved story memory for this chapter"
          count={counts.accepted}
          expanded={expandedSection === "acceptedClaims"}
          onToggle={() => toggle("acceptedClaims")}
        >
          <div className="max-h-[min(36vh,18rem)] overflow-y-auto overscroll-contain">
            <ClaimsReviewPanel
              bucket="accepted"
              claims={claims}
              disabled={chapterDisabled}
              focusedClaimId={focusedClaimId}
              onClaimSelect={onClaimSelect}
              onApprove={onClaimApprove}
              onReject={onClaimReject}
            />
          </div>
        </RightPanelAccordionRow>

        <RightPanelAccordionRow
          id="rejected-claims"
          title="Rejected claims"
          description="Hidden from review until you open this section"
          count={counts.rejected}
          expanded={expandedSection === "rejectedClaims"}
          onToggle={() => toggle("rejectedClaims")}
        >
          <div className="max-h-[min(32vh,16rem)] overflow-y-auto overscroll-contain">
            <ClaimsReviewPanel
              bucket="rejected"
              claims={claims}
              disabled={chapterDisabled}
              focusedClaimId={focusedClaimId}
              onClaimSelect={onClaimSelect}
              onApprove={onClaimApprove}
              onReject={onClaimReject}
            />
          </div>
        </RightPanelAccordionRow>
      </div>
    </div>
  );
});
