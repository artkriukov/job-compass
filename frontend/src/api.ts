import type { CompatibilityReport, CompatibilityResult, CoverLetter, ResumeSnapshot, SearchResponse, TailoredResume } from './types'
import type { SearchSettings } from './search-settings'
import type { JobApplication } from './applications'
import type { Vacancy } from './types'

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

export async function importVacancy(url: string): Promise<Vacancy> {
  const response = await fetch('/api/vacancies/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Не удалось добавить вакансию: ${response.status}`)
  }
  return response.json() as Promise<Vacancy>
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

type ApplicationPayload = {
  id: string
  company: string
  vacancy_title: string
  vacancy_url: string
  hr_url: string
  stage: JobApplication['stage']
  created_at: string
  updated_at: string
}

function fromApplicationPayload(payload: ApplicationPayload): JobApplication {
  return {
    id: payload.id,
    company: payload.company,
    vacancyTitle: payload.vacancy_title,
    vacancyUrl: payload.vacancy_url,
    hrUrl: payload.hr_url,
    stage: payload.stage,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
  }
}

export async function getRemoteApplications(signal: AbortSignal): Promise<JobApplication[]> {
  const response = await fetch('/api/applications', { signal })
  if (!response.ok) throw new Error(`Хранилище откликов недоступно: ${response.status}`)
  return (await response.json() as ApplicationPayload[]).map(fromApplicationPayload)
}

export async function createRemoteApplication(vacancy: Vacancy): Promise<JobApplication> {
  const response = await fetch('/api/applications', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: vacancy.title,
      company: vacancy.company ?? 'Компания не указана',
      location: vacancy.location,
      vacancy_url: vacancy.url,
      source_site: vacancy.source_site,
    }),
  })
  if (!response.ok) throw new Error(`Не удалось сохранить отклик: ${response.status}`)
  return fromApplicationPayload(await response.json() as ApplicationPayload)
}

export async function updateRemoteApplication(
  id: string,
  changes: Partial<Pick<JobApplication, 'stage' | 'hrUrl'>>,
): Promise<JobApplication> {
  const response = await fetch(`/api/applications/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stage: changes.stage, hr_url: changes.hrUrl }),
  })
  if (!response.ok) throw new Error(`Не удалось обновить отклик: ${response.status}`)
  return fromApplicationPayload(await response.json() as ApplicationPayload)
}

export async function deleteRemoteApplication(id: string): Promise<void> {
  const response = await fetch(`/api/applications/${id}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(`Не удалось удалить отклик: ${response.status}`)
}

export async function getResume(): Promise<ResumeSnapshot> {
  const response = await fetch('/api/career-ops/resume')
  if (!response.ok) throw new Error(`Не удалось получить сведения о резюме: ${response.status}`)
  return response.json() as Promise<ResumeSnapshot>
}

export async function uploadResume(file: File): Promise<ResumeSnapshot> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch('/api/career-ops/resume', {
    method: 'POST',
    body: formData,
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Не удалось загрузить резюме: ${response.status}`)
  }
  return response.json() as Promise<ResumeSnapshot>
}

export async function checkCompatibility(
  vacancy: Vacancy,
  targetRoles: string[],
  mode: 'quick' | 'full' = 'quick',
): Promise<CompatibilityResult> {
  const response = await fetch('/api/career-ops/compatibility', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vacancy, target_roles: targetRoles, mode }),
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Не удалось проверить совместимость: ${response.status}`)
  }
  return response.json() as Promise<CompatibilityResult>
}

export async function getCompatibilityReports(
  signal: AbortSignal,
): Promise<CompatibilityReport[]> {
  const response = await fetch('/api/career-ops/reports', { signal })
  if (!response.ok) throw new Error(`Не удалось загрузить отчёты: ${response.status}`)
  return response.json() as Promise<CompatibilityReport[]>
}

export async function createTailoredResume(reportId: string): Promise<TailoredResume> {
  const response = await fetch('/api/career-ops/tailored-resume', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_id: reportId }),
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Не удалось адаптировать резюме: ${response.status}`)
  }
  return response.json() as Promise<TailoredResume>
}

export async function createCoverLetter(reportId: string): Promise<CoverLetter> {
  const response = await fetch('/api/career-ops/cover-letter', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_id: reportId }),
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Не удалось написать сопроводительное письмо: ${response.status}`)
  }
  return response.json() as Promise<CoverLetter>
}

export async function updateCoverLetter(reportId: string, content: string): Promise<CoverLetter> {
  const response = await fetch(`/api/career-ops/cover-letter/${encodeURIComponent(reportId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Не удалось сохранить сопроводительное письмо: ${response.status}`)
  }
  return response.json() as Promise<CoverLetter>
}

