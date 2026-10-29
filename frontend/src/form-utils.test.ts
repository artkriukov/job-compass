import { describe, expect, it } from 'vitest'
import { mergeSearchResponses, parseLines } from './form-utils'

describe('parseLines', () => {
  it('parses new lines, commas and removes duplicates', () => {
    expect(parseLines('https://a.test/jobs\nhttps://b.test, https://a.test/jobs')).toEqual([
      'https://a.test/jobs',
      'https://b.test',
    ])
  })
})

describe('mergeSearchResponses', () => {
  it('deduplicates vacancies and keeps the highest score', () => {
    const vacancy = {
      title: 'Python developer', company: 'Acme', location: null,
      url: 'https://example.test/jobs/1', score: 60, reason: 'Python',
      source_site: 'https://example.test/jobs',
    }
    const result = mergeSearchResponses([
      { provider: 'site_crawler', vacancies: [vacancy], warnings: ['warning'] },
      { provider: 'site_crawler', vacancies: [{ ...vacancy, score: 90 }], warnings: ['warning'] },
    ])
    expect(result.vacancies).toHaveLength(1)
    expect(result.vacancies[0].score).toBe(90)
    expect(result.warnings).toEqual(['warning'])
  })
})

