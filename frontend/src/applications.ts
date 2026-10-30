import type { Vacancy } from './types'

export const APPLICATION_STAGES = [
  { value: 'review', label: 'На рассмотрении' },
  { value: 'hr_interview', label: 'Собеседование с HR' },
  { value: 'technical_interview', label: 'Техническое собеседование' },
  { value: 'offer', label: 'Офер' },
] as const

export type ApplicationStage = typeof APPLICATION_STAGES[number]['value']

export type JobApplication = {
  id: string
  company: string
  vacancyTitle: string
  vacancyUrl: string
  hrUrl: string
  stage: ApplicationStage
  createdAt: string
  updatedAt: string
}

type StoredApplications = {
  version: 1
  applications: JobApplication[]
}

export const APPLICATIONS_KEY = 'job-compass.applications.v1'

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function isApplicationStage(value: unknown): value is ApplicationStage {
  return APPLICATION_STAGES.some((stage) => stage.value === value)
}

export function parseApplications(value: string | null): JobApplication[] {
  if (!value) return []

  try {
    const parsed = JSON.parse(value) as Partial<StoredApplications>
    if (parsed.version !== 1 || !Array.isArray(parsed.applications)) return []
    return parsed.applications.filter((application): application is JobApplication =>
      typeof application === 'object' && application !== null &&
      isNonEmptyString(application.id) &&
      isNonEmptyString(application.company) &&
      isNonEmptyString(application.vacancyTitle) &&
      isNonEmptyString(application.vacancyUrl) &&
      typeof application.hrUrl === 'string' &&
      isApplicationStage(application.stage) &&
      isNonEmptyString(application.createdAt) &&
      isNonEmptyString(application.updatedAt),
    )
  } catch {
    return []
  }
}

export function loadApplications(): JobApplication[] {
  return parseApplications(window.localStorage.getItem(APPLICATIONS_KEY))
}

export function saveApplications(applications: JobApplication[]): void {
  window.localStorage.setItem(APPLICATIONS_KEY, JSON.stringify({ version: 1, applications }))
}

export function addVacancyApplication(
  applications: JobApplication[],
  vacancy: Vacancy,
  id: string,
  now: string,
): JobApplication[] {
  if (applications.some((application) => application.vacancyUrl === vacancy.url)) return applications
  return [{
    id,
    company: vacancy.company?.trim() || 'Компания не указана',
    vacancyTitle: vacancy.title,
    vacancyUrl: vacancy.url,
    hrUrl: '',
    stage: 'review',
    createdAt: now,
    updatedAt: now,
  }, ...applications]
}

export function updateApplication(
  applications: JobApplication[],
  id: string,
  changes: Partial<Pick<JobApplication, 'stage' | 'hrUrl'>>,
  now: string,
): JobApplication[] {
  return applications.map((application) => application.id === id
    ? { ...application, ...changes, updatedAt: now }
    : application)
}
