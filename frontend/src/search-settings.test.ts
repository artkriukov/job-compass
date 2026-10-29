import { describe, expect, it } from 'vitest'
import { EMPTY_SEARCH_SETTINGS, parseSearchSettings } from './search-settings'

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
