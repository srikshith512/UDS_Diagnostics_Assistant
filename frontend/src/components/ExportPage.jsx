import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Tag } from './ui'

const Cov = ({ label, c }) => (
  <div>
    <div className="row" style={{ justifyContent: 'space-between' }}><span>{label}</span><span className="mono">{c.covered}/{c.total}</span></div>
    <div className="bar"><i style={{ width: `${(100 * c.covered) / c.total}%` }} /></div>
  </div>
)

export default function ExportPage({ tests, onError, onInfo }) {
  const [fmt, setFmt] = useState('python')
  const [cov, setCov] = useState(null)
  const [code, setCode] = useState('')
  const approved = tests.filter((t) => t.status === 'Approved').length

  useEffect(() => { api.coverage().then(setCov).catch((e) => onError(e.message)) }, [tests]) // eslint-disable-line
  useEffect(() => {
    if (!approved) return setCode('')
    api.exportScript(fmt).then(setCode).catch((e) => onError(e.message))
  }, [fmt, tests]) // eslint-disable-line

  const copy = async () => { try { await navigator.clipboard.writeText(code); onInfo('Script copied') } catch { onError('Copy is blocked by the browser. Use Download instead.') } }
  const download = () => {
    const url = URL.createObjectURL(new Blob([code], { type: 'text/plain' }))
    Object.assign(document.createElement('a'), { href: url, download: fmt === 'python' ? 'uds_tests.py' : 'uds_tests.can' }).click()
    URL.revokeObjectURL(url)
  }

  return (
    <section>
      <h2>Export and coverage</h2>
      <p className="lead">Only approved tests are exported. Coverage is measured against the spec, so gaps show before scripts reach the test bench.</p>
      {cov && (
        <div className="grid2">
          <div className="card" style={{ display: 'grid', gap: 12 }}>
            <b>Coverage of approved tests</b>
            <Cov label="Services" c={cov.services} /><Cov label="Negative response codes" c={cov.nrcs} /><Cov label="Sessions" c={cov.sessions} />
            <span className="meta">{cov.approved} approved of {cov.total} cases</span>
          </div>
          <div className="card"><b>Not yet covered</b>
            <div className="row" style={{ marginTop: 8 }}>
              {[...cov.services.missing.map((m) => `Service ${m}`), ...cov.nrcs.missing.map((m) => `NRC ${m}`), ...cov.sessions.missing.map((m) => `Session ${m}`)].map((m) => <Tag key={m} tone="bad">{m}</Tag>)}
              {!cov.services.missing.length && !cov.nrcs.missing.length && !cov.sessions.missing.length && <Tag tone="ok">Nothing missing</Tag>}
            </div>
          </div>
        </div>
      )}
      {approved ? (<>
        <div className="row" style={{ margin: '6px 0 10px' }}>
          <button className={`btn ${fmt === 'python' ? 'pri' : ''}`} onClick={() => setFmt('python')}>Python (pytest)</button>
          <button className={`btn ${fmt === 'capl' ? 'pri' : ''}`} onClick={() => setFmt('capl')}>CAPL</button>
          <button className="btn" onClick={copy}>Copy</button><button className="btn" onClick={download}>Download</button>
        </div>
        <pre>{code}</pre>
      </>) : <Empty>Nothing to export yet. Approve test cases on the Test cases tab first.</Empty>}
    </section>
  )
}
