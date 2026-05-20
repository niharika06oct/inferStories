/** Routes that do not require a signed-in session. */
export const PUBLIC_PATHS = ["/", "/login"] as const;

export function isPublicPath(pathname: string): boolean {
  return (PUBLIC_PATHS as readonly string[]).includes(pathname);
}
