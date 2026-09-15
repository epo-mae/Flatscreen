(() => {
  if (!document.getElementById('pair-code')) return;
  const start = Date.now();
  async function check() {
    if (Date.now() - start > 600000) { document.getElementById('pair-status').textContent = 'Generate a new code if this one has expired.'; return; }
    try {
      const r = await fetch('/api/state/?view=display', {cache:'no-store', signal:AbortSignal.timeout(5000)});
      if (r.ok) { location.reload(); return; }
    } catch { /* Pairing resumes after the connection returns. */ }
    setTimeout(check, 2000);
  }
  check();
})();

