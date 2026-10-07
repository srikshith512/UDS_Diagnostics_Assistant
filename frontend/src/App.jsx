import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import Audit from './components/Audit'
import Builder from './components/Builder'
import ExportPage from './components/ExportPage'
import QA from './components/QA'
import Tests from './components/Tests'
import { ErrorBanner, Tag } from './components/ui'

const TABS = [['qa', 'Ask the spec'], ['build', 'Request builder'], ['tests', 'Test cases'], ['exp', 'Export'], ['audit', 'Audit log']]

export default function App() {
  const [tab, setTab] = useState('qa')
  const [bench, setBench] = useState({ session: 1, unlocked: false, seed_issued: false })
  const [fault, setFault] = useState(null)
  const [spec, setSpec] = useState(null)
  const [health, setHealth] = useState(null)
  const [tests, setTests] = useState([])
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [tick, setTick] = useState(0)

  const bump = () => setTick((t) => t + 1)
  const reloadTests = useCallback(() => api.tests().then(setTests).then(bump).catch((e) => setError(e.message)), [])
  const loadSpec = useCallback(() => api.spec().then(setSpec).catch((e) => setError(e.message)), [])

  useEffect(() => { loadSpec(); reloadTests(); api.health().then(setHealth).catch((e) => setError(e.message)) }, [loadSpec, reloadTests])
  useEffect(() => { if (!info) return; const t = setTimeout(() => setInfo(''), 3500); return () => clearTimeout(t) }, [info])

  const notify = (m) => { setInfo(m); bump(); loadSpec() }
  const counts = { tests: tests.length || null }

  return (
    <div className="app">
      <aside>
        <h1>UDS Diagnostics Assistant</h1>
        <p>Synthetic ECU, simulated bench</p>
        <nav aria-label="Sections">
          {TABS.map(([k, l]) => (
            <button key={k} className={`nav ${tab === k ? 'on' : ''}`} aria-current={tab === k} onClick={() => setTab(k)}>
              {l}{k === 'tests' && counts.tests ? <small>{counts.tests}</small> : null}
            </button>
          ))}
        </nav>
        <div className="sp" />
        <p className="foot">
          Search: {health?.retrieval ?? '…'}<br />Model: {health ? (health.llm_available ? health.llm_model : 'offline') : '…'}<br />No real vehicle is ever contacted.
        </p>
      </aside>
      <main>
        <div className="bench">
          <b>Bench state</b>
          <label>Session<select value={bench.session} onChange={(e) => setBench({ session: +e.target.value, unlocked: false, seed_issued: false })}>
            <option value={1}>01 Default</option><option value={3}>03 Extended</option></select></label>
          <label>Security<select value={bench.unlocked ? 'u' : 'l'} onChange={(e) => setBench({ ...bench, unlocked: e.target.value === 'u' })}>
            <option value="l">Locked</option><option value="u">Unlocked</option></select></label>
          <label>ECU variant<select value={fault ?? ''} onChange={(e) => setFault(e.target.value || null)}>
            <option value="">Reference</option><option value="skip_security">Fault: skips security check</option></select></label>
          {fault && <Tag tone="bad">Fault injected</Tag>}
        </div>
        <ErrorBanner error={error} onClose={() => setError('')} />
        {info && <div className="toast" role="status">{info}</div>}
        {tab === 'qa' && <QA spec={spec} onError={setError} onIngested={notify} />}
        {tab === 'build' && <Builder spec={spec} bench={bench} fault={fault} health={health} onError={setError} onAdded={(m) => { notify(m); reloadTests(); setTab('tests') }} />}
        {tab === 'tests' && <Tests tests={tests} fault={fault} reload={reloadTests} onError={setError} onInfo={notify} />}
        {tab === 'exp' && <ExportPage tests={tests} onError={setError} onInfo={notify} />}
        {tab === 'audit' && <Audit refreshKey={tick} onError={setError} />}
      </main>
    </div>
  )
}
