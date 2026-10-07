import { api } from '../api'
import Bytes from './Bytes'
import { Empty, Tag, useAction } from './ui'

const pre = (p) => `Session ${String(p.session).padStart(2, '0')}, ${p.unlocked ? 'unlocked' : 'locked'}${p.seed_issued ? ', seed issued' : ''}`

export default function Tests({ tests, fault, reload, onError, onInfo }) {
  const [busy, run] = useAction(onError)
  const act = (fn, msg) => run(async () => { const r = await fn(); await reload(); if (msg) onInfo(msg(r)) })
  const failed = tests.filter((t) => t.passed === false).length
  const ran = tests.some((t) => t.passed !== null)

  return (
    <section>
      <h2>Test cases</h2>
      <p className="lead">Expected responses come from the rule engine, never from the language model. Review each case, then run the suite on the simulated ECU.</p>
      <div className="row" style={{ marginBottom: 14 }}>
        <button className="btn pri" disabled={busy} onClick={() => act(api.generate, (r) => `Generated ${r.generated} test cases`)}>Generate test suite</button>
        <button className="btn" disabled={busy || !tests.length} onClick={() => act(() => api.run(fault), (r) => `Ran ${r.total} tests: ${r.failed} failed`)}>Run on simulated ECU</button>
        <button className="btn" disabled={busy || !tests.some((t) => t.status === 'Draft')} onClick={() => act(api.approveDrafts, (r) => `Approved ${r.approved} drafts`)}>Approve all drafts</button>
        {ran && <Tag tone={failed ? 'bad' : 'ok'}>{failed ? `${failed} failing` : 'All passing'}</Tag>}
      </div>
      {!tests.length && <Empty>No tests yet. Generate the suite to get positive and negative cases for every service.</Empty>}
      {tests.map((t) => (
        <article className="card" key={t.id}>
          <div className="case">
            <div>
              <h4>{t.id} {t.title}</h4>
              <div className="row" style={{ marginTop: 6 }}><Tag tone={t.kind === 'positive' ? 'ok' : 'bad'}>{t.kind}</Tag><span className="meta">{pre(t.pre)}</span></div>
            </div>
            <div className="row">
              <Tag tone={t.status === 'Approved' ? 'ok' : t.status === 'Rejected' ? 'bad' : ''}>{t.status}</Tag>
              <button className="btn sm" disabled={busy} onClick={() => act(() => api.review(t.id, 'Approved'))}>Approve</button>
              <button className="btn sm" disabled={busy} onClick={() => act(() => api.review(t.id, 'Rejected'))}>Reject</button>
            </div>
          </div>
          <div className="kv">
            <span>Request</span><Bytes hex={t.request} />
            <span>Expected</span><Bytes hex={t.expected} role="response" />
            <span>Pass if</span><span>{t.criteria}</span>
            {t.passed !== null && <><span>Actual</span><div className="row"><Bytes hex={t.actual} role="response" /><Tag tone={t.passed ? 'ok' : 'bad'}>{t.passed ? 'Pass' : 'Fail'}</Tag></div></>}
          </div>
        </article>
      ))}
    </section>
  )
}
