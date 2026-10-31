import type { CompatibilityReport } from './types'

export function compatibilityPlainText(value: string): string {
  return value
    .replace(/\[([^\]]+)]\(https?:\/\/[^)]+\)/g, '$1')
    .replace(/[*_`]/g, '')
    .trim()
}

export function findCompatibilityReport(
  reports: CompatibilityReport[],
  vacancyUrl: string,
  mode: CompatibilityReport['mode'],
): CompatibilityReport | null {
  return reports.find((report) => report.vacancy.url === vacancyUrl && report.mode === mode) ?? null
}
