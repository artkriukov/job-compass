import type { SearchResponse, Vacancy } from './types'

export const UNKNOWN_COMPANY = 'Компания не указана'

export function parseLines(value: string): string[] {
  return [...new Set(value.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean))]
}

export function mergeSearchResponses(responses: SearchResponse[]): SearchResponse {
  const byUrl = new Map<string, Vacancy>()
  for (const response of responses) {
    for (const vacancy of response.vacancies) {
      const current = byUrl.get(vacancy.url)
      if (!current || vacancy.score > current.score) byUrl.set(vacancy.url, vacancy)
    }
  }

  return {
    provider: responses.every((response) => response.provider === 'ai_job_search')
      ? 'ai_job_search'
      : 'site_crawler',
    vacancies: [...byUrl.values()].sort((left, right) => right.score - left.score),
    warnings: [...new Set(responses.flatMap((response) => response.warnings))],
  }
}

export function getVacancyCompany(vacancy: Vacancy): string {
  return vacancy.company?.trim() || UNKNOWN_COMPANY
}

export function getVacancyCompanies(vacancies: Vacancy[]): string[] {
  return [...new Set(vacancies.map(getVacancyCompany))]
    .sort((left, right) => left.localeCompare(right, 'ru'))
}

export function filterVacanciesByCompany(vacancies: Vacancy[], company: string): Vacancy[] {
  if (!company) return vacancies
  return vacancies.filter((vacancy) => getVacancyCompany(vacancy) === company)
}

