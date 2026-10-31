export type Vacancy = {
  title: string
  company: string | null
  location: string | null
  url: string
  score: number
  reason: string
  source_site: string
  description?: string | null
  seen_before: boolean
  applied: boolean
}

export type SearchResponse = {
  provider: 'ai_job_search' | 'site_crawler'
  vacancies: Vacancy[]
  warnings: string[]
}

export type ResumeSnapshot = {
  uploaded: boolean
  original_filename: string | null
  content_type: string | null
  size_bytes: number | null
  extracted_characters: number | null
  preview: string | null
  uploaded_at: string | null
}

export type CompatibilityGap = {
  requirement: string
  importance: 'critical' | 'high' | 'meaningful' | 'preferred' | 'low_signal'
  match: 'strong' | 'partial' | 'missing' | 'not_applicable'
  evidence: string
  recommendation: string
}

export type CompatibilityResult = {
  score: number
  decision: 'apply' | 'consider' | 'research' | 'skip'
  summary: string
  strengths: string[]
  gaps: CompatibilityGap[]
  improvements: string[]
  risks: string[]
  keywords: string[]
  report_path: string | null
}

export type CompatibilityReport = {
  id: string
  vacancy: Vacancy
  mode: 'quick' | 'full'
  result: CompatibilityResult
  created_at: string
  content: string | null
}

export type TailoredResumeBlock = {
  title: string
  content: string
}

export type TailoredResume = {
  id: string
  report_id: string
  blocks: TailoredResumeBlock[]
  created_at: string
}

export type CoverLetter = {
  id: string
  report_id: string
  content: string
  created_at: string
  updated_at: string
}

