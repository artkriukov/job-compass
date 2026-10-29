export type CareerSite = {
  id: string
  name: string
  url: string
}

export type SavedRole = {
  id: string
  title: string
}

export type SearchSettings = {
  sites: CareerSite[]
  roles: SavedRole[]
  includeKeywords: string[]
  excludeKeywords: string[]
}

type StoredSearchSettings = SearchSettings & {
  version: 1
}

export const SEARCH_SETTINGS_KEY = 'job-compass.search-settings.v1'

export const EMPTY_SEARCH_SETTINGS: SearchSettings = {
  sites: [],
  roles: [],
  includeKeywords: [],
  excludeKeywords: [],
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function cleanStringList(value: unknown): string[] {
  return Array.isArray(value)
    ? [...new Set(value.filter(isNonEmptyString).map((item) => item.trim().toLowerCase()))]
    : []
}

export function parseSearchSettings(value: string | null): SearchSettings {
  if (!value) return EMPTY_SEARCH_SETTINGS

  try {
    const parsed = JSON.parse(value) as Partial<StoredSearchSettings>
    if (parsed.version !== 1 || !Array.isArray(parsed.sites) || !Array.isArray(parsed.roles)) {
      return EMPTY_SEARCH_SETTINGS
    }

    const sites = parsed.sites.filter(
      (site): site is CareerSite =>
        typeof site === 'object' &&
        site !== null &&
        isNonEmptyString(site.id) &&
        isNonEmptyString(site.name) &&
        isNonEmptyString(site.url),
    )
    const roles = parsed.roles.filter(
      (role): role is SavedRole =>
        typeof role === 'object' &&
        role !== null &&
        isNonEmptyString(role.id) &&
        isNonEmptyString(role.title),
    )
    return {
      sites,
      roles,
      includeKeywords: cleanStringList(parsed.includeKeywords),
      excludeKeywords: cleanStringList(parsed.excludeKeywords),
    }
  } catch {
    return EMPTY_SEARCH_SETTINGS
  }
}

export function loadSearchSettings(): SearchSettings {
  return parseSearchSettings(window.localStorage.getItem(SEARCH_SETTINGS_KEY))
}

export function saveSearchSettings(settings: SearchSettings): void {
  const stored: StoredSearchSettings = { version: 1, ...settings }
  window.localStorage.setItem(SEARCH_SETTINGS_KEY, JSON.stringify(stored))
}
