import { describe, expect, it } from 'vitest'
import {
  filterVacanciesByCompany,
  getVacancyCompanies,
  matchesSelectionSearch,
  mergeSearchResponses,
  parseLines,
  UNKNOWN_COMPANY,
} from './form-utils'

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

describe('company vacancy filters', () => {
  const vacancies = [
    {
      title: 'Support engineer', company: 'Яндекс', location: null,
      url: 'https://example.test/jobs/1', score: 90, reason: 'Support',
      source_site: 'https://example.test/jobs',
    },
    {
      title: 'Service desk engineer', company: 'МТС', location: null,
      url: 'https://example.test/jobs/2', score: 80, reason: 'Service Desk',
      source_site: 'https://example.test/jobs',
    },
    {
      title: 'Technical specialist', company: null, location: null,
      url: 'https://example.test/jobs/3', score: 70, reason: 'Technical support',
      source_site: 'https://example.test/jobs',
    },
  ]

  it('returns unique sorted company options including an unknown company', () => {
    expect(getVacancyCompanies([...vacancies, { ...vacancies[0], url: 'https://example.test/jobs/4' }]))
      .toEqual([UNKNOWN_COMPANY, 'МТС', 'Яндекс'])
  })

  it('filters vacancies by the selected company and returns all without a selection', () => {
    expect(filterVacanciesByCompany(vacancies, 'МТС').map((vacancy) => vacancy.url))
      .toEqual(['https://example.test/jobs/2'])
    expect(filterVacanciesByCompany(vacancies, '')).toBe(vacancies)
  })
})

describe('matchesSelectionSearch', () => {
  const site = { label: 'Яндекс', meta: 'yandex.ru' }

  it('matches a site by company name or domain', () => {
    expect(matchesSelectionSearch(site, 'янд')).toBe(true)
    expect(matchesSelectionSearch(site, 'YANDEX.RU')).toBe(true)
    expect(matchesSelectionSearch(site, 'сбер')).toBe(false)
  })
})

