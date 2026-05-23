import type { ClaimOut } from "./api";

export type ClaimBucket = "new" | "accepted" | "rejected";

export function filterClaimsByBucket(
  claims: ClaimOut[],
  bucket: ClaimBucket,
): ClaimOut[] {
  switch (bucket) {
    case "new":
      return claims.filter(
        (c) => c.status === "needs_review" || c.status === "suggested",
      );
    case "accepted":
      return claims.filter((c) => c.status === "approved");
    case "rejected":
      return claims.filter((c) => c.status === "rejected");
  }
}

export function claimBucketCounts(claims: ClaimOut[]) {
  return {
    new: filterClaimsByBucket(claims, "new").length,
    accepted: filterClaimsByBucket(claims, "accepted").length,
    rejected: filterClaimsByBucket(claims, "rejected").length,
  };
}
