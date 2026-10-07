import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, Tag, useAction } from './ui'

const SUGGESTIONS = ['How do I unlock the ECU?', 'Which DIDs can I read?', 'What does NRC 33 mean?', 'Which services need security access?']

export default function QA({ spec, onError, onIngested }) {
  const [q, setQ] = useState(SUGGESTIONS[0])
  const [res, setRes] = useState(null)
  const [busy, run] = useAction(onError)
  const ask = (text = q) => run(async () => setRes(await api.ask(text)))
  useEffect(() => { ask(SUGGESTIONS[0]) }, []) // eslint-disable-line

  const upload = (e) => {
    const file = e.target.files[0]
    e.target.value = ''
    if (file) run(async () => { const r = await api.ingest(file); onIngested(`Indexed ${r.name} (${r.chunks} chunks)`) })
  }

  return (
    <section>
      <h2>Ask the spec</h2>
      <p className="lead">Answers use only the ECU specification and ingested documents, and always cite their source. If nothing matches, the assistant says so.</p>
      <form className="card row" onSubmit={(e) => { e.preventDefault(); ask() }}>
        <input type="text" style={{ flex: 1, minWidth: 200 }} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Question" maxLength={500} />
        <button className="btn pri" disabled={busy || q.trim().length < 2}>{busy ? 'Searching…' : 'Ask'}</button>
      </form>
      <div className="row" style={{ marginBottom: 14 }}>
        {SUGGESTIONS.map((s) => <button key={s} className="btn sm" onClick={() => { setQ(s); ask(s) }}>{s}</button>)}
      </div>
      {res && (
        <div className="card">
          <div className="row" style={{ marginBottom: 8 }}>
            <b>Answer</b>
            <Tag tone={res.grounded ? 'ok' : 'bad'}>{res.grounded ? 'Grounded in cited sources' : 'Not verified against sources'}</Tag>
            <Tag>{res.mode === 'llm' ? 'Language model' : res.mode === 'extractive' ? 'Extracted from spec' : 'No match'}</Tag>
            <Tag>{res.retrieval} search</Tag>
          </div>
          <p className="answer">{res.answer}</p>
          {res.citations.map((c) => (
            <details key={c.id} className="cite-box"><summary><span className="cite">{c.id}</span> {c.title} <span className="meta">score {c.score}</span></summary><p>{c.text}</p></details>
          ))}
        </div>
      )}
      <div className="card">
        <div className="row"><b>Documents</b><span className="meta">Add your own .md or .txt notes (up to 1 MB) to extend the knowledge base.</span>
          <label className="btn sm">Upload file<input type="file" accept=".md,.txt" onChange={upload} hidden /></label></div>
        {spec?.documents.length ? <div className="row" style={{ marginTop: 8 }}>{spec.documents.map((d) => <Tag key={d}>{d}</Tag>)}</div> : <Empty>No extra documents yet.</Empty>}
      </div>
      <details className="card"><summary>All specification sections ({spec?.sections.length ?? 0})</summary>
        {spec?.sections.map((s) => <p key={s.id}><span className="cite">{s.id}</span> <b>{s.title}</b><br /><span className="meta">{s.text}</span></p>)}
      </details>
    </section>
  )
}
