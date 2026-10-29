import { useState } from 'react'
import type { FormEvent } from 'react'
import { searchVacancies } from './api'
import { parseLines } from './form-utils'
import {
  loadSearchSettings,
  saveSearchSettings,
  type CareerSite,
  type SavedRole,
  type SearchSettings,
} from './search-settings'
import type { SearchResponse, Vacancy } from './types'
import './styles.css'

type Page = 'search' | 'settings'

function createId(): string {
  return crypto.randomUUID()
}

function normalizeUrl(value: string): string | null {
  try {
    const url = new URL(value.trim())
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : null
  } catch {
    return null
  }
}

function VacancyCard({ vacancy }: { vacancy: Vacancy }) {
  return (
    <article className="vacancy-card">
      <div className="score" aria-label={`Совпадение ${vacancy.score} процентов`}>{vacancy.score}</div>
      <div className="vacancy-body">
        <div className="vacancy-meta">
          <span>{vacancy.company ?? 'Компания не указана'}</span>
          {vacancy.location ? <span>{vacancy.location}</span> : null}
        </div>
        <h3>{vacancy.title}</h3>
        <p>{vacancy.reason}</p>
        <a href={vacancy.url} target="_blank" rel="noreferrer">Открыть вакансию <span aria-hidden="true">↗</span></a>
      </div>
    </article>
  )
}

function Results({ result }: { result: SearchResponse }) {
  return (
    <section className="results" aria-live="polite">
      <div className="results-heading">
        <div><p className="eyebrow">Результаты</p><h2>Найдено: {result.vacancies.length}</h2></div>
        <span className="provider">{result.provider === 'ai_job_search' ? 'AI Job Search + Codex' : 'Поиск по карьерному сайту'}</span>
      </div>
      {result.warnings.length > 0 ? <div className="warnings" role="status">{result.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div> : null}
      {result.vacancies.length > 0 ? (
        <div className="vacancy-list">{result.vacancies.map((vacancy) => <VacancyCard key={vacancy.url} vacancy={vacancy} />)}</div>
      ) : (
        <div className="empty-state"><h3>Подходящих вакансий пока нет</h3><p>Попробуйте другую должность или уберите часть исключений.</p></div>
      )}
    </section>
  )
}

type SettingsPageProps = {
  settings: SearchSettings
  onChange: (settings: SearchSettings) => void
  onOpenSearch: () => void
}

function SettingsPage({ settings, onChange, onOpenSearch }: SettingsPageProps) {
  const [siteName, setSiteName] = useState('')
  const [siteUrl, setSiteUrl] = useState('')
  const [editingSiteId, setEditingSiteId] = useState<string | null>(null)
  const [roleTitle, setRoleTitle] = useState('')
  const [editingRoleId, setEditingRoleId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [siteFormOpen, setSiteFormOpen] = useState(false)
  const [roleFormOpen, setRoleFormOpen] = useState(false)

  function resetSiteForm() {
    setSiteName('')
    setSiteUrl('')
    setEditingSiteId(null)
    setSiteFormOpen(false)
  }

  function handleSiteSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedUrl = normalizeUrl(siteUrl)
    if (!normalizedUrl) {
      setError('Введите полный адрес сайта, начиная с http:// или https://')
      return
    }
    if (settings.sites.some((site) => site.url === normalizedUrl && site.id !== editingSiteId)) {
      setError('Этот карьерный сайт уже сохранён.')
      return
    }
    const site: CareerSite = { id: editingSiteId ?? createId(), name: siteName.trim(), url: normalizedUrl }
    const sites = editingSiteId
      ? settings.sites.map((item) => item.id === editingSiteId ? site : item)
      : [...settings.sites, site]
    onChange({ ...settings, sites })
    setError(null)
    resetSiteForm()
  }

  function editSite(site: CareerSite) {
    setSiteName(site.name)
    setSiteUrl(site.url)
    setEditingSiteId(site.id)
    setSiteFormOpen(true)
    setError(null)
  }

  function handleRoleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const title = roleTitle.trim()
    if (settings.roles.some((role) => role.title.toLowerCase() === title.toLowerCase() && role.id !== editingRoleId)) {
      setError('Такая должность уже сохранена.')
      return
    }
    const role: SavedRole = { id: editingRoleId ?? createId(), title }
    const roles = editingRoleId
      ? settings.roles.map((item) => item.id === editingRoleId ? role : item)
      : [...settings.roles, role]
    onChange({ ...settings, roles })
    setRoleTitle('')
    setEditingRoleId(null)
    setRoleFormOpen(false)
    setError(null)
  }

  return (
    <div className="page-content">
      <section className="page-heading">
        <p className="eyebrow">Постоянные настройки</p>
        <h1>Источники и должности</h1>
        <p className="lede">Сохраните карьерные страницы компаний и варианты должностей один раз. Затем собирайте из них поиск за несколько кликов.</p>
      </section>
      {error ? <p className="error page-error" role="alert">{error}</p> : null}

      <div className="settings-grid">
        <section className="collection-panel" aria-labelledby="sites-title">
          <div className="section-heading">
            <div><span>01</span><div><h2 id="sites-title">Карьерные сайты</h2><p>{settings.sites.length} сохранено</p></div></div>
            <button type="button" className={siteFormOpen ? 'add-toggle open' : 'add-toggle'} onClick={() => { if (siteFormOpen) resetSiteForm(); else setSiteFormOpen(true) }} aria-expanded={siteFormOpen} aria-label={siteFormOpen ? 'Закрыть форму сайта' : 'Добавить карьерный сайт'}>+</button>
          </div>
          {siteFormOpen ? <form className="compact-form site-form" onSubmit={handleSiteSubmit}>
            <label className="field"><span>Название компании</span><input value={siteName} onChange={(event) => setSiteName(event.target.value)} placeholder="Например: Яндекс" required /></label>
            <label className="field"><span>Ссылка на вакансии</span><input value={siteUrl} onChange={(event) => setSiteUrl(event.target.value)} placeholder="https://company.ru/jobs" inputMode="url" required /></label>
            <div className="form-actions">
              <button type="submit" className="primary-button">{editingSiteId ? 'Сохранить изменения' : 'Добавить сайт'} <span>→</span></button>
              {editingSiteId ? <button type="button" className="text-button" onClick={resetSiteForm}>Отмена</button> : null}
            </div>
          </form> : null}
          <div className="saved-list">
            {settings.sites.length === 0 ? <p className="list-empty">Пока нет сохранённых сайтов.</p> : settings.sites.map((site) => (
              <article className="saved-item" key={site.id}>
                <div className="saved-icon">{site.name.slice(0, 2).toUpperCase()}</div>
                <div className="saved-copy"><h3>{site.name}</h3><a href={site.url} target="_blank" rel="noreferrer">{site.url}</a></div>
                <div className="item-actions">
                  <button type="button" className="item-button" onClick={() => editSite(site)}>Редактировать</button>
                  <button type="button" className="item-button danger" onClick={() => onChange({ ...settings, sites: settings.sites.filter((item) => item.id !== site.id) })}>Удалить</button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="collection-panel" aria-labelledby="roles-title">
          <div className="section-heading">
            <div><span>02</span><div><h2 id="roles-title">Искомые должности</h2><p>{settings.roles.length} сохранено</p></div></div>
            <button type="button" className={roleFormOpen ? 'add-toggle open' : 'add-toggle'} onClick={() => { setRoleFormOpen((open) => !open); if (roleFormOpen) { setEditingRoleId(null); setRoleTitle('') } }} aria-expanded={roleFormOpen} aria-label={roleFormOpen ? 'Закрыть форму должности' : 'Добавить должность'}>+</button>
          </div>
          {roleFormOpen ? <form className="compact-form role-form" onSubmit={handleRoleSubmit}>
            <label className="field"><span>Название должности</span><input value={roleTitle} onChange={(event) => setRoleTitle(event.target.value)} placeholder="Python backend developer" minLength={2} required /></label>
            <div className="form-actions">
              <button type="submit" className="primary-button">{editingRoleId ? 'Сохранить изменения' : 'Добавить должность'} <span>→</span></button>
              {editingRoleId ? <button type="button" className="text-button" onClick={() => { setEditingRoleId(null); setRoleTitle(''); setRoleFormOpen(false) }}>Отмена</button> : null}
            </div>
          </form> : null}
          <div className="saved-list roles-list">
            {settings.roles.length === 0 ? <p className="list-empty">Добавьте один или несколько вариантов должности.</p> : settings.roles.map((role) => (
              <article className="saved-item saved-role" key={role.id}>
                <div className="saved-icon role-icon">{role.title.slice(0, 2).toUpperCase()}</div>
                <div className="saved-copy"><h3>{role.title}</h3><p>Вариант поискового запроса</p></div>
                <div className="item-actions">
                  <button type="button" className="item-button" onClick={() => { setEditingRoleId(role.id); setRoleTitle(role.title); setRoleFormOpen(true); setError(null) }}>Редактировать</button>
                  <button type="button" className="item-button danger" onClick={() => onChange({ ...settings, roles: settings.roles.filter((item) => item.id !== role.id) })}>Удалить</button>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section className="ready-banner">
        <div><p className="eyebrow">Следующий шаг</p><h2>Настройки сохраняются в этом браузере</h2><p>Перейдите к поиску и выберите нужные сайты и должность.</p></div>
        <button type="button" className="primary-button banner-button" onClick={onOpenSearch}>Перейти к поиску <span>→</span></button>
      </section>
    </div>
  )
}

type SearchPageProps = {
  settings: SearchSettings
  selectedSiteIds: string[]
  setSelectedSiteIds: (ids: string[]) => void
  selectedRoleId: string
  setSelectedRoleId: (id: string) => void
  onOpenSettings: () => void
}

function SearchPage({ settings, selectedSiteIds, setSelectedSiteIds, selectedRoleId, setSelectedRoleId, onOpenSettings }: SearchPageProps) {
  const [include, setInclude] = useState('')
  const [exclude, setExclude] = useState('')
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const selectedRole = settings.roles.find((role) => role.id === selectedRoleId)

  function toggleSite(id: string) {
    setSelectedSiteIds(selectedSiteIds.includes(id) ? selectedSiteIds.filter((siteId) => siteId !== id) : [...selectedSiteIds, id])
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setResult(null)
    const sites = settings.sites.filter((site) => selectedSiteIds.includes(site.id)).map((site) => site.url)
    if (sites.length === 0 || !selectedRole) {
      setError('Выберите хотя бы один сайт и одну должность.')
      return
    }
    const controller = new AbortController()
    setLoading(true)
    try {
      const data = await searchVacancies({ sites, role: selectedRole.title, include_keywords: parseLines(include), exclude_keywords: parseLines(exclude) }, controller.signal)
      setResult(data)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось выполнить поиск.')
    } finally {
      setLoading(false)
    }
  }

  const hasSettings = settings.sites.length > 0 && settings.roles.length > 0
  return (
    <div className="page-content">
      <section className="page-heading search-heading"><p className="eyebrow">Поиск вакансий</p><h1>Соберите новый поиск.</h1><p className="lede">Выберите сохранённые источники и должность, добавьте фильтры и запустите поиск.</p></section>
      {!hasSettings ? (
        <section className="onboarding-card"><span>Нужны исходные данные</span><h2>Сначала добавьте сайты и должности</h2><p>Они сохранятся в браузере и будут доступны для следующих поисков.</p><button type="button" className="primary-button" onClick={onOpenSettings}>Открыть настройки <span>→</span></button></section>
      ) : (
        <section className="search-workspace">
          <div className="search-summary"><p className="eyebrow">Ваши данные</p><h2>{settings.sites.length} {settings.sites.length === 1 ? 'сайт' : 'сайтов'} · {settings.roles.length} {settings.roles.length === 1 ? 'должность' : 'должностей'}</h2><p>Настройки можно изменить в любой момент.</p><button type="button" className="text-link" onClick={onOpenSettings}>Редактировать настройки →</button></div>
          <form className="search-form" onSubmit={handleSubmit}>
            <fieldset>
              <legend>Где искать <b>*</b></legend>
              <div className="choice-list">
                {settings.sites.map((site) => (
                  <label className="choice-card" key={site.id}><input type="checkbox" checked={selectedSiteIds.includes(site.id)} onChange={() => toggleSite(site.id)} /><span><strong>{site.name}</strong><small>{new URL(site.url).hostname}</small></span></label>
                ))}
              </div>
            </fieldset>
            <label className="field"><span>Должность <b>*</b></span><select value={selectedRoleId} onChange={(event) => setSelectedRoleId(event.target.value)} required><option value="">Выберите должность</option>{settings.roles.map((role) => <option value={role.id} key={role.id}>{role.title}</option>)}</select></label>
            <div className="field-row">
              <label className="field"><span>Ключевые слова</span><input value={include} onChange={(event) => setInclude(event.target.value)} placeholder="remote, FastAPI" /><small>Через запятую</small></label>
              <label className="field"><span>Исключить</span><input value={exclude} onChange={(event) => setExclude(event.target.value)} placeholder="senior, relocation" /><small>Через запятую</small></label>
            </div>
            {error ? <p className="error" role="alert">{error}</p> : null}
            <button type="submit" className="primary-button search-button" disabled={loading}>{loading ? <><span className="spinner" /> Ищем вакансии…</> : <>Найти вакансии <span>→</span></>}</button>
          </form>
        </section>
      )}
      {result ? <Results result={result} /> : null}
    </div>
  )
}

export default function App() {
  const [page, setPage] = useState<Page>('search')
  const [settings, setSettings] = useState<SearchSettings>(loadSearchSettings)
  const [selectedSiteIds, setSelectedSiteIds] = useState<string[]>(() => settings.sites.map((site) => site.id))
  const [selectedRoleId, setSelectedRoleId] = useState(() => settings.roles[0]?.id ?? '')

  function updateSettings(nextSettings: SearchSettings) {
    setSettings(nextSettings)
    saveSearchSettings(nextSettings)
    setSelectedSiteIds((current) => current.filter((id) => nextSettings.sites.some((site) => site.id === id)))
    if (!nextSettings.roles.some((role) => role.id === selectedRoleId)) setSelectedRoleId(nextSettings.roles[0]?.id ?? '')
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <button type="button" className="brand" onClick={() => setPage('search')} aria-label="Job Compass — поиск"><span className="brand-mark">JC</span><span>Job Compass</span></button>
        <nav aria-label="Основная навигация">
          <button type="button" className={page === 'search' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('search')}><span aria-hidden="true">⌕</span><span>Поиск вакансий</span></button>
          <button type="button" className={page === 'settings' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('settings')}><span aria-hidden="true">◫</span><span>Источники и должности</span></button>
        </nav>
        <div className="sidebar-status"><i /><div><strong>Работает локально</strong><span>Данные остаются у вас</span></div></div>
      </aside>
      <main className="main-area">
        <header className="mobile-topbar"><button type="button" className="brand" onClick={() => setPage('search')}><span className="brand-mark">JC</span><span>Job Compass</span></button></header>
        {page === 'settings' ? <SettingsPage settings={settings} onChange={updateSettings} onOpenSearch={() => setPage('search')} /> : <SearchPage settings={settings} selectedSiteIds={selectedSiteIds} setSelectedSiteIds={setSelectedSiteIds} selectedRoleId={selectedRoleId} setSelectedRoleId={setSelectedRoleId} onOpenSettings={() => setPage('settings')} />}
        <footer><span>Job Compass</span><p>Собирает ссылки. Решение об отклике всегда остаётся за вами.</p></footer>
      </main>
    </div>
  )
}
