import type { SearchResponse } from './types'

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

