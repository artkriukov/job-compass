import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import {
  createRemoteApplication,
  createCoverLetter,
  createTailoredResume,
  checkCompatibility,
  deleteRemoteApplication,
  getCompatibilityReports,
  getRemoteApplications,
  getRemoteSearchSettings,
  getResume,
  importVacancy,
  saveRemoteSearchSettings,
  searchVacancies,
  uploadResume,
  updateRemoteApplication,
  updateCoverLetter,
} from './api'
import {
  addVacancyApplication,
  APPLICATION_STAGES,
  loadApplications,
  saveApplications,
  updateApplication,
  type ApplicationStage,
  type JobApplication,
} from './applications'
import {
  filterVacanciesByCompany,
  getVacancyCompanies,
  matchesSelectionSearch,
  mergeSearchResponses,
} from './form-utils'
import {
  filterCareerSites,
  getCareerSiteHostname,
  loadSearchSettings,
  loadSearchSelection,
  saveSearchSelection,
  saveSearchSettings,
  type CareerSite,
  type SavedRole,
  type SearchSettings,
} from './search-settings'
import type { CompatibilityReport, CompatibilityResult, CoverLetter, ResumeSnapshot, SearchResponse, TailoredResume, Vacancy } from './types'
import { compatibilityPlainText, findCompatibilityReport } from './compatibility'
import './styles.css'

type Page = 'search' | 'applications' | 'reports' | 'resume' | 'settings'
type SettingsSection = 'sites' | 'roles' | 'keywords'

const SETTINGS_SECTIONS: SettingsSection[] = ['sites', 'roles', 'keywords']

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

type SingleSelectOption = {
  value: string
  label: string
  meta?: string | number
}

function SingleSelect({ ariaLabel, className = '', value, options, open, disabled = false, onOpenChange, onChange }: {
  ariaLabel: string
  className?: string
  value: string
  options: SingleSelectOption[]
  open: boolean
  disabled?: boolean
  onOpenChange: (open: boolean) => void
  onChange: (value: string) => void
}) {
  const menuId = useId()
  const selectedOption = options.find((option) => option.value === value)

  return (
    <div className={`${open ? 'single-select open' : 'single-select'} ${className}`.trim()} onClick={(event) => event.stopPropagation()}>
      <button
        type="button"
        className="single-select-trigger"
        disabled={disabled}
        onClick={() => onOpenChange(!open)}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
      >
        <span>{selectedOption?.label ?? 'Ничего не выбрано'}</span>
        <i aria-hidden="true">⌄</i>
      </button>
      {open ? (
        <div className="single-select-menu" id={menuId} role="listbox" aria-label={ariaLabel}>
          {options.map((option) => {
            const selected = option.value === value
            return (
              <button
                type="button"
                className={selected ? 'single-select-option selected' : 'single-select-option'}
                key={option.value}
                role="option"
                aria-selected={selected}
                onClick={() => {
                  onChange(option.value)
                  onOpenChange(false)
                }}
              >
                <span>{option.label}</span>
                <i aria-hidden="true">{option.meta ?? (selected ? '✓' : '')}</i>
              </button>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}

function VacancyCard({ vacancy, report, applied, checking, onApply, onCheck, onOpenReport }: { vacancy: Vacancy; report: CompatibilityReport | null; applied: boolean; checking: boolean; onApply: (vacancy: Vacancy) => void; onCheck: (vacancy: Vacancy) => void; onOpenReport: (report: CompatibilityReport) => void }) {
  return (
    <article className="vacancy-card">
      <div className="score" aria-label={`Совпадение ${vacancy.score} процентов`}>{vacancy.score}</div>
      <div className="vacancy-body">
        <div className="vacancy-meta">
          <span>{vacancy.company ?? 'Компания не указана'}</span>
          {vacancy.location ? <span>{vacancy.location}</span> : null}
        </div>
        <div className="vacancy-badges">
          {vacancy.seen_before ? <span className="vacancy-badge seen">Уже просмотрена</span> : <span className="vacancy-badge new">Новая</span>}
          {vacancy.applied || applied ? <span className="vacancy-badge applied">Вы откликнулись</span> : null}
          {report ? <span className="vacancy-badge report-ready">Отчёт {report.result.score.toFixed(1)}/5</span> : null}
        </div>
        <h3>{vacancy.title}</h3>
        <p>{vacancy.reason}</p>
        <div className="vacancy-actions">
          <a href={vacancy.url} target="_blank" rel="noreferrer">Открыть вакансию <span aria-hidden="true">↗</span></a>
          <div className="vacancy-action-buttons">
            {report
              ? <button type="button" className="compatibility-button report-available" onClick={() => onOpenReport(report)}>Посмотреть отчёт</button>
              : <button type="button" className="compatibility-button" disabled={checking} onClick={() => onCheck(vacancy)}>{checking ? <><span className="spinner" /> Анализируем…</> : 'Проверить совместимость'}</button>}
            <button type="button" className={applied ? 'application-button applied' : 'application-button'} disabled={applied} onClick={() => onApply(vacancy)}>{applied ? 'Отклик добавлен ✓' : 'Я откликнулся'}</button>
          </div>
        </div>
      </div>
    </article>
  )
}

function Results({ result, reports, applications, checkingUrl, onApply, onCheck, onOpenReport }: { result: SearchResponse; reports: CompatibilityReport[]; applications: JobApplication[]; checkingUrl: string | null; onApply: (vacancy: Vacancy) => void; onCheck: (vacancy: Vacancy) => void; onOpenReport: (report: CompatibilityReport) => void }) {
  const [selectedCompany, setSelectedCompany] = useState('')
  const [companyFilterOpen, setCompanyFilterOpen] = useState(false)
  const companies = getVacancyCompanies(result.vacancies)
  const visibleVacancies = filterVacanciesByCompany(result.vacancies, selectedCompany)
  const companyOptions: SingleSelectOption[] = [
    { value: '', label: 'Все компании', meta: result.vacancies.length },
    ...companies.map((company) => ({
      value: company,
      label: company,
      meta: filterVacanciesByCompany(result.vacancies, company).length,
    })),
  ]

  return (
    <section className="results" aria-live="polite" onClick={() => setCompanyFilterOpen(false)}>
      <div className="results-heading">
        <div>
          <p className="eyebrow">Результаты</p>
          <h2>{selectedCompany ? `Показано: ${visibleVacancies.length} из ${result.vacancies.length}` : `Найдено: ${result.vacancies.length}`}</h2>
        </div>
        <div className="results-controls">
          <div className="company-filter" onClick={(event) => event.stopPropagation()}>
            <span>Компания</span>
            <SingleSelect
              ariaLabel="Фильтр по компании"
              className="company-select"
              value={selectedCompany}
              options={companies.length > 0 ? companyOptions : [{ value: '', label: 'Нет найденных компаний' }]}
              open={companyFilterOpen}
              disabled={companies.length === 0}
              onOpenChange={setCompanyFilterOpen}
              onChange={setSelectedCompany}
            />
          </div>
          <span className="provider">{result.provider === 'ai_job_search' ? 'AI Job Search + Codex' : 'Поиск по карьерному сайту'}</span>
        </div>
      </div>
      {result.warnings.length > 0 ? <div className="warnings" role="status">{result.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div> : null}
      {visibleVacancies.length > 0 ? (
        <div className="vacancy-list">{visibleVacancies.map((vacancy) => <VacancyCard key={vacancy.url} vacancy={vacancy} report={reports.find((report) => report.vacancy.url === vacancy.url) ?? null} applied={applications.some((application) => application.vacancyUrl === vacancy.url)} checking={checkingUrl === vacancy.url} onApply={onApply} onCheck={onCheck} onOpenReport={onOpenReport} />)}</div>
      ) : (
        <div className="empty-state">
          <h3>{result.vacancies.length > 0 ? 'У этой компании вакансий не найдено' : 'Подходящих вакансий пока нет'}</h3>
          <p>{result.vacancies.length > 0 ? 'Выберите другую компанию или покажите все результаты.' : 'Попробуйте другую должность или уберите часть исключений.'}</p>
        </div>
      )}
    </section>
  )
}

const DECISION_LABELS: Record<CompatibilityResult['decision'], string> = {
  apply: 'Откликаться', consider: 'Рассмотреть', research: 'Сначала изучить', skip: 'Пропустить',
}

function CompatibilityDialog({ vacancy, report, result, mode, loading, error, document, onClose, onOpenResume, onRunFull }: { vacancy: Vacancy; report?: CompatibilityReport | null; result: CompatibilityResult | null; mode: 'quick' | 'full'; loading: boolean; error: string | null; document?: string | null; onClose: () => void; onOpenResume?: () => void; onRunFull?: () => void }) {
  const [tailoredResume, setTailoredResume] = useState<TailoredResume | null>(null)
  const [tailoring, setTailoring] = useState(false)
  const [tailoringError, setTailoringError] = useState<string | null>(null)
  const [coverLetter, setCoverLetter] = useState<CoverLetter | null>(null)
  const [writingLetter, setWritingLetter] = useState(false)
  const [savingLetter, setSavingLetter] = useState(false)
  const [letterDirty, setLetterDirty] = useState(false)
  const [letterError, setLetterError] = useState<string | null>(null)
  const [copiedBlock, setCopiedBlock] = useState<string | null>(null)
  const tailoredResumeRef = useRef<HTMLElement | null>(null)
  const coverLetterRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (tailoredResume) {
      tailoredResumeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [tailoredResume])

  useEffect(() => {
    if (coverLetter?.id) {
      coverLetterRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [coverLetter?.id])

  async function handleTailorResume() {
    if (!report) return
    if (tailoredResume) {
      tailoredResumeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      return
    }
    setTailoring(true)
    setTailoringError(null)
    try {
      setTailoredResume(await createTailoredResume(report.id))
    } catch (requestError) {
      setTailoringError(requestError instanceof Error ? requestError.message : 'Не удалось адаптировать резюме.')
    } finally {
      setTailoring(false)
    }
  }

  async function handleCreateCoverLetter() {
    if (!report) return
    if (coverLetter) {
      coverLetterRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      return
    }
    setWritingLetter(true)
    setLetterError(null)
    try {
      setCoverLetter(await createCoverLetter(report.id))
      setLetterDirty(false)
    } catch (requestError) {
      setLetterError(requestError instanceof Error ? requestError.message : 'Не удалось написать сопроводительное письмо.')
    } finally {
      setWritingLetter(false)
    }
  }

  async function handleSaveCoverLetter() {
    if (!report || !coverLetter) return
    setSavingLetter(true)
    setLetterError(null)
    try {
      setCoverLetter(await updateCoverLetter(report.id, coverLetter.content.trim()))
      setLetterDirty(false)
    } catch (requestError) {
      setLetterError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить сопроводительное письмо.')
    } finally {
      setSavingLetter(false)
    }
  }

  async function copyBlock(key: string, value: string) {
    try {
      await navigator.clipboard.writeText(value)
      setCopiedBlock(key)
      window.setTimeout(() => setCopiedBlock((current) => current === key ? null : current), 1800)
    } catch {
      const message = 'Браузер не разрешил копирование. Выделите текст вручную.'
      if (key === 'cover-letter') setLetterError(message)
      else setTailoringError(message)
    }
  }

  const fullResumeText = tailoredResume?.blocks
    .map((block) => `${block.title}\n${block.content}`)
    .join('\n\n') ?? ''

  return <div className="compatibility-backdrop" role="presentation" onMouseDown={onClose}>
    <section className="compatibility-dialog" role="dialog" aria-modal="true" aria-labelledby="compatibility-title" onMouseDown={(event) => event.stopPropagation()}>
      <button type="button" className="dialog-close" aria-label="Закрыть" onClick={onClose}>×</button>
      <p className="eyebrow">Career Ops · {mode === 'quick' ? 'быстрая проверка' : 'полный анализ'}</p>
      <h2 id="compatibility-title">{vacancy.title}</h2>
      <p className="dialog-company">{vacancy.company ?? 'Компания не указана'}</p>
      {loading ? <div className="compatibility-loading"><span className="spinner" /><strong>Сравниваем вакансию с резюме…</strong><p>{mode === 'quick' ? 'Используем уже извлечённый текст вакансии и компактный профиль. Обычно это занимает меньше минуты.' : 'Career Ops формирует полный отчёт A–G, трекер и черновик письма. Это может занять несколько минут.'}</p></div> : null}
      {error ? <div className="compatibility-error" role="alert"><p>{error}</p>{onOpenResume ? <button type="button" className="primary-button" onClick={onOpenResume}>Открыть резюме <span>→</span></button> : null}</div> : null}
      {result ? <div className="compatibility-content">
        <div className={`compatibility-score decision-${result.decision}`}><strong>{result.score.toFixed(1)}</strong><span>из 5</span><b>{DECISION_LABELS[result.decision]}</b></div>
        <p className="compatibility-summary">{compatibilityPlainText(result.summary)}</p>
        {report ? <section className="report-materials"><div><h3>Материалы для отклика</h3><p>Подготовим отдельные материалы под эту вакансию на основе подтверждённого опыта.</p></div><div className="report-material-actions"><button type="button" className="primary-button" disabled={tailoring} onClick={() => void handleTailorResume()}>{tailoring ? <><span className="spinner" /> Адаптируем…</> : tailoredResume ? 'Перейти к резюме ↓' : 'Адаптировать резюме'}</button><button type="button" className="secondary-button" disabled={writingLetter} onClick={() => void handleCreateCoverLetter()}>{writingLetter ? <><span className="spinner" /> Пишем…</> : coverLetter ? 'Перейти к письму ↓' : 'Написать сопроводительное'}</button></div>{tailoringError ? <p className="material-error" role="alert">{tailoringError}</p> : null}{letterError ? <p className="material-error" role="alert">{letterError}</p> : null}</section> : null}
        {tailoredResume ? <section className="tailored-resume" ref={tailoredResumeRef}><div className="tailored-resume-heading"><div><p className="eyebrow">Версия под вакансию</p><h3>Адаптированное резюме</h3></div><button type="button" className="copy-button" onClick={() => void copyBlock('all', fullResumeText)}>{copiedBlock === 'all' ? 'Скопировано ✓' : 'Скопировать всё'}</button></div><div className="tailored-resume-blocks">{tailoredResume.blocks.map((block, index) => { const key = `${index}-${block.title}`; return <article key={key}><header><h4>{block.title}</h4><button type="button" className="copy-button" onClick={() => void copyBlock(key, block.content)}>{copiedBlock === key ? 'Скопировано ✓' : 'Копировать'}</button></header><pre>{block.content}</pre></article> })}</div></section> : null}
        {coverLetter ? <section className="cover-letter" ref={coverLetterRef}><div className="tailored-resume-heading"><div><p className="eyebrow">Текст для отклика</p><h3>Сопроводительное письмо</h3></div><button type="button" className="copy-button" onClick={() => void copyBlock('cover-letter', coverLetter.content)}>{copiedBlock === 'cover-letter' ? 'Скопировано ✓' : 'Скопировать'}</button></div><textarea aria-label="Сопроводительное письмо" value={coverLetter.content} onChange={(event) => { setCoverLetter({ ...coverLetter, content: event.target.value }); setLetterDirty(true) }} /><div className="cover-letter-footer"><span>{letterDirty ? 'Есть несохранённые изменения' : 'Сохранено в отчёте'}</span><button type="button" className="primary-button" disabled={!letterDirty || savingLetter || coverLetter.content.trim().length < 100} onClick={() => void handleSaveCoverLetter()}>{savingLetter ? 'Сохраняем…' : 'Сохранить изменения'}</button></div></section> : null}
        {result.strengths.length ? <section><h3>Сильные стороны</h3><ul>{result.strengths.map((item) => <li key={item}>{compatibilityPlainText(item)}</li>)}</ul></section> : null}
        {result.gaps.length ? <section><h3>Пробелы и как их закрыть</h3><div className="compatibility-gaps">{result.gaps.map((gap) => <article key={`${gap.requirement}-${gap.match}`}><div><strong>{compatibilityPlainText(gap.requirement)}</strong><span className={`gap-match ${gap.match}`}>{gap.match === 'missing' ? 'Нет в резюме' : gap.match === 'partial' ? 'Частично' : gap.match === 'strong' ? 'Сильное совпадение' : 'Не применимо'}</span></div><p>{compatibilityPlainText(gap.evidence)}</p><small>{compatibilityPlainText(gap.recommendation)}</small></article>)}</div></section> : null}
        {result.improvements.length ? <section><h3>Что улучшить в резюме</h3><ol>{result.improvements.map((item) => <li key={item}>{compatibilityPlainText(item)}</li>)}</ol></section> : null}
        {result.risks.length ? <section><h3>Риски вакансии</h3><ul>{result.risks.map((item) => <li key={item}>{compatibilityPlainText(item)}</li>)}</ul></section> : null}
        {result.keywords.length ? <section><h3>Ключевые слова для ATS</h3><div className="compatibility-keywords">{result.keywords.map((item) => <span key={item}>{item}</span>)}</div></section> : null}
        {document ? <section className="compatibility-document"><h3>Полный отчёт Career Ops</h3><pre>{document}</pre></section> : null}
        {mode === 'quick' && onRunFull ? <section className="full-analysis-callout"><div><h3>Нужен полный отчёт?</h3><p>Career Ops добавит исследование компании, подробный отчёт A–G и черновик сопроводительного письма. Это отдельный тяжёлый запуск.</p></div><button type="button" className="primary-button" onClick={onRunFull}>Полный отчёт <span>→</span></button></section> : null}
      </div> : null}
    </section>
  </div>
}

type SettingsPageProps = {
  settings: SearchSettings
  onChange: (settings: SearchSettings) => void
  onOpenSearch: () => void
}

function SettingsPage({ settings, onChange, onOpenSearch }: SettingsPageProps) {
  const [settingsSection, setSettingsSection] = useState<SettingsSection>('sites')
  const [siteName, setSiteName] = useState('')
  const [siteUrl, setSiteUrl] = useState('')
  const [siteQuery, setSiteQuery] = useState('')
  const [openSiteMenuId, setOpenSiteMenuId] = useState<string | null>(null)
  const [confirmingSiteId, setConfirmingSiteId] = useState<string | null>(null)
  const [editingSiteId, setEditingSiteId] = useState<string | null>(null)
  const [roleTitle, setRoleTitle] = useState('')
  const [editingRoleId, setEditingRoleId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [siteFormOpen, setSiteFormOpen] = useState(false)
  const [roleFormOpen, setRoleFormOpen] = useState(false)
  const [filterFormOpen, setFilterFormOpen] = useState(false)
  const [includeKeyword, setIncludeKeyword] = useState('')
  const [excludeKeyword, setExcludeKeyword] = useState('')
  const visibleSites = filterCareerSites(settings.sites, siteQuery)

  function closeSiteMenu() {
    setOpenSiteMenuId(null)
    setConfirmingSiteId(null)
  }

  function selectSettingsSection(section: SettingsSection) {
    setSettingsSection(section)
    closeSiteMenu()
  }

  function handleSettingsTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, section: SettingsSection) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const currentIndex = SETTINGS_SECTIONS.indexOf(section)
    const nextIndex = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? SETTINGS_SECTIONS.length - 1
        : (currentIndex + (event.key === 'ArrowRight' ? 1 : -1) + SETTINGS_SECTIONS.length) % SETTINGS_SECTIONS.length
    const nextSection = SETTINGS_SECTIONS[nextIndex]
    selectSettingsSection(nextSection)
    document.getElementById(`settings-tab-${nextSection}`)?.focus()
  }

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
    closeSiteMenu()
  }

  function removeSite(siteId: string) {
    onChange({ ...settings, sites: settings.sites.filter((site) => site.id !== siteId) })
    closeSiteMenu()
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
    <div className="page-content" onClick={closeSiteMenu}>
      <section className="page-heading">
        <p className="eyebrow">Постоянные настройки</p>
        <h1>Источники и должности</h1>
        <p className="lede">Сохраните карьерные страницы компаний и варианты должностей один раз. Затем собирайте из них поиск за несколько кликов.</p>
      </section>
      {error ? <p className="error page-error" role="alert">{error}</p> : null}

      <div className="settings-tabs" role="tablist" aria-label="Разделы настроек">
        <button id="settings-tab-sites" type="button" role="tab" aria-selected={settingsSection === 'sites'} aria-controls="settings-panel-sites" className={settingsSection === 'sites' ? 'active' : ''} onClick={() => selectSettingsSection('sites')} onKeyDown={(event) => handleSettingsTabKeyDown(event, 'sites')}>Карьерные сайты <b>{settings.sites.length}</b></button>
        <button id="settings-tab-roles" type="button" role="tab" aria-selected={settingsSection === 'roles'} aria-controls="settings-panel-roles" className={settingsSection === 'roles' ? 'active' : ''} onClick={() => selectSettingsSection('roles')} onKeyDown={(event) => handleSettingsTabKeyDown(event, 'roles')}>Должности <b>{settings.roles.length}</b></button>
        <button id="settings-tab-keywords" type="button" role="tab" aria-selected={settingsSection === 'keywords'} aria-controls="settings-panel-keywords" className={settingsSection === 'keywords' ? 'active' : ''} onClick={() => selectSettingsSection('keywords')} onKeyDown={(event) => handleSettingsTabKeyDown(event, 'keywords')}>Ключевые слова <b>{settings.includeKeywords.length + settings.excludeKeywords.length}</b></button>
      </div>

      <div className="settings-grid">
        {settingsSection === 'sites' ? <section id="settings-panel-sites" className="collection-panel sites-panel" role="tabpanel" aria-labelledby="settings-tab-sites">
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
          {settings.sites.length > 0 ? <div className="site-toolbar">
            <label className="site-search">
              <span aria-hidden="true">⌕</span>
              <input type="search" name="site-search" value={siteQuery} onChange={(event) => setSiteQuery(event.target.value)} placeholder="Найти по названию или домену…" autoComplete="off" spellCheck={false} aria-label="Поиск карьерных сайтов" />
              {siteQuery ? <button type="button" onClick={() => setSiteQuery('')} aria-label="Очистить поиск">×</button> : null}
            </label>
            <span className="site-search-summary" aria-live="polite">Показано: {visibleSites.length} из {settings.sites.length}</span>
          </div> : null}
          <div className="saved-list sites-list">
            {settings.sites.length === 0 ? <p className="list-empty">Пока нет сохранённых сайтов.</p> : visibleSites.length === 0 ? <div className="list-empty"><p>По запросу «{siteQuery.trim()}» ничего не найдено.</p><button type="button" className="text-button" onClick={() => setSiteQuery('')}>Очистить поиск</button></div> : visibleSites.map((site) => (
              <article className="saved-item saved-site" key={site.id}>
                <div className="saved-icon">{site.name.slice(0, 2).toUpperCase()}</div>
                <div className="saved-copy"><h3 title={site.name}>{site.name}</h3><small title={getCareerSiteHostname(site.url)}>{getCareerSiteHostname(site.url)}</small></div>
                <div className="site-actions" onClick={(event) => event.stopPropagation()}>
                  <button type="button" className="site-menu-trigger" onClick={() => { setOpenSiteMenuId((current) => current === site.id ? null : site.id); setConfirmingSiteId(null) }} aria-label={`Действия для ${site.name}`} aria-haspopup="menu" aria-expanded={openSiteMenuId === site.id}>⋯</button>
                  {openSiteMenuId === site.id ? confirmingSiteId === site.id ? <div className="site-actions-menu site-delete-confirm" role="dialog" aria-label={`Удалить ${site.name}?`} onKeyDown={(event) => { if (event.key === 'Escape') closeSiteMenu() }}>
                    <strong>Удалить сайт?</strong>
                    <p>«{site.name}» исчезнет из сохранённых источников.</p>
                    <div><button type="button" className="site-menu-action" onClick={closeSiteMenu}>Отмена</button><button type="button" className="site-menu-action danger" onClick={() => removeSite(site.id)}>Удалить</button></div>
                  </div> : <div className="site-actions-menu" role="menu" onKeyDown={(event) => { if (event.key === 'Escape') closeSiteMenu() }}>
                    <button type="button" className="site-menu-action" role="menuitem" onClick={() => editSite(site)}><EditIcon /><span>Редактировать</span></button>
                    <button type="button" className="site-menu-action danger" role="menuitem" onClick={() => setConfirmingSiteId(site.id)}><TrashIcon /><span>Удалить</span></button>
                  </div> : null}
                </div>
              </article>
            ))}
          </div>
        </section> : null}

        {settingsSection === 'roles' ? <section id="settings-panel-roles" className="collection-panel" role="tabpanel" aria-labelledby="settings-tab-roles">
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
        </section> : null}

        {settingsSection === 'keywords' ? <section id="settings-panel-keywords" className="collection-panel" role="tabpanel" aria-labelledby="settings-tab-keywords">
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
        </section> : null}
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
  applications: JobApplication[]
  onApply: (vacancy: Vacancy) => void
  onOpenSettings: () => void
  onOpenResume: () => void
}

type SelectionItem = { id: string; label: string; meta?: string }

function SelectionDropdown({ label, items, selectedIds, open, onOpenChange, onToggle, searchable = false }: { label: string; items: SelectionItem[]; selectedIds: string[]; open: boolean; onOpenChange: () => void; onToggle: (id: string) => void; searchable?: boolean }) {
  const [query, setQuery] = useState('')
  const activeQuery = open ? query : ''
  const visibleItems = searchable ? items.filter((item) => matchesSelectionSearch(item, activeQuery)) : items

  return (
    <fieldset className="selection-field" onClick={(event) => event.stopPropagation()}>
      <legend>{label} <b>*</b></legend>
      <div className={open ? 'multi-select open' : 'multi-select'}>
        <button type="button" className="multi-select-trigger" onClick={onOpenChange} aria-expanded={open}><span>{selectedIds.length > 0 ? `Выбрано: ${selectedIds.length}` : 'Ничего не выбрано'}</span><i aria-hidden="true">⌄</i></button>
        {open ? <div className={searchable ? 'multi-select-menu searchable' : 'multi-select-menu'}>
          {searchable ? <label className="selection-search">
            <span aria-hidden="true">⌕</span>
            <input value={activeQuery} onChange={(event) => setQuery(event.target.value)} placeholder="Найти компанию…" autoFocus />
            {activeQuery ? <button type="button" onClick={() => setQuery('')} aria-label="Очистить поиск">×</button> : null}
          </label> : null}
          <div className="multi-options-scroll">
            {visibleItems.length > 0 ? visibleItems.map((item) => (
              <label className="multi-option" key={item.id}>
                <input type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => onToggle(item.id)} />
                <span><strong>{item.label}</strong>{item.meta ? <small>{item.meta}</small> : null}</span>
              </label>
            )) : <p className="selection-empty">Ничего не найдено</p>}
          </div>
        </div> : null}
      </div>
    </fieldset>
  )
}

function SearchPage({ settings, selectedSiteIds, setSelectedSiteIds, selectedRoleIds, setSelectedRoleIds, selectedIncludeKeywords, setSelectedIncludeKeywords, selectedExcludeKeywords, setSelectedExcludeKeywords, applications, onApply, onOpenSettings, onOpenResume }: SearchPageProps) {
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [openDropdown, setOpenDropdown] = useState<'sites' | 'roles' | 'include' | 'exclude' | null>(null)
  const [compatibilityVacancy, setCompatibilityVacancy] = useState<Vacancy | null>(null)
  const [compatibilityResult, setCompatibilityResult] = useState<CompatibilityResult | null>(null)
  const [compatibilityError, setCompatibilityError] = useState<string | null>(null)
  const [checkingUrl, setCheckingUrl] = useState<string | null>(null)
  const [compatibilityCache, setCompatibilityCache] = useState<Record<string, CompatibilityResult>>({})
  const [compatibilityMode, setCompatibilityMode] = useState<'quick' | 'full'>('quick')
  const [compatibilityDocument, setCompatibilityDocument] = useState<string | null>(null)
  const [compatibilitySourceReport, setCompatibilitySourceReport] = useState<CompatibilityReport | null>(null)
  const [reports, setReports] = useState<CompatibilityReport[]>([])
  const [manualVacancyUrl, setManualVacancyUrl] = useState('')
  const [manualVacancyLoading, setManualVacancyLoading] = useState(false)
  const [manualVacancyError, setManualVacancyError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    void getCompatibilityReports(controller.signal).then(setReports).catch(() => undefined)
    return () => controller.abort()
  }, [])

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

  async function handleManualVacancy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setManualVacancyError(null)
    setManualVacancyLoading(true)
    try {
      const vacancy = await importVacancy(manualVacancyUrl.trim())
      const importedResult: SearchResponse = {
        provider: 'site_crawler',
        vacancies: [vacancy],
        warnings: [],
      }
      setResult((current) => current
        ? mergeSearchResponses([current, importedResult])
        : importedResult)
      setManualVacancyUrl('')
    } catch (requestError) {
      setManualVacancyError(requestError instanceof Error ? requestError.message : 'Не удалось добавить вакансию.')
    } finally {
      setManualVacancyLoading(false)
    }
  }

  async function refreshCompatibilityReport(vacancy: Vacancy, mode: 'quick' | 'full') {
    const controller = new AbortController()
    try {
      const loadedReports = await getCompatibilityReports(controller.signal)
      setReports(loadedReports)
      const matchingReport = findCompatibilityReport(loadedReports, vacancy.url, mode)
      if (matchingReport) {
        setCompatibilitySourceReport(matchingReport)
        setCompatibilityDocument(matchingReport.content)
      }
    } catch {
      // The analysis remains usable even if report history cannot be refreshed.
    }
  }

  async function handleCompatibility(vacancy: Vacancy, mode: 'quick' | 'full' = 'quick') {
    setCompatibilityVacancy(vacancy)
    setCompatibilityMode(mode)
    setCompatibilityError(null)
    setCompatibilityDocument(null)
    setCompatibilitySourceReport(null)
    const cacheKey = `${mode}:${vacancy.url}`
    const cached = compatibilityCache[cacheKey]
    if (cached) {
      setCompatibilityResult(cached)
      const savedReport = findCompatibilityReport(reports, vacancy.url, mode)
      if (savedReport) {
        setCompatibilitySourceReport(savedReport)
        setCompatibilityDocument(savedReport.content)
      } else {
        void refreshCompatibilityReport(vacancy, mode)
      }
      return
    }
    setCompatibilityResult(null)
    setCheckingUrl(vacancy.url)
    try {
      const checked = await checkCompatibility(vacancy, settings.roles.map((role) => role.title), mode)
      setCompatibilityResult(checked)
      setCompatibilityCache((current) => ({ ...current, [cacheKey]: checked }))
      await refreshCompatibilityReport(vacancy, mode)
    } catch (requestError) {
      setCompatibilityError(requestError instanceof Error ? requestError.message : 'Не удалось выполнить анализ.')
    } finally {
      setCheckingUrl(null)
    }
  }

  function openSavedReport(report: CompatibilityReport) {
    setCompatibilityVacancy(report.vacancy)
    setCompatibilityMode(report.mode)
    setCompatibilityResult(report.result)
    setCompatibilityDocument(report.content)
    setCompatibilitySourceReport(report)
    setCompatibilityError(null)
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
              <SelectionDropdown label="Где искать" items={settings.sites.map((site) => ({ id: site.id, label: site.name, meta: new URL(site.url).hostname }))} selectedIds={selectedSiteIds} open={openDropdown === 'sites'} onOpenChange={() => setOpenDropdown((current) => current === 'sites' ? null : 'sites')} onToggle={(id) => setSelectedSiteIds(toggleSelection(selectedSiteIds, id))} searchable />
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
      <section className="manual-vacancy-panel">
        <div><p className="eyebrow">Одна вакансия</p><h2>Добавить по ссылке</h2><p>Вставьте прямую ссылку — мы извлечём данные и покажем карточку с проверкой совместимости.</p></div>
        <form onSubmit={handleManualVacancy}>
          <label><span className="visually-hidden">Ссылка на вакансию</span><input type="url" value={manualVacancyUrl} onChange={(event) => setManualVacancyUrl(event.target.value)} placeholder="https://company.ru/jobs/123" required /></label>
          <button type="submit" className="primary-button" disabled={manualVacancyLoading}>{manualVacancyLoading ? <><span className="spinner" /> Добавляем…</> : <>Добавить вакансию <span>→</span></>}</button>
          {manualVacancyError ? <p className="error" role="alert">{manualVacancyError}</p> : null}
        </form>
      </section>
      {result ? <Results result={result} reports={reports} applications={applications} checkingUrl={checkingUrl} onApply={onApply} onCheck={handleCompatibility} onOpenReport={openSavedReport} /> : null}
      {compatibilityVacancy ? <CompatibilityDialog vacancy={compatibilityVacancy} report={compatibilitySourceReport} result={compatibilityResult} mode={compatibilityMode} loading={checkingUrl === compatibilityVacancy.url} error={compatibilityError} document={compatibilityDocument} onClose={() => setCompatibilityVacancy(null)} onOpenResume={() => { setCompatibilityVacancy(null); onOpenResume() }} onRunFull={() => void handleCompatibility(compatibilityVacancy, 'full')} /> : null}
    </div>
  )
}

type ApplicationsPageProps = {
  applications: JobApplication[]
  onUpdate: (id: string, changes: Partial<Pick<JobApplication, 'stage' | 'hrUrl'>>) => void
  onRemove: (id: string) => void
  onOpenSearch: () => void
}

function formatApplicationDate(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value))
}

function ApplicationsPage({ applications, onUpdate, onRemove, onOpenSearch }: ApplicationsPageProps) {
  const [openStageId, setOpenStageId] = useState<string | null>(null)
  const stageCounts = Object.fromEntries(APPLICATION_STAGES.map((stage) => [
    stage.value,
    applications.filter((application) => application.stage === stage.value).length,
  ])) as Record<ApplicationStage, number>

  return (
    <div className="page-content" onClick={() => setOpenStageId(null)}>
      <section className="page-heading dashboard-heading">
        <p className="eyebrow">Трекер откликов</p>
        <h1>Ваши отклики.</h1>
        <p className="lede">Сохраняйте вакансии, отмечайте этап отбора и держите контакты рекрутеров в одном месте.</p>
      </section>

      <section className="application-stats" aria-label="Статистика откликов">
        <article className="application-stat total"><span>Всего</span><strong>{applications.length}</strong></article>
        {APPLICATION_STAGES.map((stage) => <article className={`application-stat stage-${stage.value}`} key={stage.value}><span>{stage.label}</span><strong>{stageCounts[stage.value]}</strong></article>)}
      </section>

      {applications.length === 0 ? (
        <section className="applications-empty">
          <span aria-hidden="true">↗</span>
          <h2>Здесь появятся ваши отклики</h2>
          <p>Найдите подходящую вакансию и нажмите «Я откликнулся».</p>
          <button type="button" className="primary-button" onClick={onOpenSearch}>Перейти к поиску <span>→</span></button>
        </section>
      ) : (
        <section className="applications-list" aria-label="Список откликов">
          {applications.map((application) => (
            <article className="application-card" key={application.id}>
              <div className="application-company-mark">{application.company.slice(0, 2).toUpperCase()}</div>
              <div className="application-main">
                <span className="application-company">{application.company}</span>
                <h2>{application.vacancyTitle}</h2>
                <a href={application.vacancyUrl} target="_blank" rel="noreferrer">Открыть вакансию ↗</a>
                <small>Добавлено {formatApplicationDate(application.createdAt)}</small>
              </div>
              <div className="application-field stage-field">
                <span>Этап отбора</span>
                <SingleSelect
                  ariaLabel={`Этап отбора для ${application.vacancyTitle}`}
                  className="application-stage-select"
                  value={application.stage}
                  options={APPLICATION_STAGES.map((stage) => ({ value: stage.value, label: stage.label }))}
                  open={openStageId === application.id}
                  onOpenChange={(open) => setOpenStageId(open ? application.id : null)}
                  onChange={(stage) => onUpdate(application.id, { stage: stage as ApplicationStage })}
                />
              </div>
              <label className="application-field hr-field">
                <span>Ссылка на HR</span>
                <input type="url" value={application.hrUrl} onChange={(event) => onUpdate(application.id, { hrUrl: event.target.value })} placeholder="Telegram, LinkedIn или профиль" />
              </label>
              <button type="button" className="application-remove" onClick={() => onRemove(application.id)} aria-label={`Удалить отклик ${application.vacancyTitle}`} title="Удалить отклик"><TrashIcon /></button>
            </article>
          ))}
        </section>
      )}
      <p className="storage-note">Данные пока сохраняются локально в браузере. Структура подготовлена для будущей синхронизации с Google Sheets.</p>
    </div>
  )
}

function ReportsPage({ visible, onOpenSearch }: { visible: boolean; onOpenSearch: () => void }) {
  const [reports, setReports] = useState<CompatibilityReport[]>([])
  const [selectedReport, setSelectedReport] = useState<CompatibilityReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    if (!visible) return
    const controller = new AbortController()
    let mounted = true
    void (async () => {
      await Promise.resolve()
      if (!mounted) return
      setLoading(true)
      setError(null)
      try {
        const loadedReports = await getCompatibilityReports(controller.signal)
        if (mounted) setReports(loadedReports)
      } catch (requestError) {
        if (!mounted || requestError instanceof DOMException && requestError.name === 'AbortError') return
        setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить отчёты.')
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => {
      mounted = false
      controller.abort()
    }
  }, [visible, reloadKey])

  return (
    <div className="page-content">
      <section className="page-heading dashboard-heading">
        <p className="eyebrow">Career Ops</p>
        <h1>Отчёты.</h1>
        <p className="lede">Все проведённые проверки совместимости сохраняются локально и доступны без повторного анализа.</p>
      </section>

      {error ? <div className="reports-error" role="alert"><p>{error}</p><button type="button" className="report-open-button" onClick={() => setReloadKey((current) => current + 1)}>Повторить загрузку</button></div> : null}
      {loading ? <p className="reports-loading">Загружаем сохранённые отчёты…</p> : null}
      {!loading && !error && reports.length === 0 ? (
        <section className="applications-empty">
          <span aria-hidden="true">▤</span>
          <h2>Отчётов пока нет</h2>
          <p>Найдите вакансию и запустите проверку совместимости.</p>
          <button type="button" className="primary-button" onClick={onOpenSearch}>Перейти к поиску <span>→</span></button>
        </section>
      ) : null}
      {reports.length > 0 ? (
        <section className="reports-panel" aria-label="Сохранённые отчёты">
          <div className="reports-table-scroll">
            <table className="reports-table">
              <thead><tr><th>Вакансия</th><th>Ссылка</th><th>Совместимость</th><th><span className="visually-hidden">Действие</span></th></tr></thead>
              <tbody>{reports.map((report) => (
                <tr key={report.id}>
                  <td><strong>{report.vacancy.title}</strong><span>{report.vacancy.company ?? 'Компания не указана'} · {report.mode === 'full' ? 'Полный' : 'Быстрый'}</span></td>
                  <td><a href={report.vacancy.url} target="_blank" rel="noreferrer">Открыть вакансию ↗</a></td>
                  <td><span className={`report-score decision-${report.result.decision}`}><b>{report.result.score.toFixed(1)}</b> из 5</span></td>
                  <td><button type="button" className="report-open-button" onClick={() => setSelectedReport(report)}>Открыть отчёт</button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      ) : null}
      {selectedReport ? <CompatibilityDialog vacancy={selectedReport.vacancy} report={selectedReport} result={selectedReport.result} mode={selectedReport.mode} loading={false} error={null} document={selectedReport.content} onClose={() => setSelectedReport(null)} /> : null}
    </div>
  )
}

function formatFileSize(value: number): string {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} КБ`
  return `${(value / (1024 * 1024)).toFixed(1)} МБ`
}

function ResumePage() {
  const [resume, setResume] = useState<ResumeSnapshot | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void getResume()
      .then((snapshot) => {
        if (active) setResume(snapshot)
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить сведения о резюме.')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [])

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) return
    const form = event.currentTarget
    setError(null)
    setUploading(true)
    try {
      setResume(await uploadResume(file))
      setFile(null)
      form.reset()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить резюме.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="page-content">
      <section className="page-heading resume-heading">
        <p className="eyebrow">Профиль кандидата</p>
        <h1>Ваше резюме.</h1>
        <p className="lede">Загрузите исходный файл. Он останется на этом компьютере, а перед анализом вакансий вы сможете проверить извлечённый текст.</p>
      </section>

      <section className="resume-workspace">
        <form className="resume-upload" onSubmit={handleUpload}>
          <div className="resume-upload-copy">
            <span aria-hidden="true">↑</span>
            <div><h2>{resume?.uploaded ? 'Заменить исходное резюме' : 'Загрузить резюме'}</h2><p>PDF, DOCX, TXT или MD · до 10 МБ</p></div>
          </div>
          <label className="resume-file-field">
            <span>{file ? file.name : 'Выбрать файл'}</span>
            <input type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </label>
          <button type="submit" className="primary-button" disabled={!file || uploading}>{uploading ? <><span className="spinner" /> Извлекаем текст…</> : <>Загрузить <span>→</span></>}</button>
        </form>

        {error ? <p className="error resume-error" role="alert">{error}</p> : null}
        {loading ? <p className="resume-loading">Проверяем сохранённое резюме…</p> : null}

        {!loading && resume?.uploaded ? <div className="resume-result">
          <div className="resume-result-heading">
            <div><p className="eyebrow">Файл загружен</p><h2>{resume.original_filename}</h2></div>
            <dl>
              <div><dt>Размер</dt><dd>{formatFileSize(resume.size_bytes ?? 0)}</dd></div>
              <div><dt>Извлечено</dt><dd>{resume.extracted_characters?.toLocaleString('ru-RU')} знаков</dd></div>
            </dl>
          </div>
          <div className="resume-preview"><div><strong>Предварительный просмотр</strong><span>Career Ops использует этот текст только после запуска проверки</span></div><pre>{resume.preview}</pre></div>
        </div> : null}
      </section>
    </div>
  )
}

export default function App() {
  const [page, setPage] = useState<Page>('search')
  const [settings, setSettings] = useState<SearchSettings>(loadSearchSettings)
  const [initialSelection] = useState(loadSearchSelection)
  const [selectedSiteIds, setSelectedSiteIds] = useState<string[]>(initialSelection.siteIds)
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>(initialSelection.roleIds)
  const [selectedIncludeKeywords, setSelectedIncludeKeywords] = useState<string[]>(initialSelection.includeKeywords)
  const [selectedExcludeKeywords, setSelectedExcludeKeywords] = useState<string[]>(initialSelection.excludeKeywords)
  const [applications, setApplications] = useState<JobApplication[]>(loadApplications)

  useEffect(() => {
    saveSearchSelection({
      siteIds: selectedSiteIds,
      roleIds: selectedRoleIds,
      includeKeywords: selectedIncludeKeywords,
      excludeKeywords: selectedExcludeKeywords,
    })
  }, [selectedSiteIds, selectedRoleIds, selectedIncludeKeywords, selectedExcludeKeywords])

  useEffect(() => {
    saveApplications(applications)
  }, [applications])

  useEffect(() => {
    const controller = new AbortController()
    void getRemoteApplications(controller.signal)
      .then(setApplications)
      .catch(() => undefined)
    return () => controller.abort()
  }, [])

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
        setSelectedSiteIds((current) => current.filter((id) => remoteSettings.sites.some((site) => site.id === id)))
        setSelectedRoleIds((current) => current.filter((id) => remoteSettings.roles.some((role) => role.id === id)))
        setSelectedIncludeKeywords((current) => current.filter((keyword) => remoteSettings.includeKeywords.includes(keyword)))
        setSelectedExcludeKeywords((current) => current.filter((keyword) => remoteSettings.excludeKeywords.includes(keyword)))
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
    setSelectedIncludeKeywords((current) => current.filter((keyword) => nextSettings.includeKeywords.includes(keyword)))
    setSelectedExcludeKeywords((current) => current.filter((keyword) => nextSettings.excludeKeywords.includes(keyword)))
  }

  function addApplication(vacancy: Vacancy) {
    setApplications((current) => addVacancyApplication(current, vacancy, createId(), new Date().toISOString()))
    void createRemoteApplication(vacancy)
      .then((saved) => setApplications((current) => [saved, ...current.filter((application) => application.vacancyUrl !== saved.vacancyUrl)]))
      .catch(() => undefined)
  }

  function changeApplication(id: string, changes: Partial<Pick<JobApplication, 'stage' | 'hrUrl'>>) {
    setApplications((current) => updateApplication(current, id, changes, new Date().toISOString()))
    void updateRemoteApplication(id, changes)
      .then((saved) => setApplications((current) => current.map((application) => application.id === id ? saved : application)))
      .catch(() => undefined)
  }

  function removeApplication(id: string) {
    setApplications((current) => current.filter((application) => application.id !== id))
    void deleteRemoteApplication(id).catch(() => undefined)
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <button type="button" className="brand" onClick={() => setPage('search')} aria-label="Job Compass — поиск"><span className="brand-mark">JC</span><span>Job Compass</span></button>
        <nav aria-label="Основная навигация">
          <button type="button" className={page === 'search' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('search')}><span aria-hidden="true">⌕</span><span>Поиск вакансий</span></button>
          <button type="button" className={page === 'applications' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('applications')}><span aria-hidden="true">✓</span><span>Отклики</span>{applications.length > 0 ? <b className="nav-count">{applications.length}</b> : null}</button>
          <button type="button" className={page === 'reports' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('reports')}><span aria-hidden="true">▥</span><span>Отчёты</span></button>
          <button type="button" className={page === 'resume' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('resume')}><span aria-hidden="true">▤</span><span>Резюме</span></button>
          <button type="button" className={page === 'settings' ? 'nav-item active' : 'nav-item'} onClick={() => setPage('settings')}><span aria-hidden="true">◫</span><span>Настройки</span></button>
        </nav>
        <div className="sidebar-status"><i /><div><strong>Работает локально</strong><span>Данные остаются у вас</span></div></div>
      </aside>
      <main className="main-area">
        <header className="mobile-topbar"><button type="button" className="brand" onClick={() => setPage('search')}><span className="brand-mark">JC</span><span>Job Compass</span></button></header>
        <div hidden={page !== 'search'}>
          <SearchPage settings={settings} selectedSiteIds={selectedSiteIds} setSelectedSiteIds={setSelectedSiteIds} selectedRoleIds={selectedRoleIds} setSelectedRoleIds={setSelectedRoleIds} selectedIncludeKeywords={selectedIncludeKeywords} setSelectedIncludeKeywords={setSelectedIncludeKeywords} selectedExcludeKeywords={selectedExcludeKeywords} setSelectedExcludeKeywords={setSelectedExcludeKeywords} applications={applications} onApply={addApplication} onOpenSettings={() => setPage('settings')} onOpenResume={() => setPage('resume')} />
        </div>
        <div hidden={page !== 'applications'}>
          <ApplicationsPage applications={applications} onUpdate={changeApplication} onRemove={removeApplication} onOpenSearch={() => setPage('search')} />
        </div>
        <div hidden={page !== 'reports'}>
          <ReportsPage visible={page === 'reports'} onOpenSearch={() => setPage('search')} />
        </div>
        <div hidden={page !== 'resume'}>
          <ResumePage />
        </div>
        <div hidden={page !== 'settings'}>
          <SettingsPage settings={settings} onChange={updateSettings} onOpenSearch={() => setPage('search')} />
        </div>
        <footer><span>Job Compass</span><p>Собирает ссылки. Решение об отклике всегда остаётся за вами.</p></footer>
      </main>
    </div>
  )
}
