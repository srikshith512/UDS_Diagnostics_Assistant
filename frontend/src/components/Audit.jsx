import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty } from './ui'

export default function Audit({ refreshKey, onError }) {
  const [rows, setRows] = useState([])
  useEffect(() => { api.audit().then(setRows).catch((e) => onError(e.message)) }, [refreshKey]) // eslint-disable-line
  return (
    <section>
      <h2>Audit log</h2>
      <p className="lead">Every question, generation, review decision, run and export is recorded with the person who did it.</p>
      {rows.length ? (
        <div className="card wide"><table><thead><tr><th>Time (UTC)</th><th>Who</th><th>Action</th><th>Detail</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.id}><td className="mono nowrap">{r.ts.replace('T', ' ').slice(0, 19)}</td><td>{r.actor}</td><td>{r.action}</td><td className="meta">{r.detail}</td></tr>)}</tbody></table></div>
      ) : <Empty>No activity yet.</Empty>}
    </section>
  )
}
