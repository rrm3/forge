/**
 * AI Tuesdays 12-week program constants and helpers.
 * Mirrors backend/models.py: PROGRAM_START_DATE, get_program_week(), intake_title(), wrapup_title().
 */

export const PROGRAM_START_DATE = new Date('2026-03-24T00:00:00');
export const PROGRAM_WEEKS = 12;

export function getProgramWeek(asOf?: Date): number {
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
