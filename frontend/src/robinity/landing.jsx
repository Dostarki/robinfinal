import React, { useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import "./landing.css";
import { XConnect } from "./x-connect.jsx";
import { CURVE_K, CURVE_SUPPLY, CURVE_TARGET, PRICE_END, PRICE_START, quoteCurve } from "./lib/curve-math.js";

const X_URL = "https://x.com/robinityint";
const TOTAL_SUPPLY = 1_000_000_000;

export function ComingSoonButton({ className = "ri-button ri-button-primary" }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const timer = setTimeout(() => setOpen(false), 6000);
    return () => clearTimeout(timer);
  }, [open]);
  return <>
    <button type="button" data-testid="open-intelligence-soon-button" className={className} onClick={() => setOpen(true)}>Open Intelligence <span>↗</span></button>
    {open && createPortal(<div className="ri-soon-toast" role="status" data-testid="soon-toast">
      <p><strong>Coming soon.</strong> Intelligence will be announced shortly — stay tuned on <a href={X_URL} target="_blank" rel="noreferrer" data-testid="soon-toast-x-link">X (@robinityint)</a>.</p>
      <button type="button" className="ri-soon-toast-close" data-testid="soon-toast-close" aria-label="Dismiss notification" onClick={() => setOpen(false)}>×</button>
    </div>, document.body)}
  </>;
}


const usd = value => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: value < 1 ? 6 : 2 }).format(Number.isFinite(value) ? value : 0);
const compact = value => new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Math.max(0, value || 0));
const Logo = () => <img src="/assets/robinity-logo.png" alt="Robinity Intelligence" />;
const SCRAMBLE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$#@%&";

function randomize(text, progress) {
  return String(text).split("").map((char, index) => {
    if (char === " " || char === "\n") return char;
    const threshold = index / Math.max(1, String(text).length);
    return progress > threshold ? char : SCRAMBLE_CHARS[Math.floor(Math.random() * SCRAMBLE_CHARS.length)];
  }).join("");
}

function useReveal(duration = 760) {
  const ref = useRef(null);
  const frame = useRef(0);
  const [progress, setProgress] = useState(1);
  useEffect(() => {
    const element = ref.current;
    if (!element || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    setProgress(0);
    let started = false, start = 0;
    const observer = new IntersectionObserver(([entry]) => {
      if (started || !entry.isIntersecting) return;
      started = true;
      start = performance.now();
      const tick = now => {
        const next = Math.min(1, (now - start) / duration);
        setProgress(next);
        if (next < 1) frame.current = requestAnimationFrame(tick);
      };
      frame.current = requestAnimationFrame(tick);
      observer.disconnect();
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.1 });
    observer.observe(element);
    return () => { observer.disconnect(); cancelAnimationFrame(frame.current); };
  }, [duration]);
  return [ref, progress];
}

function ScrambleText({ as: Tag = "span", children, className }) {
  const text = String(children);
  const [ref, progress] = useReveal(720);
  return <Tag ref={ref} className={["ri-scramble", className].filter(Boolean).join(" ")} aria-label={text}>{progress >= 1 ? text : randomize(text, progress)}</Tag>;
}

function ScrambleNumber({ as: Tag = "span", value, className, prefix = "", suffix = "", decimals = 0 }) {
  const [ref, progress] = useReveal(860);
  const target = Number(value);
  const display = Number.isFinite(target) ? (target * progress).toLocaleString("en-US", { maximumFractionDigits: decimals, minimumFractionDigits: decimals }) : String(value);
  const final = `${prefix}${display}${suffix}`;
  return <Tag ref={ref} className={["ri-scramble", className].filter(Boolean).join(" ")} aria-label={`${prefix}${value}${suffix}`}>{progress >= 1 ? `${prefix}${value}${suffix}` : randomize(final, progress)}</Tag>;
}

const EvidenceDepth = React.lazy(() => import("./evidence-depth.jsx"));
const TokenChart3D = React.lazy(() => import("./token-chart-3d.jsx"));
const BackdropParticles = React.lazy(() => import("./backdrop-particles.jsx"));

export function PublicHeader({ legal = false }) {
  const [active, setActive] = useState("overview");
  useEffect(() => {
    if (legal) return;
    const ids = ["overview", "token", "curve", "mechanics", "rewards"];
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) setActive(visible.target.id);
    }, { rootMargin: "-28% 0px -58% 0px", threshold: [0.05, 0.2, 0.5] });
    ids.forEach(id => { const element = document.getElementById(id); if (element) observer.observe(element); });
    return () => observer.disconnect();
  }, [legal]);
  const links = legal ? [{ href: "/landing", label: "Overview" }, { href: "/intelligence", label: "Intelligence" }] : [{ href: "#overview", label: "Overview", id: "overview" }, { href: "#curve", label: "Curve", id: "curve" }, { href: "#rewards", label: "Rewards", id: "rewards" }];
  return <header className="ri-header">
    <a className="ri-brand" href="/landing"><span><Logo /></span><strong>Robinity</strong><em>Intelligence</em></a>
    <nav className="ri-floating-nav" aria-label="Primary navigation">
      {links.map(link => <a key={link.label} href={link.href} className={!legal && active === link.id ? "is-active" : ""}>{link.label}</a>)}
    </nav>
    <XConnect />
  </header>;
}

export function PublicFooter() {
  return <footer className="ri-footer">
    <div className="ri-footer-brand"><Logo /><div><strong>Robinity Intelligence</strong><p>Token research with context.</p></div></div>
    <div className="ri-footer-links"><a href="/methodology">Methodology</a><a href="/legal">Legal</a><a href="/legal#rewards">Rewards</a><a href={X_URL} target="_blank" rel="noreferrer" aria-label="Robinity Intelligence on X">𝕏</a></div>
    <p className="ri-footer-note">Information is for research only. Verify contracts and transaction details independently before signing.</p>
    <small>© 2026 Robinity Intelligence</small>
  </footer>;
}

function EvidenceField() {
  const [selected, setSelected] = useState("security");
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const copy = {
    security: ["Security signals", "Review permissions, transfer controls and liquidity warnings in one place."],
    creator: ["Creator context", "See available creator activity and related token history without treating missing data as a clean bill of health."],
    score: ["Score breakdown", "Understand how individual findings affect a score and where the evidence stops."]
  };
  const entries = Object.entries(copy);
  const activate = key => {
    setSelected(key);
    setOpen(true);
  };
  const handleBlur = event => {
    if (!wrapRef.current?.contains(event.relatedTarget)) setOpen(false);
  };
  return <div ref={wrapRef} className={`ri-evidence${open ? " is-report-open" : ""}`} aria-label="Product report preview" onMouseLeave={() => setOpen(false)} onBlur={handleBlur}>
    <React.Suspense fallback={null}><EvidenceDepth /></React.Suspense>
    <div className="ri-evidence-grid" aria-hidden="true" />
    <svg className="ri-evidence-lines" viewBox="0 0 620 420" aria-hidden="true">
      <defs>
        <filter id="ri-wire-glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.2" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <path className="ri-cable ri-cable-bg" d="M116 211 C188 211 206 96 306 96 S384 96 474 96"/>
      <path className="ri-cable ri-cable-bg" d="M116 211 C196 211 216 211 306 211 S386 211 474 211"/>
      <path className="ri-cable ri-cable-bg" d="M116 211 C188 211 208 326 306 326 S388 326 474 326"/>
      <path className="ri-cable ri-cable-flow ri-flow-a" d="M116 211 C188 211 206 96 306 96 S384 96 474 96"/>
      <path className="ri-cable ri-cable-flow ri-flow-b" d="M116 211 C196 211 216 211 306 211 S386 211 474 211"/>
      <path className="ri-cable ri-cable-flow ri-flow-c" d="M116 211 C188 211 208 326 306 326 S388 326 474 326"/>
      <circle className="ri-cable-node ri-cable-source" cx="116" cy="211" r="12"/>
      <circle className="ri-cable-node" cx="306" cy="96" r="6"/>
      <circle className="ri-cable-node" cx="306" cy="211" r="6"/>
      <circle className="ri-cable-node" cx="306" cy="326" r="6"/>
    </svg>
    <div className="ri-evidence-core"><span>Token</span><strong><ScrambleText>0x…F2c</ScrambleText></strong></div>
    <div className="ri-evidence-actions" role="tablist" aria-label="Report preview sections">
      {entries.map(([key, value]) => <button key={key} role="tab" aria-selected={selected === key} onMouseEnter={() => activate(key)} onFocus={() => activate(key)} onClick={() => activate(key)}><i />{value[0]}</button>)}
    </div>
    <div className="ri-evidence-report" aria-live="polite"><div className="ri-report-top"><span>Signal detail</span><b><ScrambleNumber value={78} /> <small>/ 100</small></b></div><div className="ri-report-bar"><i /></div><p>{copy[selected][0]}</p><small>{copy[selected][1]}</small></div>
    <div className="ri-wire-field" aria-hidden="true">
      {Array.from({ length: 18 }, (_, index) => <span key={index} style={{ "--x": `${8 + (index * 23) % 92}%`, "--y": `${10 + (index * 37) % 80}%`, "--d": `${index * -0.23}s`, "--r": `${(index % 5) * 22 - 44}deg` }} />)}
    </div>
  </div>;
}

function CurveGraph({ math }) {
  const id = useId().replace(/:/g, "");
  const x = sold => 42 + sold / CURVE_SUPPLY * 536;
  const y = price => 214 - (price - PRICE_START) / (PRICE_END - PRICE_START) * 168;
  const startX = x(math.priorSold), finalX = x(math.finalSold);
  return <div className="ri-curve-graph"><svg viewBox="0 0 620 250" role="img" aria-label="Linear marginal token price rising from 0.0001 to 0.0009 US dollars"><defs><linearGradient id={`ri-curve-${id}`} x1="0" x2="1"><stop stopColor="#9bb6cb"/><stop offset="1" stopColor="#ddae8b"/></linearGradient></defs><path className="ri-chart-grid" d="M42 46H578M42 102H578M42 158H578M42 214H578M42 30V220M176 30V220M310 30V220M444 30V220M578 30V220"/><path className="ri-chart-area" d={`M42 214 L578 46 L578 214 Z`} /><path className="ri-chart-line" d="M42 214 L578 46" stroke={`url(#ri-curve-${id})`} /><path className="ri-chart-allocation" d={`M${startX} ${y(PRICE_START + CURVE_K * math.priorSold)} L${finalX} ${y(math.nextPrice)}`} /><line className="ri-chart-marker" x1={startX} x2={startX} y1={y(PRICE_START + CURVE_K * math.priorSold)} y2="220"/><circle className="ri-chart-dot" cx={startX} cy={y(PRICE_START + CURVE_K * math.priorSold)} r="5"/></svg><div className="ri-chart-axis"><span>0 sold · $0.0001</span><span>200M sold · $0.0009</span></div></div>;
}

function useEthQuote() {
  const [state, setState] = useState({ rate: null, at: null, error: false });
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    let active = true;
    const load = async () => { try { const response = await fetch("https://api.coinbase.com/v2/prices/ETH-USD/spot"); const result = await response.json(); const rate = Number(result?.data?.amount); if (!Number.isFinite(rate)) throw Error("Invalid ETH quote"); if (active) setState({ rate, at: Date.now(), error: false }); } catch { if (active) setState(previous => ({ ...previous, error: true })); } };
    load(); const timer = window.setInterval(load, 60_000); return () => { active = false; window.clearInterval(timer); };
  }, []);
  useEffect(() => { const timer = window.setInterval(() => setClock(Date.now()), 10_000); return () => window.clearInterval(timer); }, []);
  return { ...state, ageMs: state.at ? Math.max(0, clock - state.at) : null };
}

function quoteStatus(quote) {
  if (!quote.rate) return quote.error ? "ETH / USD quote is unavailable. USD estimates remain available." : "Loading ETH / USD quote…";
  const seconds = Math.floor((quote.ageMs || 0) / 1000);
  const freshness = seconds < 10 ? "updated just now" : `updated ${seconds}s ago`;
  return `ETH / USD ${usd(quote.rate)} · ${quote.error ? `last quote ${freshness}` : freshness}`;
}

function CurveExplorer() {
  const [raise, setRaise] = useState(0), [mode, setMode] = useState("USD"), [amount, setAmount] = useState("100");
  const quote = useEthQuote();
  const contribution = Math.max(0, Number(amount || 0)) * (mode === "ETH" ? (quote.rate || 0) : 1);
  const math = useMemo(() => quoteCurve(raise, contribution), [raise, contribution]);
  const toggle = () => { const currentUsd = mode === "USD" ? Math.max(0, Number(amount || 0)) : Math.max(0, Number(amount || 0)) * (quote.rate || 0); if (!quote.rate) return; const next = mode === "USD" ? "ETH" : "USD"; setMode(next); setAmount(next === "ETH" ? (currentUsd / quote.rate).toFixed(5) : currentUsd.toFixed(2)); };
  const limitReached = math.acceptedUsd < contribution;
  return <section className="ri-curve-section ri-section" id="curve"><div className="ri-curve-heading"><p className="ri-kicker">The curve</p><ScrambleText as="h2">See how your entry changes along the curve.</ScrambleText><ScrambleText as="p">The published curve allocates 200 million tokens as the marginal price rises from $0.0001 to $0.0009.</ScrambleText></div><div className="ri-curve-layout"><article className="ri-curve-card"><CurveGraph math={math}/><div className="ri-curve-legend"><span><i className="ri-legend-current" />Before commitment</span><span><i className="ri-legend-allocation" />Allocation range</span></div></article><form className="ri-curve-controls" onSubmit={event => event.preventDefault()}><div className="ri-control-label"><label htmlFor="raise">Raise before your commitment</label><strong>{usd(raise)}</strong></div><input id="raise" type="range" min="0" max={CURVE_TARGET} step="100" value={raise} onChange={event => setRaise(Number(event.target.value))}/><div className="ri-range-labels"><span>$0</span><span>$100K</span></div><div className="ri-input-row"><label htmlFor="commitment">Your commitment</label><button type="button" onClick={toggle} disabled={!quote.rate}>Use {mode === "USD" ? "ETH" : "USD"}</button></div><div className="ri-amount-field"><input id="commitment" type="number" min="0" step={mode === "USD" ? "1" : "0.001"} value={amount} onChange={event => setAmount(event.target.value)} /><span>{mode}</span></div><p className={`ri-quote ${quote.error ? "is-error" : ""}`} aria-live="polite">{quoteStatus(quote)}</p>{limitReached && <p className="ri-limit-note">The remaining allocation limits this estimate to {usd(math.acceptedUsd)}.</p>}<div className="ri-curve-results"><div><span>Tokens allocated</span><b>{compact(math.tokens)}</b></div><div><span>Average price</span><b>{math.tokens ? usd(math.averagePrice) : "—"}</b></div><div><span>Next price</span><b>{usd(math.nextPrice)}</b></div><div><span>Raise after</span><b>{usd(math.raisedAfterUsd)}</b></div></div></form></div><p className="ri-curve-disclosure">Estimates use the published curve parameters. Network fees, execution order, contract rounding and actual sale status can change an on-chain result.</p></section>;
}

function TokenOverview() {
  return <section className="ri-token-section ri-section" id="token"><div className="ri-token-copy"><p className="ri-kicker">Token overview</p><ScrambleText as="h2">The token, in numbers.</ScrambleText><ScrambleText as="p">Supply and allocation information is shown separately from the research product so each claim can be evaluated on its own terms.</ScrambleText><dl className="ri-token-stats"><div><dt>Total supply</dt><dd><ScrambleNumber value={1} suffix="B" /></dd><small><ScrambleNumber value={1000000000} /> units</small></div><div><dt>Presale allocation</dt><dd><ScrambleNumber value={200} suffix="M" /></dd><small><ScrambleNumber value={20} suffix="%" /> · $100,000 curve target</small></div><div><dt>Engagement Rewards</dt><dd><ScrambleNumber value={50} suffix="M" /></dd><small><ScrambleNumber value={5} suffix="%" /> · campaign allocation</small></div><div><dt>Remaining allocation</dt><dd><ScrambleNumber value={750} suffix="M" /></dd><small>Not yet announced</small></div></dl></div><div className="ri-token-visual"><div className="ri-token-chart"><React.Suspense fallback={null}><TokenChart3D /></React.Suspense></div></div></section>;
}

function Mechanics() { return <section className="ri-mechanics ri-section" id="mechanics"><div className="ri-mechanics-title"><p className="ri-kicker">Mechanics</p><ScrambleText as="h2">What happens when you participate.</ScrambleText></div><ol><li><span><ScrambleNumber value={1} prefix="0" /></span><div><ScrambleText as="h3">Verify the network and contract.</ScrambleText><ScrambleText as="p">Review the selected network, contract address and current sale status before connecting a wallet.</ScrambleText></div></li><li><span><ScrambleNumber value={2} prefix="0" /></span><div><ScrambleText as="h3">Review the quote.</ScrambleText><ScrambleText as="p">Check the amount, allocation estimate and transaction recipient before you sign anything.</ScrambleText></div></li><li><span><ScrambleNumber value={3} prefix="0" /></span><div><ScrambleText as="h3">Keep the record.</ScrambleText><ScrambleText as="p">Confirmed activity belongs to the selected deployment and should be independently verifiable on-chain.</ScrambleText></div></li></ol></section>; }

function Rewards() { return <section className="ri-rewards ri-section" id="rewards"><div><p className="ri-kicker">Engagement Rewards</p><ScrambleText as="h2">Contribute to the conversation.</ScrambleText><ScrambleText as="p">50 million tokens are reserved for Engagement Rewards. Eligible contributions earn points; allocations are proportional to each participant’s share of valid points.</ScrambleText><a className="ri-primary-link" href={X_URL} target="_blank" rel="noreferrer">Follow on X <span>↗</span></a></div><div className="ri-reward-formula"><span>Valid user points</span><b>× <ScrambleNumber value={50000000} /></b><i>÷</i><span>Total valid points</span><ScrambleText as="strong">Allocation</ScrambleText><ScrambleText as="small">Campaign eligibility, timing and validation rules will be published before rewards are distributed.</ScrambleText></div></section>; }

function LandingBackdrop() {
  return <div className="ri-page-backdrop" aria-hidden="true">
    <div className="ri-backdrop" />
    <React.Suspense fallback={null}><BackdropParticles /></React.Suspense>
  </div>;
}

export function LandingV2() { return <><LandingBackdrop/><PublicHeader/><main className="ri-landing"><section className="ri-hero ri-section" id="overview"><div className="ri-hero-copy"><p className="ri-kicker">Token research, with context</p><ScrambleText as="h1">Look beyond the ticker.</ScrambleText><ScrambleText as="p">Review token security signals, creator activity and the evidence behind each score—before deciding what to do next.</ScrambleText><div className="ri-hero-actions"><ComingSoonButton/><a href="#token" className="ri-button ri-button-quiet">Explore the token <span>↓</span></a></div></div><EvidenceField/></section><TokenOverview/><CurveExplorer/><Mechanics/><Rewards/></main><PublicFooter/></>; }

export function MethodologyV2() { return <><PublicHeader legal/><main className="ri-methodology"><header><p className="ri-kicker">Robinity Intelligence · Methodology</p><h1>Make the score inspectable.</h1><p>A safety score is a structured summary of detected signals. It helps prioritize research; it is not a guarantee, audit or prediction of an asset’s outcome.</p><div className="ri-legal-meta"><span>Current methodology</span><span>100 means fewer detected risk signals</span></div></header><section className="ri-method-score"><div><p className="ri-kicker">How it starts</p><h2>Start at 100. Subtract for evidence.</h2><p>Each detected risk signal has a published weight. The displayed score is bounded from 0 to 100 after the available signals are evaluated.</p></div><div className="ri-score-equation"><b>100</b><span>−</span><strong>weighted detected signals</strong><span>=</span><b>Safety score</b><small>A lack of detected signals is not proof that a token is safe.</small></div></section><section className="ri-method-grid"><article><p className="ri-kicker">01 · Inputs</p><h2>Signals are tied to evidence.</h2><p>Where supported by the network, reports can include contract permissions, transfer controls, source visibility, tax indicators, liquidity-related data and available creator context.</p></article><article><p className="ri-kicker">02 · Coverage</p><h2>Unknown is not green.</h2><p>Network support and upstream data vary. Missing, stale or partial data should remain visible in a report instead of being silently converted into a positive signal.</p></article><article><p className="ri-kicker">03 · Interpretation</p><h2>Read the breakdown.</h2><p>Use the individual findings, their weights and the evidence gaps before relying on the headline score. Independent verification remains necessary.</p></article></section><section className="ri-method-limits"><p className="ri-kicker">Limits</p><h2>What the score cannot tell you.</h2><ul><li>It cannot identify every exploit, economic attack, undisclosed relationship or future change.</li><li>It cannot replace code review, wallet due diligence or an on-chain transaction review.</li><li>It does not measure investment suitability, expected returns or legal compliance.</li></ul><ComingSoonButton/></section></main><PublicFooter/></>; }

const documents = [
  ["terms", "Terms of Use", <><p>Robinity Intelligence provides website and research interfaces. You are responsible for independently verifying every contract, address, network, quote and transaction before signing through a wallet.</p><p>Information may rely on third-party networks and data providers. Availability, completeness and accuracy are not guaranteed. Do not probe, overload or bypass access controls, and do not represent a score or estimate as a guarantee or as financial advice.</p></>],
  ["privacy", "Privacy Notice", <><p>Public use may process contract addresses, selected networks and technical information needed to operate the service. Analysis history can exist both in browser storage and, where a report is requested from the service, on the application backend.</p><p>Admin access uses a wallet signature and authenticator code. The site does not ask for wallet private keys. API credentials submitted to the protected admin area are stored as encrypted server-side values and displayed back only as masked identifiers.</p><p>Third-party providers may process requests under their own terms. Specific retention periods, data controller identity and an operational privacy contact must be published before a public sale or broader data collection launches.</p></>],
  ["risks", "Risk Disclosures", <><p><strong>Technology and smart-contract risk.</strong> The token operates on a public blockchain. Smart-contract code may contain undiscovered vulnerabilities, and upgrades or forks outside the project’s control can change how the token behaves. Any audit covers a snapshot of the code at a single point in time and does not guarantee the absence of future exploits.</p><p><strong>Liquidity and market risk.</strong> There is no guarantee that a liquid secondary market will develop for the token. The bonding-curve price applies only within the curve contract; any secondary-market price is determined independently and may be significantly lower. Trading volume, market-maker participation and exchange listings are not promised or controlled by the project.</p><p><strong>Regulatory risk.</strong> The legal classification of tokens varies across jurisdictions and may change. Participants are responsible for understanding and complying with the laws applicable to them. The project does not provide legal, tax or investment advice. Future regulatory action could restrict the token’s transferability or the project’s operations.</p><p><strong>Operational and dependency risk.</strong> The platform depends on third-party RPCs, data feeds, hosting providers and external APIs. Outages, rate limits, data inaccuracies or policy changes at any upstream provider may degrade or interrupt the service without advance notice.</p><p><strong>Score and research limitations.</strong> Safety scores are derived from automated signal detection with published weights. A high score is not a safety guarantee; it reflects fewer detected signals at the time of analysis. Missing data is not treated as a positive signal, but the absence of a detected risk does not prove that no risk exists. Independent verification remains the user’s responsibility.</p><p>Curve estimates are mathematical previews based on the published parameters. Network conditions, transaction ordering, fees, rounding and contract behavior can produce a different on-chain result.</p><p>Digital assets can lose all value. Review the specific deployment, contract and participation terms, and consult a qualified professional before participating.</p></>],
  ["token-sale", "Token Sale Terms", <><p>These terms apply only to a sale published from a verified deployment record on this site. No sale is presented here without that record, and this document is not an offer of securities.</p><p>A published sale would state the exact network, contract addresses, the amount of token a commitment buys along the published curve, the cap, the accepted asset, quote validity, and the minimum contribution. Any transaction would be signed directly with the contract; the website never holds funds.</p><p>If a sale is paused or the curve is exhausted, available information reflects the recorded state rather than an assumed continuation. Tax treatment and eligibility are not covered by this document; consult a qualified professional before participating.</p></>],
  ["rewards", "Engagement Rewards Rules", <><p>A proposed allocation of 50,000,000 tokens is reserved for Engagement Rewards. A distribution is only run once campaign timing, eligibility, scoring rules and an identified organizer are published and verified.</p><p>Proposed formula: allocation = 50,000,000 × valid user points ÷ total valid points. If the total valid point pool is zero, no distribution is computed. Invalid, duplicate or sybil-style activity is excluded before the pool is counted.</p><p>No reward is guaranteed today. Points, eligibility, disputes and campaign conditions will be published with the official operator and channel before any distribution.</p></>],
  ["cookies", "Cookies & Storage", <><p>This site stores what is technically required to operate: an authentication cookie only within the protected admin area, and browser storage used to keep analysis history on the request side.</p><p>No advertising, social, or cross-site tracking is added. Requests for market data or security providers may go to selected third parties under their own terms.</p><p>If optional tracking or a consent flow is introduced later, it will be listed in this inventory with a real choice before anything optional loads.</p></>],
  ["third-party", "Third-Party Services", <p>Blockchain RPCs, wallet extensions, market data, security providers and social platforms are independent services. Outages, changed policies and upstream errors can affect the interface. Their use does not imply endorsement.</p>],
  ["contact", "Contact & Changes", <p>Each document carries an effective date and should be reviewed when updated. The official project channel is <a href={X_URL} target="_blank" rel="noreferrer">Robinity Intelligence on X</a>. A dedicated legal, privacy and security contact should be published with the operator’s verified legal identity.</p>]
];

export function LegalV2() { return <><PublicHeader legal/><main className="ri-legal"><header><p className="ri-kicker">Robinity Intelligence · Legal Center</p><h1>Clear information, without invented assurances.</h1><p>These draft public documents explain the website and research interface. They do not establish an investment, custody or advisory relationship.</p><div className="ri-legal-meta"><span>Version 0.2</span><span>Effective: September 18, 2026</span><span>Draft operator details pending verification</span></div></header><div className="ri-legal-layout"><nav className="ri-legal-jumpnav" aria-label="Legal documents">{documents.map(([id, title]) => <a key={id} href={`#${id}`}>{title}</a>)}</nav><div className="ri-legal-documents">{documents.map(([id, title, content]) => <section id={id} key={id}><p className="ri-doc-number">{String(documents.findIndex(item => item[0] === id) + 1).padStart(2, "0")}</p><h2>{title}</h2>{content}</section>)}</div></div></main><PublicFooter/></>; }
