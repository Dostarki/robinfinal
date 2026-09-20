export async function queuedAnalysis(asset, onProgress, signal) {
  const response = await fetch('/api/risk/analyses', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(asset), signal });
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Analysis service unavailable.');
  if (data.report) return data;
  const url = '/api/risk/analyses/' + encodeURIComponent(data.jobId);
  return new Promise((resolve, reject) => {
    let finished = false, pollTimer, stream;
    const finish = (error, value) => {
      if (finished) return;
      finished = true; clearTimeout(pollTimer); stream?.close();
      signal?.removeEventListener('abort', abort);
      error ? reject(error) : resolve(value);
    };
    const abort = () => finish(new DOMException('Aborted', 'AbortError'));
    const receive = state => {
      onProgress(state);
      if (state.report) finish(null, state);
      else if (state.status === 'failed') finish(Error(state.error || 'Analysis could not be completed.'));
    };
    const poll = async () => {
      if (finished) return;
      try {
        const res = await fetch(url, { signal });
        if ([401,403,404].includes(res.status)) return finish(Error('Reconnect your wallet to view this analysis.'));
        if (res.ok) receive(await res.json());
      } catch { if (signal?.aborted) return abort(); }
      if (!finished) pollTimer = setTimeout(poll,3000);
    };
    signal?.addEventListener('abort', abort, { once:true });
    if (signal?.aborted) return abort();
    if (typeof EventSource !== 'undefined') {
      stream = new EventSource(url + '/events');
      stream.addEventListener('progress', event => { try { receive(JSON.parse(event.data)); } catch {} });
      stream.onerror = () => stream.close(); // polling remains the recovery path
    }
    receive(data); poll();
  });
}
