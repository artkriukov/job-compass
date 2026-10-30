import { describe, expect, it } from 'vitest'
import { addVacancyApplication, parseApplications, updateApplication } from './applications'

const vacancy = {
  title: 'Инженер поддержки', company: 'Яндекс', location: null,
  url: 'https://example.test/jobs/1', score: 90, reason: 'Подходит',
  source_site: 'https://example.test/jobs',
  seen_before: false, applied: false,
}

describe('application storage', () => {
  it('adds a vacancy once with the initial review stage', () => {
    const added = addVacancyApplication([], vacancy, 'application-1', '2026-10-29T12:00:00.000Z')
    expect(added[0]).toMatchObject({
      id: 'application-1', company: 'Яндекс', vacancyTitle: 'Инженер поддержки',
      stage: 'review', hrUrl: '',
    })
    expect(addVacancyApplication(added, vacancy, 'application-2', '2026-10-29T13:00:00.000Z')).toBe(added)
  })

  it('updates a stage and HR link', () => {
    const added = addVacancyApplication([], vacancy, 'application-1', '2026-10-29T12:00:00.000Z')
    expect(updateApplication(added, 'application-1', {
      stage: 'hr_interview', hrUrl: 'https://t.me/recruiter',
    }, '2026-10-29T13:00:00.000Z')[0]).toMatchObject({
      stage: 'hr_interview', hrUrl: 'https://t.me/recruiter', updatedAt: '2026-10-29T13:00:00.000Z',
    })
  })

  it('rejects corrupt storage data', () => {
    expect(parseApplications('{broken')).toEqual([])
    expect(parseApplications(JSON.stringify({ version: 2, applications: [] }))).toEqual([])
  })

  it('keeps valid stored applications and drops invalid entries', () => {
    const added = addVacancyApplication([], vacancy, 'application-1', '2026-10-29T12:00:00.000Z')
    const parsed = parseApplications(JSON.stringify({
      version: 1,
      applications: [...added, { ...added[0], id: '', stage: 'unknown' }],
    }))

    expect(parsed).toEqual(added)
  })
})
