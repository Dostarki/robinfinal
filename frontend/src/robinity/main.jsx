import React from "react";
import { createRoot } from "react-dom/client";
import { ComingSoonButton, LandingV2, LegalV2, MethodologyV2, PublicFooter, PublicHeader } from "./landing.jsx";
import "./styles.css";

const RiskApp = React.lazy(() => import("../risk-ui/App.jsx").then(module => ({ default: module.RiskApp })));
const AdminApp = React.lazy(() => import("./admin.jsx"));

function RouteFallback({ children }) {
  return <main className="console-page"><p className="muted">{children}</p></main>;
}

function ContactPage() {
  return <><PublicHeader legal/><main className="ri-legal"><header><p className="ri-kicker">Robinity Intelligence · Contact</p><h1>Reach the right channel.</h1><p>Official announcements go through the project channel on X. Legal, privacy and security inquiries belong to the dedicated contacts below; the site does not publish an invented operator identity.</p><div className="ri-legal-meta"><span>Contact status</span><span>Operator identity pending verification</span></div></header><div className="ri-legal-layout"><aside><strong>Contact channels</strong><a href="/legal">Legal Center</a><a href="/methodology">Methodology</a><a href="https://x.com/robinityint" target="_blank" rel="noreferrer">Robinity Intelligence on X</a></aside><div className="ri-legal-documents"><section><p className="ri-doc-number">01</p><h2>Project announcements</h2><p>Official product and campaign announcements are published on the verified channel: <a href="https://x.com/robinityint" target="_blank" rel="noreferrer">Robinity Intelligence on X</a>.</p></section><section><p className="ri-doc-number">02</p><h2>Legal, privacy and security</h2><p>A dedicated legal, privacy and security contact will be published together with the operator’s verified legal identity, before any public sale. Until then, do not send private keys or credentials to any address; the site never requests them.</p></section></div></div></main><PublicFooter/></>;
}

function ConsolePage() {
  return <><PublicHeader legal/><main className="console-page"><div className="eyebrow">Robinity Intelligence</div><h1>Curve Console</h1><p className="muted">Use Intelligence for research. Authorized infrastructure operations are available from the protected admin workspace.</p><ComingSoonButton className="button"/></main><PublicFooter/></>;
}

function App() {
  const path = window.location.pathname;
  if (path.includes("risk") || path === "/intelligence") return <React.Suspense fallback={<RouteFallback>Loading Intelligence…</RouteFallback>}><RiskApp/></React.Suspense>;
  if (path.includes("admin")) return <React.Suspense fallback={<RouteFallback>Loading admin workspace…</RouteFallback>}><AdminApp/></React.Suspense>;
  if (path.includes("legal")) return <LegalV2/>;
  if (path === "/contact") return <ContactPage/>;
  if (path === "/methodology") return <MethodologyV2/>;
  if (path.includes("index") || path === "/console") return <ConsolePage/>;
  return <LandingV2/>;
}

createRoot(document.getElementById("root")).render(<App/>);
