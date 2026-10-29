import { useState } from 'react'
import type { FormEvent } from 'react'
import { searchVacancies } from './api'
import { parseLines } from './form-utils'
import type { SearchResponse, Vacancy } from './types'
import './styles.css'

const EXAMPLE_SITES = [
  'https://boards.greenhouse.io/example',
  'https://jobs.lever.co/example',
].join('\n')

function VacancyCard({ vacancy }: { vacancy: Vacancy }) {
  return (
    <article className="vacancy-card">
      <div className="score" aria-label={`Совпадение ${vacancy.score} процентов`}>
        {vacancy.score}
      </div>
      <div className="vacancy-body">
        <div className="vacancy-meta">
          <span>{vacancy.company ?? 'Компания не указана'}</span>
          {vacancy.location && <span>{vacancy.location}</span>}
        </div>
        <h3>{vacancy.title}</h3>
        <p>{vacancy.reason}</p>
        <a href={vacancy.url} target="_blank" rel="noreferrer">
          Открыть вакансию <span aria-hidden="true">↗</span>
        </a>
      </div>
    </article>
  )
}

function Results({ result }: { result: SearchResponse }) {
  return (
    <section className="results" aria-live="polite">
      <div className="results-heading">
        <div>
          <p className="eyebrow">Результаты</p>
          <h2>Найдено: {result.vacancies.length}</h2>
        </div>
        <span className="provider">
          {result.provider === 'ai_job_search'
            ? 'AI Job Search + Codex'
            : 'Поиск по карьерному сайту'}
        </span>
      </div>

      {result.warnings.length > 0 && (
        <div className="warnings" role="status">
          {result.warnings.map((warning) => <p key={warning}>{warning}</p>)}
        </div>
      )}

      {result.vacancies.length > 0 ? (
        <div className="vacancy-list">
          {result.vacancies.map((vacancy) => <VacancyCard key={vacancy.url} vacancy={vacancy} />)}
        </div>
      ) : (
        <div className="empty-state">
          <h3>Подходящих вакансий пока нет</h3>
          <p>Попробуйте сделать название должности короче или убрать часть исключений.</p>
        </div>
      )}
    </section>
  )
}

export default function App() {
  const [sites, setSites] = useState('')
  const [role, setRole] = useState('')
  const [include, setInclude] = useState('')
  const [exclude, setExclude] = useState('')
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setResult(null)

    const parsedSites = parseLines(sites)
    if (parsedSites.length === 0) {
      setError('Добавьте хотя бы один карьерный сайт.')
      return
    }

    const controller = new AbortController()
    setLoading(true)
    try {
      const data = await searchVacancies({
        sites: parsedSites,
        role: role.trim(),
        include_keywords: parseLines(include),
        exclude_keywords: parseLines(exclude),
      }, controller.signal)
      setResult(data)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось выполнить поиск.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Job Compass — на главную">
          <span className="brand-mark">JC</span>
          <span>Job Compass</span>
        </a>
        <span className="local-badge"><i /> Работает локально</span>
      </header>

      <div className="shell" id="top">
        <section className="intro">
          <p className="eyebrow">Ваш радар вакансий</p>
          <h1>Ищите там, где хотите работать.</h1>
          <p className="lede">
            Укажите карьерные страницы компаний и примерную должность. Job Compass соберёт
            релевантные вакансии и прямые ссылки в одном отчёте.
          </p>
        </section>

        <section className="search-panel" aria-labelledby="search-title">
          <div className="panel-heading">
            <span>01</span>
            <div>
              <h2 id="search-title">Настройте поиск</h2>
              <p>До 20 публичных карьерных страниц за один запуск.</p>
            </div>
          </div>

          <form onSubmit={handleSubmit}>
            <label className="field field-wide">
              <span>Сайты компаний <b>*</b></span>
              <textarea
                value={sites}
                onChange={(event) => setSites(event.target.value)}
                placeholder={EXAMPLE_SITES}
                rows={5}
                required
              />
              <small>Один адрес в строке или через запятую</small>
            </label>

            <label className="field field-wide">
              <span>Примерная должность <b>*</b></span>
              <input
                value={role}
                onChange={(event) => setRole(event.target.value)}
                placeholder="Например: Python backend developer"
                minLength={2}
                required
              />
            </label>

            <div className="field-row">
              <label className="field">
                <span>Ключевые слова</span>
                <input
                  value={include}
                  onChange={(event) => setInclude(event.target.value)}
                  placeholder="remote, FastAPI"
                />
                <small>Необязательно</small>
              </label>
              <label className="field">
                <span>Исключить</span>
                <input
                  value={exclude}
                  onChange={(event) => setExclude(event.target.value)}
                  placeholder="senior, relocation"
                />
                <small>Необязательно</small>
              </label>
            </div>

            {error && <p className="error" role="alert">{error}</p>}

            <button type="submit" disabled={loading}>
              {loading ? <><span className="spinner" /> Ищем вакансии…</> : <>Начать поиск <span>→</span></>}
            </button>
          </form>
        </section>

        {result && <Results result={result} />}
      </div>

      <footer>
        <span>Job Compass</span>
        <p>Собирает ссылки. Решение об отклике всегда остаётся за вами.</p>
      </footer>
    </main>
  )
}

