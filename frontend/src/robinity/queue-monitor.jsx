import React, { useEffect, useState } from 'react';

function formatDuration(seconds) {
  if (seconds == null || !Number.isFinite(Number(seconds))) return '—';
  const s = Number(seconds);
  return s < 60 ? s.toFixed(1) + 's' : (s / 60).toFixed(1) + 'min';
}

export default function QueueMonitor() {
  const [snapshot,setSnapshot] = useState(null), [error,setError] = useState('');
  useEffect(() => {
    let stopped = false, timer;
    const update = async () => {
      try {
        const response = await fetch('/api/admin/queue/stats', {signal:AbortSignal.timeout(8000)});
        const data = await response.json();
        if (!response.ok || data.error) throw Error(data.error || 'Queue metrics unavailable');
        if (!stopped) { setSnapshot(data); setError(''); }
      } catch { if (!stopped) setError('Queue metrics unavailable. Check database and Redis connectivity.'); }
      if (!stopped) timer = setTimeout(update,10000);
    };
    update(); return () => { stopped=true; clearTimeout(timer); };
  },[]);
  return <section className="admin-panel"><h2>Analysis operations</h2>
    {error && <p role="alert">{error} {snapshot && 'The snapshot below is outdated.'}</p>}
    {!snapshot && !error && <p>Loading queue metrics…</p>}
    {snapshot && <>
      <p>Updated {new Date(snapshot.timestamp).toLocaleString()} · Observed server limits, not provider billing quotas.</p>
      {snapshot.deliveryError && <p role="alert">{snapshot.deliveryError}</p>}

      {/* BullMQ queue counts */}
      <h3>Queue state</h3>
      <div className="api-key-details">{Object.entries(snapshot.queues || {}).map(([state,count]) => <div key={state}><strong>{state}</strong><p>{count}</p></div>)}</div>

      {/* Provider capacity */}
      <h3>Provider capacity</h3>
      <div className="api-key-details">{Object.entries(snapshot.providers || {}).map(([name,p]) => <div key={name}><strong>{name}</strong><p>{p.inFlight} / {p.concurrency} active · {Number(p.tokens).toFixed(1)} available permits</p><small>{p.cooldownUntil>Date.now() ? 'Cooling down until '+new Date(p.cooldownUntil).toLocaleTimeString() : 'No cooldown'}</small></div>)}</div>

      {/* Durable jobs */}
      <h3>Durable jobs</h3>
      {(snapshot.jobs || []).map(row => <p key={row.status}>{row.status}: {row.count}{['queued','running'].includes(row.status) && row.oldest ? ' · oldest '+new Date(row.oldest).toLocaleString() : ''}</p>)}

      {/* Job duration metrics — plan §11 */}
      {Array.isArray(snapshot.metrics) && snapshot.metrics.length > 0 && <>
        <h3>Analysis performance (last hour)</h3>
        <table className="queue-metrics-table" style={{width:'100%',borderCollapse:'collapse',fontSize:'0.85em'}}>
          <thead><tr><th style={{textAlign:'left',padding:'4px 8px'}}>Status</th><th style={{textAlign:'left',padding:'4px 8px'}}>Stage</th><th style={{textAlign:'right',padding:'4px 8px'}}>Count</th><th style={{textAlign:'right',padding:'4px 8px'}}>Avg</th><th style={{textAlign:'right',padding:'4px 8px'}}>p95</th></tr></thead>
          <tbody>{snapshot.metrics.map((row, i) => <tr key={i} style={{borderTop:'1px solid var(--border, #333)'}}>
            <td style={{padding:'4px 8px'}}>{row.status}</td>
            <td style={{padding:'4px 8px'}}>{row.stage || '—'}</td>
            <td style={{textAlign:'right',padding:'4px 8px'}}>{row.count}</td>
            <td style={{textAlign:'right',padding:'4px 8px'}}>{formatDuration(row.avg_duration_sec)}</td>
            <td style={{textAlign:'right',padding:'4px 8px'}}>{formatDuration(row.p95_duration_sec)}</td>
          </tr>)}</tbody>
        </table>
      </>}
    </>}
  </section>;
}
