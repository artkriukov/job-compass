import { describe, expect, it } from 'vitest'
import { compatibilityPlainText } from './compatibility'

describe('compatibilityPlainText', () => {
  it('removes markdown formatting from Career Ops prose', () => {
    expect(compatibilityPlainText('**Skip.** [Вакансия активна](https://example.com/job).'))
      .toBe('Skip. Вакансия активна.')
  })
})
