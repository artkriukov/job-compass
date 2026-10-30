import { describe, expect, it } from 'vitest'
import {
  EMPTY_SEARCH_SELECTION,
  EMPTY_SEARCH_SETTINGS,
  filterCareerSites,
  getCareerSiteHostname,
  parseSearchSelection,
  parseSearchSettings,
} from './search-settings'

const sites = [
  { id: 'site-1', name: 'Яндекс', url: 'https://yandex.ru/jobs' },
  { id: 'site-2', name: 'Cloud.ru', url: 'https://career.cloud.ru/vacancies' },
]

describe('career site search', () => {
  it('matches sites by company name or hostname', () => {
    expect(filterCareerSites(sites, 'янд')).toEqual([sites[0]])
    expect(filterCareerSites(sites, 'career.cloud')).toEqual([sites[1]])
    expect(filterCareerSites(sites, '  ')).toBe(sites)
  })

  it('formats hostnames for display', () => {
    expect(getCareerSiteHostname('https://www.example.com/jobs')).toBe('example.com')
  })
})

describe('parseSearchSettings', () => {
  it('loads valid versioned settings', () => {
    expect(parseSearchSettings(JSON.stringify({
      version: 1,
      sites: [{ id: 'site-1', name: 'Яндекс', url: 'https://yandex.ru/jobs' }],
      roles: [{ id: 'role-1', title: 'Python developer' }],
      includeKeywords: ['Remote', 'Linux'],
      excludeKeywords: ['Senior'],
    }))).toEqual({
      sites: [{ id: 'site-1', name: 'Яндекс', url: 'https://yandex.ru/jobs' }],
      roles: [{ id: 'role-1', title: 'Python developer' }],
      includeKeywords: ['remote', 'linux'],
      excludeKeywords: ['senior'],
    })
  })

  it('returns empty settings for corrupt or unsupported data', () => {
    expect(parseSearchSettings('{broken')).toEqual(EMPTY_SEARCH_SETTINGS)
    expect(parseSearchSettings(JSON.stringify({ version: 2 }))).toEqual(EMPTY_SEARCH_SETTINGS)
  })

  it('drops invalid list entries', () => {
    expect(parseSearchSettings(JSON.stringify({
      version: 1,
      sites: [{ id: '', name: 'Bad', url: 'https://bad.test' }],
      roles: [{ id: 'good', title: 'Data analyst' }, { id: 'bad', title: '' }],
    }))).toEqual({
      sites: [], roles: [{ id: 'good', title: 'Data analyst' }],
      includeKeywords: [], excludeKeywords: [],
    })
  })
})

describe('parseSearchSelection', () => {
  it('loads a versioned saved search selection', () => {
    expect(parseSearchSelection(JSON.stringify({
      version: 1,
      siteIds: ['site-1', 'site-2'],
      roleIds: ['role-1'],
      includeKeywords: ['Linux'],
      excludeKeywords: ['Продажи'],
    }))).toEqual({
      siteIds: ['site-1', 'site-2'],
      roleIds: ['role-1'],
      includeKeywords: ['linux'],
      excludeKeywords: ['продажи'],
    })
  })

  it('returns an empty selection for corrupt or unsupported data', () => {
    expect(parseSearchSelection('{broken')).toEqual(EMPTY_SEARCH_SELECTION)
    expect(parseSearchSelection(JSON.stringify({ version: 2 }))).toEqual(EMPTY_SEARCH_SELECTION)
  })
})
