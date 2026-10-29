export type Vacancy = {
  title: string
  company: string | null
  location: string | null
  url: string
  score: number
  reason: string
  source_site: string
}

export type SearchResponse = {
  provider: 'ai_job_search' | 'site_crawler'
  vacancies: Vacancy[]
  warnings: string[]
}

