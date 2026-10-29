import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { getRemoteSearchSettings, saveRemoteSearchSettings, searchVacancies } from './api'
import { mergeSearchResponses } from './form-utils'
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

function EditIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4l10.5-10.5a2.8 2.8 0 0 0-4-4L4 16v4Z" /><path d="m13.5 6.5 4 4" /></svg>
}

function TrashIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3m3 0-1 13H7L6 7m4 4v5m4-5v5" /></svg>
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
  const [filterFormOpen, setFilterFormOpen] = useState(false)
  const [includeKeyword, setIncludeKeyword] = useState('')
  const [excludeKeyword, setExcludeKeyword] = useState('')

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

  function handleIncludeKeywordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const keyword = includeKeyword.trim().toLowerCase()
    if (!keyword || settings.includeKeywords.includes(keyword)) return
    onChange({ ...settings, includeKeywords: [...settings.includeKeywords, keyword] })
    setIncludeKeyword('')
    setError(null)
  }

  function handleExcludeKeywordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const keyword = excludeKeyword.trim().toLowerCase()
    if (!keyword || settings.excludeKeywords.includes(keyword)) return
    onChange({ ...settings, excludeKeywords: [...settings.excludeKeywords, keyword] })
    setExcludeKeyword('')
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
            <div><h2 id="sites-title">Карьерные сайты</h2><p>{settings.sites.length} сохранено</p></div>
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
                <div className="saved-copy"><h3>{site.name}</h3></div>
                <div className="item-actions">
                  <button type="button" className="item-button" onClick={() => editSite(site)} aria-label={`Редактировать ${site.name}`} title="Редактировать"><EditIcon /></button>
                  <button type="button" className="item-button danger" onClick={() => onChange({ ...settings, sites: settings.sites.filter((item) => item.id !== site.id) })} aria-label={`Удалить ${site.name}`} title="Удалить"><TrashIcon /></button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="collection-panel" aria-labelledby="roles-title">
          <div className="section-heading">
            <div><h2 id="roles-title">Искомые должности</h2><p>{settings.roles.length} сохранено</p></div>
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
                <div className="saved-copy"><h3>{role.title}</h3></div>
                <div className="item-actions">
                  <button type="button" className="item-button" onClick={() => { setEditingRoleId(role.id); setRoleTitle(role.title); setRoleFormOpen(true); setError(null) }} aria-label={`Редактировать ${role.title}`} title="Редактировать"><EditIcon /></button>
                  <button type="button" className="item-button danger" onClick={() => onChange({ ...settings, roles: settings.roles.filter((item) => item.id !== role.id) })} aria-label={`Удалить ${role.title}`} title="Удалить"><TrashIcon /></button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="collection-panel" aria-labelledby="filters-title">
          <div className="section-heading">
            <div><h2 id="filters-title">Ключевые слова и исключения</h2><p>{settings.includeKeywords.length + settings.excludeKeywords.length} сохранено</p></div>
            <button type="button" className={filterFormOpen ? 'add-toggle open' : 'add-toggle'} onClick={() => setFilterFormOpen((open) => !open)} aria-expanded={filterFormOpen} aria-label={filterFormOpen ? 'Закрыть настройки фильтров' : 'Настроить фильтры'}>+</button>
          </div>
          {filterFormOpen ? <div className="compact-form filter-form">
            <form className="keyword-add-form" onSubmit={handleIncludeKeywordSubmit}>
              <label className="field"><span>Добавить ключевое слово или фразу</span><input value={includeKeyword} onChange={(event) => setIncludeKeyword(event.target.value)} placeholder="Например: Service Desk" required /></label>
              <button type="submit" className="primary-button">Добавить <span>+</span></button>
            </form>
            <form className="keyword-add-form" onSubmit={handleExcludeKeywordSubmit}>
              <label className="field"><span>Добавить слово-исключение</span><input value={excludeKeyword} onChange={(event) => setExcludeKeyword(event.target.value)} placeholder="Например: продажи" required /></label>
              <button type="submit" className="primary-button">Добавить <span>+</span></button>
            </form>
          </div> : null}
          <div className="filter-summary">
            <div><strong>Ключевые слова</strong><div className="keyword-list">{settings.includeKeywords.length > 0 ? settings.includeKeywords.map((keyword) => <span key={keyword}>{keyword}<button type="button" onClick={() => onChange({ ...settings, includeKeywords: settings.includeKeywords.filter((item) => item !== keyword) })} aria-label={`Удалить ${keyword}`}>×</button></span>) : <em>Не заданы</em>}</div></div>
            <div><strong>Исключения</strong><div className="keyword-list exclusions">{settings.excludeKeywords.length > 0 ? settings.excludeKeywords.map((keyword) => <span key={keyword}>{keyword}<button type="button" onClick={() => onChange({ ...settings, excludeKeywords: settings.excludeKeywords.filter((item) => item !== keyword) })} aria-label={`Удалить ${keyword}`}>×</button></span>) : <em>Не заданы</em>}</div></div>
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
  selectedRoleIds: string[]
  setSelectedRoleIds: (ids: string[]) => void
  selectedIncludeKeywords: string[]
  setSelectedIncludeKeywords: (keywords: string[]) => void
  selectedExcludeKeywords: string[]
  setSelectedExcludeKeywords: (keywords: string[]) => void
  onOpenSettings: () => void
}

type SelectionItem = { id: string; label: string; meta?: string }

function SelectionDropdown({ label, items, selectedIds, open, onOpenChange, onToggle }: { label: string; items: SelectionItem[]; selectedIds: string[]; open: boolean; onOpenChange: () => void; onToggle: (id: string) => void }) {
  return (
    <fieldset className="selection-field" onClick={(event) => event.stopPropagation()}>
      <legend>{label} <b>*</b></legend>
      <div className={open ? 'multi-select open' : 'multi-select'}>
        <button type="button" className="multi-select-trigger" onClick={onOpenChange} aria-expanded={open}><span>{selectedIds.length > 0 ? `Выбрано: ${selectedIds.length}` : 'Ничего не выбрано'}</span><i aria-hidden="true">⌄</i></button>
        {open ? <div className="multi-select-menu">
          {items.map((item) => (
            <label className="multi-option" key={item.id}>
              <input type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => onToggle(item.id)} />
              <span><strong>{item.label}</strong>{item.meta ? <small>{item.meta}</small> : null}</span>
            </label>
          ))}
        </div> : null}
      </div>
    </fieldset>
  )
}

function SearchPage({ settings, selectedSiteIds, setSelectedSiteIds, selectedRoleIds, setSelectedRoleIds, selectedIncludeKeywords, setSelectedIncludeKeywords, selectedExcludeKeywords, setSelectedExcludeKeywords, onOpenSettings }: SearchPageProps) {
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [openDropdown, setOpenDropdown] = useState<'sites' | 'roles' | 'include' | 'exclude' | null>(null)

  function toggleSelection(ids: string[], id: string): string[] {
    return ids.includes(id) ? ids.filter((itemId) => itemId !== id) : [...ids, id]
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setResult(null)
    const sites = settings.sites.filter((site) => selectedSiteIds.includes(site.id)).map((site) => site.url)
    const roles = settings.roles.filter((role) => selectedRoleIds.includes(role.id))
    if (sites.length === 0 || roles.length === 0) {
      setError('Выберите хотя бы один сайт и одну должность.')
      return
    }
    const controller = new AbortController()
    setLoading(true)
    try {
      const responses = await Promise.all(roles.map((role) => searchVacancies({ sites, role: role.title, include_keywords: selectedIncludeKeywords, exclude_keywords: selectedExcludeKeywords }, controller.signal)))
      setResult(mergeSearchResponses(responses))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось выполнить поиск.')
    } finally {
      setLoading(false)
    }
  }

  const hasSettings = settings.sites.length > 0 && settings.roles.length > 0
  return (
    <div className="page-content" onClick={() => setOpenDropdown(null)}>
      <section className="page-heading search-heading"><p className="eyebrow">Поиск вакансий</p><h1>Соберите новый поиск.</h1><p className="lede">Выберите сохранённые источники и должность, добавьте фильтры и запустите поиск.</p></section>
      {!hasSettings ? (
        <section className="onboarding-card"><span>Нужны исходные данные</span><h2>Сначала добавьте сайты и должности</h2><p>Они сохранятся в браузере и будут доступны для следующих поисков.</p><button type="button" className="primary-button" onClick={onOpenSettings}>Открыть настройки <span>→</span></button></section>
      ) : (
        <section className="search-workspace">
          <form className="search-form" onSubmit={handleSubmit}>
            <div className="selection-row">
              <SelectionDropdown label="Где искать" items={settings.sites.map((site) => ({ id: site.id, label: site.name, meta: new URL(site.url).hostname }))} selectedIds={selectedSiteIds} open={openDropdown === 'sites'} onOpenChange={() => setOpenDropdown((current) => current === 'sites' ? null : 'sites')} onToggle={(id) => setSelectedSiteIds(toggleSelection(selectedSiteIds, id))} />
              <SelectionDropdown label="Должности" items={settings.roles.map((role) => ({ id: role.id, label: role.title }))} selectedIds={selectedRoleIds} open={openDropdown === 'roles'} onOpenChange={() => setOpenDropdown((current) => current === 'roles' ? null : 'roles')} onToggle={(id) => setSelectedRoleIds(toggleSelection(selectedRoleIds, id))} />
            </div>
            <div className="selection-row filter-selection-row">
              <SelectionDropdown label="Ключевые слова" items={settings.includeKeywords.map((keyword) => ({ id: keyword, label: keyword }))} selectedIds={selectedIncludeKeywords} open={openDropdown === 'include'} onOpenChange={() => setOpenDropdown((current) => current === 'include' ? null : 'include')} onToggle={(keyword) => setSelectedIncludeKeywords(toggleSelection(selectedIncludeKeywords, keyword))} />
              <SelectionDropdown label="Исключения" items={settings.excludeKeywords.map((keyword) => ({ id: keyword, label: keyword }))} selectedIds={selectedExcludeKeywords} open={openDropdown === 'exclude'} onOpenChange={() => setOpenDropdown((current) => current === 'exclude' ? null : 'exclude')} onToggle={(keyword) => setSelectedExcludeKeywords(toggleSelection(selectedExcludeKeywords, keyword))} />
            </div>
            {error ? <p className="error" role="alert">{error}</p> : null}
            <button type="submit" className="primary-button search-button" disabled={loading}>{loading ? <><span className="spinner" /> Ищем по выбранным должностям…</> : <>Найти вакансии <span>→</span></>}</button>
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
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>(() => settings.roles.map((role) => role.id))
  const [selectedIncludeKeywords, setSelectedIncludeKeywords] = useState<string[]>(() => settings.includeKeywords)
  const [selectedExcludeKeywords, setSelectedExcludeKeywords] = useState<string[]>(() => settings.excludeKeywords)

  useEffect(() => {
    const controller = new AbortController()
    const localSettings = loadSearchSettings()
    const localHasData = localSettings.sites.length > 0 || localSettings.roles.length > 0 ||
      localSettings.includeKeywords.length > 0 || localSettings.excludeKeywords.length > 0

    void getRemoteSearchSettings(controller.signal)
      .then((remoteSettings) => {
        const remoteHasData = remoteSettings.sites.length > 0 || remoteSettings.roles.length > 0 ||
          remoteSettings.includeKeywords.length > 0 || remoteSettings.excludeKeywords.length > 0
        if (!remoteHasData && localHasData) {
          return saveRemoteSearchSettings(localSettings)
        }
        setSettings(remoteSettings)
        saveSearchSettings(remoteSettings)
        setSelectedSiteIds(remoteSettings.sites.map((site) => site.id))
        setSelectedRoleIds(remoteSettings.roles.map((role) => role.id))
        setSelectedIncludeKeywords(remoteSettings.includeKeywords)
        setSelectedExcludeKeywords(remoteSettings.excludeKeywords)
      })
      .catch(() => undefined)

    return () => controller.abort()
  }, [])

  function updateSettings(nextSettings: SearchSettings) {
    setSettings(nextSettings)
    saveSearchSettings(nextSettings)
    void saveRemoteSearchSettings(nextSettings).catch(() => undefined)
    setSelectedSiteIds((current) => current.filter((id) => nextSettings.sites.some((site) => site.id === id)))
    setSelectedRoleIds((current) => current.filter((id) => nextSettings.roles.some((role) => role.id === id)))
    setSelectedIncludeKeywords(nextSettings.includeKeywords)
    setSelectedExcludeKeywords(nextSettings.excludeKeywords)
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
        {page === 'settings' ? <SettingsPage settings={settings} onChange={updateSettings} onOpenSearch={() => setPage('search')} /> : <SearchPage settings={settings} selectedSiteIds={selectedSiteIds} setSelectedSiteIds={setSelectedSiteIds} selectedRoleIds={selectedRoleIds} setSelectedRoleIds={setSelectedRoleIds} selectedIncludeKeywords={selectedIncludeKeywords} setSelectedIncludeKeywords={setSelectedIncludeKeywords} selectedExcludeKeywords={selectedExcludeKeywords} setSelectedExcludeKeywords={setSelectedExcludeKeywords} onOpenSettings={() => setPage('settings')} />}
        <footer><span>Job Compass</span><p>Собирает ссылки. Решение об отклике всегда остаётся за вами.</p></footer>
      </main>
    </div>
  )
}
