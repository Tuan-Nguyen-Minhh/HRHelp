const PREFIX = "hr_idem_";

export function idempotencyKey(scope: string): string {
  const existing = sessionStorage.getItem(PREFIX + scope);
  if (existing) return existing;
  const created = crypto.randomUUID();
  sessionStorage.setItem(PREFIX + scope, created);
  return created;
}

export function clearIdempotency(scope: string): void {
  sessionStorage.removeItem(PREFIX + scope);
}
