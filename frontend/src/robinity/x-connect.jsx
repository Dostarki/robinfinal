import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";

const API = "/api/x";
const api = (path, options = {}) => fetch(`${API}${path}`, { credentials: "include", headers: { "Content-Type": "application/json" }, ...options }).then(async res => {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Error(data.detail || `Request failed (${res.status})`);
  return data;
});

function Toast({ message, tone = "info", onClose }) {
  useEffect(() => { const timer = setTimeout(onClose, 6000); return () => clearTimeout(timer); }, []);
  return createPortal(<div className={`ri-soon-toast ri-toast-${tone}`} role="status" data-testid="x-toast">
    <p>{message}</p>
    <button type="button" className="ri-soon-toast-close" aria-label="Dismiss notification" data-testid="x-toast-close" onClick={onClose}>×</button>
  </div>, document.body);
}

function EvmForm({ onSaved, notify }) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const valid = /^0x[a-fA-F0-9]{40}$/.test(value.trim());
  const submit = async event => {
    event.preventDefault();
    if (!valid) return notify("Enter a valid EVM address (0x + 40 hex characters).", "error");
    setBusy(true);
    try { const data = await api("/evm", { method: "POST", body: JSON.stringify({ address: value.trim() }) }); onSaved(data.user); notify("EVM address saved.", "success"); }
    catch (error) { notify(error.message, "error"); }
    finally { setBusy(false); }
  };
  return <form className="ri-evm-form" onSubmit={submit} data-testid="evm-form">
    <p className="ri-kicker">Step 1 · Wallet</p>
    <h3>Enter your EVM address</h3>
    <p>Rewards are tied to this wallet. You only need to enter it once — it cannot be changed later.</p>
    <input value={value} onChange={event => setValue(event.target.value)} placeholder="0x…" spellCheck={false} autoComplete="off" data-testid="evm-address-input" />
    <button type="submit" className="ri-button ri-button-primary" disabled={busy} data-testid="evm-address-save-button">{busy ? "Saving…" : "Save address"}</button>
  </form>;
}

const TASKS = cfg => [
  { id: "follow", title: `Follow @${cfg.target_username}`, text: "Follow the official Robinity Intelligence account on X.", action: "Follow", intent: `https://x.com/intent/follow?screen_name=${cfg.target_username}` },
  { id: "like_rt", title: "Like & repost the announcement", text: "Like and repost the pinned announcement post.", action: "Open post", intent: cfg.tweet_url || null },
  { id: "quote", title: "Quote the announcement", text: "Share the announcement with a quote post of your own.", action: "Quote", intent: cfg.tweet_url ? `https://x.com/intent/post?${new URLSearchParams({ text: cfg.quote_text, url: cfg.tweet_url })}` : null }
].map(task => ({ ...task, points: cfg.points?.[task.id] ?? 0 }));

const ANDROID = /Android/i.test(navigator.userAgent);
// Android: intent:// forces the installed X app (falls back to the web URL). iOS/desktop: plain https link (universal link opens the X app when installed).
const appLink = url => {
  if (!ANDROID) return url;
  const u = new URL(url);
  return `intent://${u.host}${u.pathname}${u.search}#Intent;scheme=https;package=com.twitter.android;S.browser_fallback_url=${encodeURIComponent(url)};end`;
};

function TaskCard({ task, state, onVerify, notify }) {
  const [opened, setOpened] = useState(false);
  const [busy, setBusy] = useState(false);
  const done = state?.done;
  const open = event => { if (!task.intent) { event.preventDefault(); return notify("This task link is not configured yet.", "error"); } setOpened(true); };
  const verify = async () => { setBusy(true); try { await onVerify(task.id); } finally { setBusy(false); } };
  return <li className={`ri-task${done ? " is-done" : ""}`} data-testid={`task-${task.id}`}>
    <div><strong>{task.title} <span className="ri-task-points" data-testid={`task-${task.id}-points`}>+{task.points} pts</span></strong><p>{task.text}</p></div>
    {done ? <span className="ri-task-done" data-testid={`task-${task.id}-done`}>✓ Done · +{task.points}</span> : <div className="ri-task-actions">
      <a className="ri-button ri-button-quiet" href={task.intent ? appLink(task.intent) : "#"} target={ANDROID ? undefined : "_blank"} rel="noopener noreferrer" onClick={open} data-testid={`task-${task.id}-open-button`}>{task.action} ↗</a>
      <button type="button" className="ri-button ri-button-primary" onClick={verify} disabled={busy || !opened} title={opened ? "" : "Open the task first"} data-testid={`task-${task.id}-verify-button`}>{busy ? "Checking…" : "Verify"}</button>
    </div>}
  </li>;
}

function TasksPanel({ user, cfg, setUser, notify, onClose }) {
  useEffect(() => { const onKey = event => event.key === "Escape" && onClose(); window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, [onClose]);
  const verify = async id => {
    try { const data = await api(`/tasks/${id}/verify`, { method: "POST" }); setUser(data.user); notify(`Task completed. +${data.points_awarded} points!`, "success"); }
    catch (error) { notify(error.message, "error"); }
  };
  const tasks = TASKS(cfg);
  const completed = tasks.filter(task => user.tasks?.[task.id]?.done).length;
  const maxPoints = tasks.reduce((sum, task) => sum + task.points, 0);
  return createPortal(<div className="ri-modal-backdrop" onClick={onClose} data-testid="tasks-modal-backdrop">
    <section className="ri-modal" role="dialog" aria-modal="true" aria-label="Tasks" onClick={event => event.stopPropagation()} data-testid="tasks-modal">
      <header><div><p className="ri-kicker">Tasks</p><h2>Complete the tasks</h2></div><button type="button" className="ri-soon-toast-close" aria-label="Close" onClick={onClose} data-testid="tasks-modal-close">×</button></header>
      {!user.evm_address ? <EvmForm onSaved={setUser} notify={notify} /> : <>
        <div className="ri-points-card" data-testid="tasks-points-card"><span>Your points</span><strong data-testid="tasks-user-points">{user.points ?? 0}</strong><small>of {maxPoints} available</small></div>
        <div className="ri-task-meta"><span data-testid="tasks-evm-address">Wallet · {user.evm_address.slice(0, 6)}…{user.evm_address.slice(-4)}</span><span data-testid="tasks-progress">{completed}/{tasks.length} completed</span></div>
        <ul className="ri-task-list">{tasks.map(task => <TaskCard key={task.id} task={task} state={user.tasks?.[task.id]} onVerify={verify} notify={notify} />)}</ul>
      </>}
    </section>
  </div>, document.body);
}

function LeaderboardPanel({ user, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { const onKey = event => event.key === "Escape" && onClose(); window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, [onClose]);
  useEffect(() => { api("/leaderboard").then(setData).catch(err => setError(err.message)); }, []);
  const medal = rank => rank <= 3 ? ["🥇", "🥈", "🥉"][rank - 1] : `#${rank}`;
  return createPortal(<div className="ri-modal-backdrop" onClick={onClose} data-testid="leaderboard-modal-backdrop">
    <section className="ri-modal" role="dialog" aria-modal="true" aria-label="Leaderboard" onClick={event => event.stopPropagation()} data-testid="leaderboard-modal">
      <header><div><p className="ri-kicker">Leaderboard</p><h2>Top 10 participants</h2></div><button type="button" className="ri-soon-toast-close" aria-label="Close" onClick={onClose} data-testid="leaderboard-modal-close">×</button></header>
      {data && <div className="ri-task-meta"><span data-testid="leaderboard-total">{data.total_participants} participant{data.total_participants === 1 ? "" : "s"}</span><span>Follow +{data.points.follow} · Like & RT +{data.points.like_rt} · Quote +{data.points.quote}</span></div>}
      {error && <p className="ri-lb-empty" data-testid="leaderboard-error">{error}</p>}
      {data && data.entries.length === 0 && <p className="ri-lb-empty" data-testid="leaderboard-empty">No participants yet. Connect X, complete the tasks and be the first on the board.</p>}
      {data && data.entries.length > 0 && <ol className="ri-lb-list" data-testid="leaderboard-list">
        {data.entries.map(entry => <li key={entry.x_id} className={`ri-lb-row${user?.x_id === entry.x_id ? " is-me" : ""}`} data-testid={`leaderboard-row-${entry.rank}`}>
          <span className="ri-lb-rank">{medal(entry.rank)}</span>
          <img src={entry.profile_image_url || "/assets/robinity-logo.png"} alt="" />
          <span className="ri-lb-user"><strong>@{entry.username}</strong>{user?.x_id === entry.x_id && <em>you</em>}<small>{entry.completed}/3 tasks</small></span>
          <span className="ri-lb-points" data-testid={`leaderboard-points-${entry.rank}`}>{entry.points} <small>pts</small></span>
        </li>)}
      </ol>}
      {!data && !error && <p className="ri-lb-empty">Loading…</p>}
    </section>
  </div>, document.body);
}

export function XConnect() {
  const [user, setUser] = useState(null);
  const [cfg, setCfg] = useState(null);
  const [tasksOpen, setTasksOpen] = useState(false);
  const [boardOpen, setBoardOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const notify = (message, tone = "info") => setToast({ id: Date.now(), message, tone });
  useEffect(() => {
    api("/me").then(data => setUser(data.user)).catch(() => {});
    api("/config").then(setCfg).catch(() => setCfg({ configured: false, target_username: "RobinityInt" }));
    const params = new URLSearchParams(window.location.search);
    if (params.get("x_error")) notify("X connection failed. Please try again.", "error");
    if (params.get("x_connected")) notify("X account connected.", "success");
    if (params.has("x_error") || params.has("x_connected")) window.history.replaceState({}, "", window.location.pathname);
  }, []);
  const connect = () => {
    if (cfg && !cfg.configured) return notify("X connection is not available yet. Stay tuned on X (@robinityint).", "error");
    window.location.href = `${API}/auth/login`;
  };
  const logout = async () => { await api("/logout", { method: "POST" }); setUser(null); setTasksOpen(false); };
  return <div className="ri-header-x" data-testid="x-connect-area">
    <button type="button" className="ri-button ri-button-quiet ri-lb-button" onClick={() => setBoardOpen(true)} data-testid="leaderboard-button">Leaderboard</button>
    {user ? <>
      <button type="button" className="ri-button ri-button-quiet ri-tasks-button" onClick={() => setTasksOpen(true)} data-testid="tasks-button">Tasks{user.points ? <span className="ri-tasks-pts" data-testid="tasks-button-points">{user.points} pts</span> : null}</button>
      <div className="ri-x-profile" data-testid="x-profile">
        <img src={user.profile_image_url || "/assets/robinity-logo.png"} alt={`@${user.username}`} data-testid="x-profile-image" />
        <span data-testid="x-profile-username">@{user.username}</span>
        <button type="button" onClick={logout} aria-label="Disconnect X" data-testid="x-disconnect-button">×</button>
      </div>
    </> : <button type="button" className="ri-button ri-button-quiet ri-x-button" onClick={connect} data-testid="x-connect-button"><span aria-hidden="true">𝕏</span> Connect X</button>}
    {tasksOpen && user && cfg && <TasksPanel user={user} cfg={cfg} setUser={setUser} notify={notify} onClose={() => setTasksOpen(false)} />}
    {boardOpen && <LeaderboardPanel user={user} onClose={() => setBoardOpen(false)} />}
    {toast && <Toast key={toast.id} message={toast.message} tone={toast.tone} onClose={() => setToast(null)} />}
  </div>;
}
