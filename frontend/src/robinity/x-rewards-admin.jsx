import React, { useEffect, useState } from "react";

const API = (url, options = {}) => fetch(url, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...options }).then(async response => {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(data.error || data.detail?.error || data.detail || `Request failed (${response.status})`);
  return data;
});

const BUILT_IN = [["follow", "Follow"], ["like_rt", "Like & RT"], ["quote", "Quote"]];
const CHECKS = [["none", "No check (claim)"], ["like_rt", "Verify like + repost of link"], ["quote", "Verify quote of link"]];

function SettingsPanel({ settings, onSaved, notify }) {
  const [form, setForm] = useState(settings);
  const [busy, setBusy] = useState(false);
  useEffect(() => setForm(settings), [settings]);
  const submit = async event => {
    event.preventDefault(); setBusy(true);
    try { onSaved(await API("/api/admin/x/settings", { method: "PUT", body: JSON.stringify(form) })); notify("X task settings saved. The landing page uses them immediately."); }
    catch (error) { notify(error.message, true); }
    finally { setBusy(false); }
  };
  return <section className="admin-panel" data-testid="x-settings-panel">
    <h2><span>X task settings</span><span className="status-pill active">{settings.source === "database" ? "saved in database" : "using .env defaults"}</span></h2>
    <form onSubmit={submit}>
      <div className="row">
        <div><label>Target X username</label><input value={form.target_username} onChange={e => setForm({ ...form, target_username: e.target.value })} placeholder="RobinityInt" data-testid="x-settings-username" /></div>
        <div><label>Like / RT / Quote post link</label><input value={form.tweet_url} onChange={e => setForm({ ...form, tweet_url: e.target.value })} placeholder="https://x.com/RobinityInt/status/123…" data-testid="x-settings-tweet-url" /></div>
      </div>
      <label>Quote text</label><input value={form.quote_text} onChange={e => setForm({ ...form, quote_text: e.target.value })} maxLength={280} data-testid="x-settings-quote-text" />
      <div className="xr-grid">
        {BUILT_IN.map(([id, name]) => <div key={id}><label>{name} points</label><input type="number" min="0" value={form.points[id]} onChange={e => setForm({ ...form, points: { ...form.points, [id]: e.target.value } })} data-testid={`x-settings-points-${id}`} /></div>)}
      </div>
      <p className="xr-note">Point changes apply to every user instantly (leaderboard is recalculated from current values).</p>
      <button className="button" style={{ marginTop: 14, width: "auto" }} disabled={busy} data-testid="x-settings-save">{busy ? "Saving…" : "Save settings"}</button>
    </form>
  </section>;
}

const EMPTY_TASK = { title: "", text: "", link: "", points: 25, check: "none" };

function TasksPanel({ tasks, reload, notify }) {
  const [form, setForm] = useState(EMPTY_TASK);
  const [editing, setEditing] = useState(null);
  const submit = async event => {
    event.preventDefault();
    try {
      if (editing) await API(`/api/admin/x/tasks/${editing}`, { method: "PUT", body: JSON.stringify(form) });
      else await API("/api/admin/x/tasks", { method: "POST", body: JSON.stringify(form) });
      setForm(EMPTY_TASK); setEditing(null); reload(); notify(editing ? "Task updated." : "Task added — it now appears on the landing page as a new task.");
    } catch (error) { notify(error.message, true); }
  };
  const remove = async id => { if (!window.confirm("Remove this task? Points already earned stay with users.")) return; try { await API(`/api/admin/x/tasks/${id}`, { method: "DELETE" }); reload(); } catch (error) { notify(error.message, true); } };
  const toggle = async task => { try { await API(`/api/admin/x/tasks/${task.id}`, { method: "PUT", body: JSON.stringify({ ...task, active: !task.active }) }); reload(); } catch (error) { notify(error.message, true); } };
  return <section className="admin-panel" style={{ marginTop: 20 }} data-testid="x-tasks-panel">
    <h2><span>Custom tasks</span><span className="muted" style={{ fontSize: 11 }}>{tasks.length} task{tasks.length === 1 ? "" : "s"}</span></h2>
    <form onSubmit={submit} data-testid="x-task-form">
      <div className="row">
        <div><label>Title</label><input required value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Join our Telegram" data-testid="x-task-title" /></div>
        <div><label>Points</label><input type="number" min="0" required value={form.points} onChange={e => setForm({ ...form, points: e.target.value })} data-testid="x-task-points" /></div>
      </div>
      <label>Description (shown to users)</label><input value={form.text} onChange={e => setForm({ ...form, text: e.target.value })} maxLength={300} data-testid="x-task-text" />
      <div className="row">
        <div><label>Link (optional)</label><input value={form.link} onChange={e => setForm({ ...form, link: e.target.value })} placeholder="https://…" data-testid="x-task-link" /></div>
        <div><label>Verification</label><select value={form.check} onChange={e => setForm({ ...form, check: e.target.value })} data-testid="x-task-check">{CHECKS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
      </div>
      <div className="xr-actions" style={{ marginTop: 14 }}>
        <button className="button" data-testid="x-task-submit">{editing ? "Save task" : "+ Add task"}</button>
        {editing && <button type="button" className="button secondary" onClick={() => { setEditing(null); setForm(EMPTY_TASK); }}>Cancel</button>}
      </div>
    </form>
    <table className="xr-table" style={{ marginTop: 18 }} data-testid="x-tasks-table">
      <thead><tr><th>Task</th><th>Points</th><th>Check</th><th>State</th><th /></tr></thead>
      <tbody>
        {tasks.map(task => <tr key={task.id} data-testid={`x-task-row-${task.id}`}>
          <td><b>{task.title}</b>{task.text && <small style={{ display: "block", color: "var(--ds-muted)" }}>{task.text}</small>}{task.link && <small style={{ display: "block", color: "var(--ds-blue)", wordBreak: "break-all" }}>{task.link}</small>}</td>
          <td>+{task.points}</td>
          <td>{CHECKS.find(([v]) => v === (task.check || "none"))?.[1]}</td>
          <td><span className={`status-pill ${task.active === false ? "inactive" : "active"}`}>{task.active === false ? "hidden" : "live"}</span></td>
          <td><div className="xr-actions">
            <button type="button" className="button secondary" onClick={() => { setEditing(task.id); setForm({ title: task.title, text: task.text || "", link: task.link || "", points: task.points, check: task.check || "none", active: task.active !== false }); }}>Edit</button>
            <button type="button" className="button secondary" onClick={() => toggle(task)}>{task.active === false ? "Show" : "Hide"}</button>
            <button type="button" className="button secondary danger" onClick={() => remove(task.id)} data-testid={`x-task-delete-${task.id}`}>Delete</button>
          </div></td>
        </tr>)}
        {!tasks.length && <tr><td colSpan="5" className="muted">No custom tasks yet. Add one above — it appears in the Tasks panel on the landing page with a "New" badge.</td></tr>}
      </tbody>
    </table>
  </section>;
}

function UserRow({ user, taskDefs, onChange, onDelete }) {
  const [points, setPoints] = useState(user.points);
  const [busy, setBusy] = useState(false);
  useEffect(() => setPoints(user.points), [user.points]);
  const patch = async body => { setBusy(true); try { await onChange(user.x_id, body); } finally { setBusy(false); } };
  return <tr data-testid={`x-user-row-${user.x_id}`}>
    <td><div className="xr-user"><img src={user.profile_image_url || "/assets/robinity-logo.png"} alt="" /><div><b>@{user.username}</b><small>{user.source === "manual" ? "manual entry" : user.name || "—"}</small></div></div></td>
    <td style={{ fontFamily: "var(--ds-font-mono)", fontSize: 11 }}>{user.evm_address ? `${user.evm_address.slice(0, 6)}…${user.evm_address.slice(-4)}` : <span className="muted">not set</span>}</td>
    <td><div className="xr-tasks">{taskDefs.map(task => { const on = Boolean(user.tasks?.[task.id]?.done); return <label key={task.id} className={on ? "on" : ""} title={`+${task.points}`}><input type="checkbox" checked={on} disabled={busy} onChange={() => patch({ tasks: { [task.id]: !on } })} data-testid={`x-user-${user.x_id}-task-${task.id}`} />{task.title || BUILT_IN.find(([id]) => id === task.id)?.[1] || task.id}</label>; })}</div></td>
    <td><div className="xr-actions"><input type="number" min="0" value={points} onChange={e => setPoints(e.target.value)} data-testid={`x-user-${user.x_id}-points`} />
      {String(points) !== String(user.points) && <button type="button" className="button" disabled={busy} onClick={() => patch({ points })} data-testid={`x-user-${user.x_id}-save`}>Save</button>}</div>
      {user.points_adjustment !== 0 && <small className="xr-note">tasks {user.task_points} {user.points_adjustment > 0 ? "+" : "−"} {Math.abs(user.points_adjustment)} manual</small>}</td>
    <td><button type="button" className="button secondary danger" disabled={busy} onClick={() => onDelete(user)} data-testid={`x-user-${user.x_id}-delete`}>Delete</button></td>
  </tr>;
}

function UsersPanel({ notify }) {
  const [data, setData] = useState({ users: [], total: 0, tasks: [] });
  const [query, setQuery] = useState("");
  const [form, setForm] = useState({ username: "", evm_address: "", points: 0 });
  const load = q => API(`/api/admin/x/users?q=${encodeURIComponent(q ?? query)}`).then(setData).catch(error => notify(error.message, true));
  useEffect(() => { const timer = setTimeout(() => load(query), 250); return () => clearTimeout(timer); }, [query]);
  const change = async (id, body) => { try { await API(`/api/admin/x/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }); load(); } catch (error) { notify(error.message, true); } };
  const remove = async user => { if (!window.confirm(`Delete @${user.username} and their session? This cannot be undone.`)) return; try { await API(`/api/admin/x/users/${user.x_id}`, { method: "DELETE" }); load(); notify(`@${user.username} removed.`); } catch (error) { notify(error.message, true); } };
  const add = async event => {
    event.preventDefault();
    try { await API("/api/admin/x/users", { method: "POST", body: JSON.stringify(form) }); setForm({ username: "", evm_address: "", points: 0 }); load(); notify("User added."); }
    catch (error) { notify(error.message, true); }
  };
  return <>
    <section className="admin-panel" style={{ marginTop: 20 }} data-testid="x-add-user-panel">
      <h2>Add user manually</h2>
      <form onSubmit={add} className="xr-grid" data-testid="x-add-user-form">
        <div><label>X username</label><input required value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} placeholder="@handle" data-testid="x-add-user-username" /></div>
        <div><label>EVM address (optional — needed for leaderboard)</label><input value={form.evm_address} onChange={e => setForm({ ...form, evm_address: e.target.value })} placeholder="0x…" data-testid="x-add-user-evm" /></div>
        <div><label>Starting points</label><input type="number" min="0" value={form.points} onChange={e => setForm({ ...form, points: e.target.value })} data-testid="x-add-user-points" /></div>
      </form>
      <button className="button" style={{ marginTop: 14, width: "auto" }} onClick={add} data-testid="x-add-user-submit">+ Add user</button>
    </section>
    <section className="admin-panel" style={{ marginTop: 20 }} data-testid="x-users-panel">
      <h2><span>Connected users <span className="muted" style={{ fontSize: 12 }}>({data.total})</span></span>
        <input style={{ width: 260, minHeight: 34, margin: 0 }} value={query} onChange={e => setQuery(e.target.value)} placeholder="Search username / name / wallet" data-testid="x-users-search" /></h2>
      <table className="xr-table" data-testid="x-users-table">
        <thead><tr><th>User</th><th>Wallet</th><th>Tasks</th><th>Points</th><th /></tr></thead>
        <tbody>
          {data.users.map(user => <UserRow key={user.x_id} user={user} taskDefs={data.tasks} onChange={change} onDelete={remove} />)}
          {!data.users.length && <tr><td colSpan="5" className="muted" data-testid="x-users-empty">{query ? "No users match this search." : "No users have connected X yet."}</td></tr>}
        </tbody>
      </table>
    </section>
  </>;
}

export default function XRewardsAdmin() {
  const [settings, setSettings] = useState(null);
  const [message, setMessage] = useState(null);
  const notify = (text, error = false) => { setMessage({ text, error }); setTimeout(() => setMessage(null), 5000); };
  const load = () => API("/api/admin/x/settings").then(setSettings).catch(error => notify(error.message, true));
  useEffect(() => { load(); }, []);
  if (!settings) return <section className="admin-panel"><p className="muted">Loading X rewards…</p></section>;
  return <div data-testid="x-rewards-tab">
    {message && <p className={message.error ? "error" : "muted"} role="status" data-testid="x-rewards-message" style={{ marginBottom: 10 }}>{message.text}</p>}
    <SettingsPanel settings={settings} onSaved={setSettings} notify={notify} />
    <TasksPanel tasks={settings.custom_tasks} reload={load} notify={notify} />
    <UsersPanel notify={notify} />
  </div>;
}
