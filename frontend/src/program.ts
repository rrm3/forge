/**
 * AI Tuesdays 12-week program constants and helpers.
 * Mirrors backend/models.py: PROGRAM_START_DATE, get_program_week(), intake_title(), wrapup_title().
 *
 * The canonical program week comes from the backend profile response (program_week field).
 * setProgramWeekOverride() is called once on profile load so that helpers like
 * intakeTitle() and wrapupTitle() use the backend-computed value (which respects
 * per-user overrides for testing).
 */

export const PROGRAM_START_DATE = new Date('2026-03-24T00:00:00');
export const PROGRAM_WEEKS = 12;

/** Per-user override set from profile.program_week on load. */
let _weekOverride: number | null = null;

/** Called once when the profile loads to sync the frontend with the backend's week. */
export function setProgramWeekOverride(week: number) {
  _weekOverride = week > 0 ? week : null;
}

export function getProgramWeek(asOf?: Date): number {
  if (_weekOverride !== null) return _weekOverride;
  const d = asOf ?? new Date();
  const daysElapsed = Math.floor(
    (d.getTime() - PROGRAM_START_DATE.getTime()) / (1000 * 60 * 60 * 24)
  );
  const week = Math.max(1, Math.floor(daysElapsed / 7) + 1);
  return Math.min(week, PROGRAM_WEEKS);
}

export function intakeTitle(week?: number): string {
  const w = week ?? getProgramWeek();
  return `Day ${w} Getting Started`;
}

export function wrapupTitle(week?: number): string {
  const w = week ?? getProgramWeek();
  return `Day ${w} Wrap-up`;
}
