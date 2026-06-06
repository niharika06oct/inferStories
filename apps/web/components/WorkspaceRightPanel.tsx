"use client";

import { forwardRef, useEffect, useImperativeHandle, useMemo, useState } from "react";
import { Button, Spinner, cn } from "./ui";
import { ClaimsReviewPanel } from "./ClaimsReviewPanel";
import { ContinuityIssuesList } from "./ContinuityIssuesList";
import { RightPanelAccordionRow } from "./RightPanelAccordion";
import type {
  ContinuityResolutionStatus,
  ClaimOut,
  ValidationIssueOut,
} from "../lib/api";
import { claimBucketCounts } from "../lib/claimBuckets";
import { continuityBucketCounts } from "../lib/continuityBuckets";
import {
  CONTINUITY_SORT_OPTIONS,
  loadContinuitySortOrder,
  saveContinuitySortOrder,
  sortContinuityIssues,
  type ContinuitySortOrder,
} from "../lib/continuitySort";

export type RightPanelSection =
  | "continuity"
  | "resolvedContinuity"
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
  focusedContinuityIssueId?: number | null;
  onContinuityIssueSelect?: (issue: ValidationIssueOut) => void;
  onContinuityResolve?: (
    issue: ValidationIssueOut,
    status: ContinuityResolutionStatus,
  ) => void;
  continuityResolveBusyId?: number | null;
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
    focusedContinuityIssueId,
    onContinuityIssueSelect,
    onContinuityResolve,
    continuityResolveBusyId = null,
  },
  ref,
) {
  const [expandedSection, setExpandedSection] =
    useState<RightPanelSection | null>(null);
  const [continuitySort, setContinuitySort] = useState<ContinuitySortOrder>("text");

  useEffect(() => {
    setContinuitySort(loadContinuitySortOrder());
  }, []);

  const continuityCounts = useMemo(
    () => continuityBucketCounts(continuityIssues),
    [continuityIssues],
  );

  const sortedOpenIssues = useMemo(() => {
    const open = continuityIssues.filter(
      (i) => (i.resolution_status ?? "open") === "open",
    );
    return sortContinuityIssues(open, continuitySort);
  }, [continuityIssues, continuitySort]);

  const sortedResolvedIssues = useMemo(() => {
    const resolved = continuityIssues.filter((i) => {
      const s = i.resolution_status ?? "open";
      return s === "fixed" || s === "rejected";
    });
    return sortContinuityIssues(resolved, continuitySort);
  }, [continuityIssues, continuitySort]);

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

  const continuityToolbar = (
    <div className="border-b border-border/60 bg-secondary/25 px-3 py-2 space-y-2">
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
      <label className="flex flex-col gap-1">
        <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Sort
        </span>
        <select
          className="rounded-md border border-border bg-background px-2 py-1.5 text-xs text-foreground"
          value={continuitySort}
          disabled={continuityIssues.length === 0}
          onChange={(e) => {
            const next = e.target.value as ContinuitySortOrder;
            setContinuitySort(next);
            saveContinuitySortOrder(next);
          }}
        >
          {CONTINUITY_SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );

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
          description="Open issues — mark fixed or reject when handled"
          count={continuityCounts.open}
          expanded={expandedSection === "continuity"}
          onToggle={() => toggle("continuity")}
        >
          {continuityToolbar}
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
            ) : (
              <ContinuityIssuesList
                issues={sortedOpenIssues}
                emptyMessage="No open continuity issues."
                focusedContinuityIssueId={focusedContinuityIssueId}
                onContinuityIssueSelect={onContinuityIssueSelect}
                onResolve={onContinuityResolve}
                showResolveActions={!!onContinuityResolve}
                resolveBusyId={continuityResolveBusyId}
              />
            )}
          </div>
        </RightPanelAccordionRow>

        <RightPanelAccordionRow
          id="resolved-continuity"
          title="Handled continuity"
          description="Fixed or rejected — hidden from the open list"
          count={continuityCounts.resolved}
          expanded={expandedSection === "resolvedContinuity"}
          onToggle={() => toggle("resolvedContinuity")}
        >
          <div className="max-h-[min(28vh,14rem)] overflow-y-auto overscroll-contain p-3">
            {storyLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : (
              <ContinuityIssuesList
                issues={sortedResolvedIssues}
                emptyMessage="No handled continuity issues yet."
                focusedContinuityIssueId={focusedContinuityIssueId}
                onContinuityIssueSelect={onContinuityIssueSelect}
              />
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
