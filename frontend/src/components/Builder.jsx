import { useEffect, useState } from 'react'
import { api } from '../api'
import Bytes from './Bytes'
import { Tag, useAction, useDebounced } from './ui'

export default function Builder({ spec, bench, fault, health, onError, onAdded }) {
  const [hex, setHex] = useState('27 01')
  const [goal, setGoal] = useState('')
  const [note, setNote] = useState('')
  const [v, setV] = useState(null)
  const [busy, run] = useAction(onError)
  const debounced = useDebounced(hex)
  const payload = { ...bench, fault }

  useEffect(() => {
    let live = true
    api.validate({ request_hex: debounced, ...bench, fault }).then((r) => live && (setV(r), onError(''))).catch((e) => live && (setV(null), onError(e.message)))
    return () => { live = false }
  }, [debounced, bench.session, bench.unlocked, bench.seed_issued, fault]) // eslint-disable-line

  const suggest = () => run(async () => {
    const r = await api.assist({ description: goal, ...payload })
    setHex(r.suggestion); setNote(r.explanation)
  })
  const add = () => run(async () => { const r = await api.addTest({ request_hex: hex, ...bench }); onAdded(`Added ${r.id} as a draft test case`) })

  return (
    <section>
      <h2>Request builder</h2>
      <p className="lead">Type a request or pick an example. The rule engine predicts the response for the bench state above; the simulated ECU answers the same request.</p>
      <div className="card">
        <input type="text" className="mono" style={{ width: '100%' }} value={hex} onChange={(e) => setHex(e.target.value)} aria-label="Request bytes in hex" />
        <div className="row" style={{ marginTop: 10 }}>
          {spec?.services.map((s) => <button key={s.sid} className="btn sm" onClick={() => setHex(s.example)}>{s.sid} {s.name}</button>)}
        </div>
      </div>
      <form className="card row" onSubmit={(e) => { e.preventDefault(); suggest() }}>
        <input type="text" style={{ flex: 1, minWidth: 220 }} placeholder="Or describe it: “Read the VIN” or “Unlock the ECU”" value={goal} onChange={(e) => setGoal(e.target.value)} aria-label="Describe the request in plain language" maxLength={500} />
        <button className="btn" disabled={busy || goal.trim().length < 3 || !health?.llm_available}>{busy ? 'Thinking…' : 'Suggest request'}</button>
        {!health?.llm_available && <span className="meta">Needs the Ollama model ({health?.llm_model ?? 'not configured'}). The rule engine still checks every suggestion.</span>}
        {note && <span className="meta" style={{ flexBasis: '100%' }}>{note}</span>}
      </form>
      {v && (<>
        <div className="grid2">
          <div className="card"><b>Request</b><div style={{ marginTop: 8 }}><Bytes hex={v.request} /></div></div>
          <div className="card">
            <div className="row"><b>Predicted by rules</b><Tag tone={v.spec.positive ? 'ok' : 'bad'}>{v.spec.positive ? 'Valid' : 'Rejected'}</Tag></div>
            <div style={{ marginTop: 8 }}><Bytes hex={v.spec.response} role="response" /></div>
            {v.spec.nrc_text && <div className="meta" style={{ marginTop: 6 }}>NRC {v.spec.response.split(' ')[2]}: {v.spec.nrc_text}</div>}
          </div>
        </div>
        <div className="card">
          <div className="row"><b>Simulated ECU</b><Tag tone={v.matches ? 'ok' : 'bad'}>{v.matches ? 'Matches spec' : 'Deviates from spec'}</Tag></div>
          <div style={{ marginTop: 8 }}><Bytes hex={v.ecu.response} role="response" /></div>
          <ol className="trace">{v.spec.trace.map((t, i) => <li key={i}>{t}</li>)}</ol>
          <button className="btn" onClick={add} disabled={busy || !v.request}>Add as test case</button>
        </div>
      </>)}
    </section>
  )
}
