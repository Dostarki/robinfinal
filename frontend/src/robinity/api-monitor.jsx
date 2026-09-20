import React, { useState } from 'react';
import './api-monitor.css';
import QueueMonitor from './queue-monitor';

const number = value => Number(value || 0).toLocaleString();
const percent = value => value == null ? 'Unavailable' : `${value.toFixed(1)}%`;
const date = value => value ? new Date(value).toLocaleString() : 'Not recorded';

export default function ApiMonitor({ keys, dailyBudgets = [], owner, refresh, action, saveSettings }) {
  const [filter, setFilter] = useState('All');
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const providers = [...new Set(['GoPlus', 'Helius', 'Etherscan', 'Bitquery', ...keys.map(key => key.provider)])];
  async function save(event) {
    event.preventDefault(); setSaving(true); setError('');
    try { await saveSettings(editing); setEditing(null); refresh(); }
    catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }
  return <section className="api-monitor">
    <QueueMonitor />
    <div className="api-monitor-heading"><div><h2>API infrastructure</h2><p>Least-used eligible key per provider · UTC calendar month · refreshes every 10 seconds</p></div><button className="button secondary" onClick={refresh}>Refresh</button></div>
    <p className="api-monitor-note">Budget usage counts requests observed by this server, not provider billing credits or usage from other apps. Unknown limits stay unavailable. Tracking begins at the date shown on each key; earlier usage cannot be reconstructed. GoPlus authentication calls are not included in analysis request totals.</p>
    <div className="api-monitor-filters">{['All', ...providers].map(provider => <button className="button secondary" aria-pressed={filter === provider} key={provider} onClick={() => setFilter(provider)}>{provider}</button>)}</div>
    {providers.filter(provider => filter === 'All' || filter === provider).map(provider => {
      const items = keys.filter(key => key.provider === provider);
      const requests = items.reduce((sum, key) => sum + key.monthlyRequests, 0);
      return <section className="admin-panel api-provider" key={provider}>
        <div className="api-monitor-heading"><h3>{provider}</h3><span>{items.length} keys · {number(requests)} monthly requests · {items.filter(key => key.state === 'ready').length} ready</span></div>
        {dailyBudgets.filter(budget => budget.provider === provider).map(budget => <p className="api-monitor-note" key={provider}>Creator requests today ({budget.day} UTC): {number(budget.used)} / {number(budget.limit)} · {percent(budget.used / budget.limit * 100)} of server daily budget</p>)}
        {!items.length && <p className="muted">{provider === 'GoPlus' ? 'Public access — no API credentials configured. No per-key quota is available.' : 'No API credentials configured.'}</p>}
        {items.map(key => <article className="api-key-card" key={key.id}>
          <div className="api-monitor-heading"><div><strong>{key.label || provider}</strong> <code>{key.masked}</code><p>{key.source === 'env' ? 'Server environment' : 'Encrypted vault'} · {key.month || 'Current month'} UTC</p></div><span className={`status-pill ${key.state === 'ready' ? 'active' : 'pending'}`}>{key.state}</span></div>
          <div className="api-key-meters"><div><span>Local request budget</span><strong>{percent(key.quotaPercent)}</strong><progress aria-label={`${key.label} request budget`} max="100" value={key.quotaPercent == null ? 0 : Math.min(100, key.quotaPercent)} /><small>{number(key.monthlyRequests)} / {key.monthlyLimit ? number(key.monthlyLimit) : 'no limit configured'}</small></div><div><span>Share of provider traffic</span><strong>{percent(key.trafficPercent)}</strong><progress aria-label={`${key.label} traffic share`} max="100" value={key.trafficPercent || 0}/><small>Of {provider}'s observed monthly requests</small></div></div>
          <dl className="api-key-details">
            <div><dt>Successful / failed this month</dt><dd>{number(key.monthlySuccesses)} / {number(key.monthlyRequests - key.monthlySuccesses)}</dd></div>
            <div><dt>Success rate this month</dt><dd>{percent(key.monthlyRequests ? key.monthlySuccesses / key.monthlyRequests * 100 : null)}</dd></div>
            <div><dt>Local budget remaining</dt><dd>{key.monthlyLimit ? number(Math.max(0, key.monthlyLimit - key.monthlyRequests)) : 'Unavailable'}</dd></div>
            <div><dt>Last request / HTTP status</dt><dd>{date(key.lastUsedAt)} · {key.lastStatus || '—'}</dd></div>
            <div><dt>Consecutive failures</dt><dd>{number(key.consecutiveErrors)}</dd></div>
            <div><dt>Cooldown until</dt><dd>{key.cooldownUntil > Date.now() ? date(key.cooldownUntil) : 'None'}</dd></div>
            <div><dt>Expiry</dt><dd>{key.expiresAt ? date(key.expiresAt) : 'Not configured'}</dd></div>
            <div><dt>Reliable tracking started</dt><dd>{date(key.trackedSince)}</dd></div>
            <div><dt>Recorded lifetime requests</dt><dd>{number(key.requestCount)} (may include legacy counters)</dd></div>
          </dl>
          {(key.state === 'expired' || key.state === 'quota reached' || key.consecutiveErrors >= 3 || key.quotaPercent >= 80 || (key.expiresAt && key.expiresAt - Date.now() < 7 * 86400000)) && <p className="api-key-attention">{key.state === 'expired' ? 'Expired: replace this credential or verify its expiry.' : key.state === 'quota reached' ? 'Local budget exhausted: check the provider account before adjusting the budget.' : key.consecutiveErrors >= 3 ? 'Repeated failures: check credentials, provider access and account limits.' : 'Review soon: budget above 80% or credential expiring within 7 days.'}</p>}
          {owner && <div className="api-key-actions"><button className="button secondary" onClick={() => {setError(''); setEditing({ id: key.id, monthlyLimit: key.monthlyLimit, expiresAt: key.expiresAt ? new Date(key.expiresAt).toISOString().slice(0, 10) : '' });}}>Edit budget / expiry</button>{key.source === 'vault' && <><button className="button secondary" onClick={() => action('rotate', key.id)}>Replace key</button><button className="button secondary" onClick={() => action('toggle', key.id)}>{key.active ? 'Pause' : 'Activate'}</button><button className="button secondary" onClick={() => action('delete', key.id)}>Remove</button></>}</div>}
          {editing?.id === key.id && <form className="api-key-editor" onSubmit={save}><label>Monthly local request budget (0 = no limit)<input type="number" min="0" max="100000000" required value={editing.monthlyLimit} onChange={e => setEditing({ ...editing, monthlyLimit: e.target.value })}/></label><label>Credential expiry (optional)<input type="date" value={editing.expiresAt} onChange={e => setEditing({ ...editing, expiresAt: e.target.value })}/></label><button className="button" disabled={saving}>{saving ? 'Saving…' : 'Save settings'}</button><button type="button" className="button secondary" onClick={() => setEditing(null)}>Cancel</button>{error && <p role="alert">{error}</p>}</form>}
        </article>)}
      </section>;
    })}
    <p className="api-monitor-note">RugCheck, Honeypot.is and DexScreener (market data / logos) use public endpoints; no key rotation is configured for them. Creator requests also have server-wide daily budgets: Helius 60, Bitquery 10, Etherscan 100. These budgets apply across all keys.</p>
  </section>;
}
