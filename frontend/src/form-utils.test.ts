import { describe, expect, it } from 'vitest'
import { parseLines } from './form-utils'

describe('parseLines', () => {
  it('parses new lines, commas and removes duplicates', () => {
    expect(parseLines('https://a.test/jobs\nhttps://b.test, https://a.test/jobs')).toEqual([
      'https://a.test/jobs',
      'https://b.test',
    ])
  })
})

