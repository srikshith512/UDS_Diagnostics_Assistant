// Renders a hex string as byte chips. Role colors the first byte: request SID or response (positive/negative).
export default function Bytes({ hex, role = 'request' }) {
  const bytes = (hex || '').split(/\s+/).filter(Boolean)
  if (!bytes.length) return <span className="meta">no bytes</span>
  const first = role === 'response' ? (bytes[0] === '7F' ? 'neg' : 'pos') : 'sid'
  return (
    <div className="bytes" aria-label={hex}>
      {bytes.map((b, i) => <span key={i} className={`byte ${i === 0 ? first : ''}`}>{b}</span>)}
    </div>
  )
}
