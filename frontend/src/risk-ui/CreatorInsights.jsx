import React, { useEffect, useState } from 'react';

const format = value => value == null ? 'Unavailable' : Number(value).toLocaleString('en-US',{maximumFractionDigits:6});
const short = address => address.slice(0,6) + '…' + address.slice(-4);
const date = value => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleDateString('en-US',{month:'short',day:'numeric'}) : 'Unknown';
const explorers = {ethereum:'https://etherscan.io',base:'https://basescan.org',arbitrum:'https://arbiscan.io',optimism:'https://optimistic.etherscan.io',bsc:'https://bscscan.com',polygon:'https://polygonscan.com'};
const explorer = (chain,address) => chain === 'solana' ? 'https://solscan.io/account/' + address : explorers[chain] + '/address/' + address;
function Missing({children}) { return <div className="insight-missing"><span className="missing-mark">—</span><p>{children}</p></div>; }

export default function CreatorInsights({report}) {
  const [state,setState] = useState({loading:true});
  useEffect(()=>{
    setState(report.insights ? {data:report.insights} : {error:'Creator data was unavailable for this assessment.'});
  },[report.chain,report.address,report.analyzedAt]);
  return <section className="creator-insights enter" style={{'--delay':'1450ms'}} aria-label="Creator and wallet analysis">
    <div className="section-title"><h3>Behind the token</h3><span>{state.loading ? 'Reading wallet signals' : 'Creator intelligence'}</span></div>
    {state.loading ? <div className="insights-skeleton" role="status" aria-label="Loading creator and wallet data"><div/><div/><div/></div> : state.error ? <Missing>{state.error}</Missing> : <Insights data={state.data}/>}
  </section>;
}
function Insights({data}) {
  const {creator,balances,balanceHistory,launches,movements,exchangeUsage,rugHistory} = data;
  const available = data.coverage.filter(item=>item.state === 'available').length;
  const verifiedPumpDeployer = creator?.platform === 'pump.fun';
  return <>
    <div className="creator-identity insight-card enter">
      <div className="insight-label">{verifiedPumpDeployer ? 'VERIFIED PUMP.FUN DEPLOYER' : 'CREATOR / DEPLOYER'}</div>
      {creator ? <><a className="creator-address" href={explorer(data.chain,creator.address)} target="_blank" rel="noreferrer">{short(creator.address)} <span>↗</span></a><code>{creator.address}</code><p>{creator.verification}</p>{creator.createdAt && <small>Created {date(creator.createdAt)}</small>}</> : <Missing>No creator address has been verified for this token. Pool, LP, and authority wallets are excluded.</Missing>}
    </div>
    <div className="insight-grid">
      <div className="insight-card enter" style={{'--delay':'100ms'}}><div className="insight-label">{verifiedPumpDeployer ? 'DEPLOYER WALLET HOLDINGS' : 'CURRENT WALLET HOLDINGS'}</div>
        {balances ? <>{balances.totalUsd != null && <div className="insight-number">${format(balances.totalUsd)}<small>sampled holdings value</small></div>}{balances.items.length ? <div className="holdings-list">{balances.items.slice(0,5).map((item,i)=><div key={i}><span>{item.symbol || 'Unknown asset'}</span><strong>{format(item.balance)}</strong></div>)}</div> : <p className="quiet-note">No holdings returned in this sample.</p>}<p className="insight-note">{balances.note}</p></> : <Missing>Current balance data is unavailable.</Missing>}
      </div>
      <div className="insight-card enter" style={{'--delay':'200ms'}}><div className="insight-label">EXCHANGE ACTIVITY</div>
        {exchangeUsage ? <><div className="exchange-stats"><div><strong>{format(exchangeUsage.swapTransactions)}</strong><span>Observed swaps</span></div><div><strong>{exchangeUsage.cexTransfers == null ? '—' : exchangeUsage.cexTransfers}</strong><span>Labeled CEX transfers</span></div></div>{exchangeUsage.labels.length > 0 && <div className="exchange-labels">{exchangeUsage.labels.map(label=><span key={label}>{label}</span>)}</div>}<p className="insight-note">{exchangeUsage.note}</p></> : <Missing>Verified exchange activity is unavailable for this wallet.</Missing>}
      </div>
    </div>
    <details className="insight-card insight-details enter" style={{'--delay':'300ms'}} open><summary>Previous launches <span>{launches ? launches.items.length + ' observed' : 'Unavailable'} <b>＋</b></span></summary>
      {launches ? <>{launches.items.length ? <div className="launch-list">{launches.items.map(item=><a key={item.address} href={explorer(data.chain,item.address)} target="_blank" rel="noreferrer"><div><strong>{item.symbol || item.name}</strong><small>{item.kind} · {short(item.address)}</small></div><span>{date(item.createdAt)} ↗</span></a>)}</div> : <p className="quiet-note">No other deployments were returned in this limited sample.</p>}<p className="insight-note">{launches.note}</p></> : <Missing>Launch history is unavailable. This does not mean the creator has no prior launches.</Missing>}
    </details>
    {balanceHistory && <div className="insight-card enter" style={{'--delay':'350ms'}}><div className="insight-label">HISTORICAL SOL BALANCE</div><div className="movements-list">{balanceHistory.items.map(item=><div key={item.time}><span>{date(item.time)}</span><strong className="incoming">{format(item.balance)} {item.symbol}</strong></div>)}</div><p className="insight-note">{balanceHistory.note}</p></div>}
    <details className="insight-card insight-details enter" style={{'--delay':'400ms'}}><summary>Recent balance movements <span>{movements ? movements.items.length + ' movements' : 'Unavailable'} <b>＋</b></span></summary>
      {movements ? <>{movements.items.length ? <div className="movements-list">{movements.items.map((item,i)=><div key={i}><span>{date(item.time)}</span><strong className={item.amount < 0 ? 'outgoing' : 'incoming'}>{item.amount > 0 ? '+' : ''}{format(item.amount)} {item.symbol}</strong></div>)}</div> : <p className="quiet-note">No native movements returned in this sample.</p>}<p className="insight-note">{movements.note}</p></> : <Missing>Balance history is unavailable. No historical values have been estimated.</Missing>}
    </details>
    <div className="insight-card rug-history enter" style={{'--delay':'500ms'}}><div><div className="insight-label">VERIFIED RUG HISTORY</div><p>{rugHistory.note}</p></div><div className="rug-stat"><strong>{rugHistory.percent == null ? '—' : rugHistory.percent + '%'}</strong><span>{rugHistory.evaluated} evaluated outcomes</span></div></div>
    <details className="coverage-details"><summary><span className={'coverage-dot ' + (available ? 'available' : '')}/>Data coverage <span>{available}/{data.coverage.length} connections available</span></summary><div>{data.coverage.map((item,i)=><p key={i}><strong>{item.provider}</strong><span className={item.state}>{item.state === 'unconfigured' ? 'Not connected' : item.state === 'available' ? 'Available' : 'Unavailable'}</span><small>{item.note}</small></p>)}</div></details>
  </>;
}
