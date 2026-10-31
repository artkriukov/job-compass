import { describe, expect, it } from 'vitest'
import { compatibilityPlainText, findCompatibilityReport } from './compatibility'
import type { CompatibilityReport } from './types'

describe('compatibilityPlainText', () => {
  it('removes markdown formatting from Career Ops prose', () => {
    expect(compatibilityPlainText('**Skip.** [Вакансия активна](https://example.com/job).'))
      .toBe('Skip. Вакансия активна.')
  })
})

describe('findCompatibilityReport', () => {
  it('finds the newly saved report for the same vacancy and analysis mode', () => {
    const report = {
      id: 'report-1',
      vacancy: { url: 'https://example.com/jobs/1' },
      mode: 'quick',
    } as CompatibilityReport

    expect(findCompatibilityReport([report], 'https://example.com/jobs/1', 'quick')).toBe(report)
    expect(findCompatibilityReport([report], 'https://example.com/jobs/1', 'full')).toBeNull()
  })
})
