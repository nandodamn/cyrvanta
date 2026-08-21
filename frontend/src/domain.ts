/** Vocabularies the backend defines and the interface must not invent.
 *
 * Fixed rather than derived from live data on purpose: a memory can reasonably
 * apply to `critical` incidents in a tenant that has never had one, and a
 * filter built from whatever exists today would quietly hide the option. What
 * these must not be is duplicated -- three copies of the severity ladder drift,
 * and the copy that drifts is discovered by a user, not by a test.
 */

export const SEVERITIES = ["informational", "low", "medium", "high", "critical"] as const;

export const INCIDENT_STATUSES = [
  "new",
  "triaged",
  "investigating",
  "contained",
  "resolved",
  "closed",
  "reopened",
] as const;

export type Severity = (typeof SEVERITIES)[number];
export type IncidentStatus = (typeof INCIDENT_STATUSES)[number];
