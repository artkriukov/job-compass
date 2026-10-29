import type { SearchResponse } from './types'
import type { SearchSettings } from './search-settings'

type SearchPayload = {
  sites: string[]
  role: string
  include_keywords: string[]
  exclude_keywords: string[]
}

export async function searchVacancies(
  payload: SearchPayload,
  signal: AbortSignal,
): Promise<SearchResponse> {
  const response = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Ошибка сервера: ${response.status}`)
  }
  return response.json() as Promise<SearchResponse>
}

type SettingsPayload = {
  sites: SearchSettings['sites']
  roles: SearchSettings['roles']
  include_keywords: string[]
  exclude_keywords: string[]
}

function fromSettingsPayload(payload: SettingsPayload): SearchSettings {
  return {
    sites: payload.sites,
    roles: payload.roles,
    includeKeywords: payload.include_keywords,
    excludeKeywords: payload.exclude_keywords,
  }
}

function toSettingsPayload(settings: SearchSettings): SettingsPayload {
  return {
    sites: settings.sites,
    roles: settings.roles,
    include_keywords: settings.includeKeywords,
    exclude_keywords: settings.excludeKeywords,
  }
}

export async function getRemoteSearchSettings(signal: AbortSignal): Promise<SearchSettings> {
  const response = await fetch('/api/settings', { signal })
  if (!response.ok) throw new Error(`Хранилище настроек недоступно: ${response.status}`)
  return fromSettingsPayload(await response.json() as SettingsPayload)
}

export async function saveRemoteSearchSettings(settings: SearchSettings): Promise<void> {
  const response = await fetch('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(toSettingsPayload(settings)),
  })
  if (!response.ok) throw new Error(`Не удалось сохранить настройки: ${response.status}`)
}

