(() => {
  const banner = document.getElementById('planner-update');
  if (!banner) return;
  let revision = null, dirty = false, waiting = false;
  document.querySelectorAll('form input:not([type="hidden"]), form select, form textarea').forEach(field => {
    field.addEventListener('input', () => { dirty = true; });
    field.addEventListener('change', () => { dirty = true; });
  });
  document.querySelectorAll('form').forEach(form => form.addEventListener('submit', () => { waiting = true; }));
  document.getElementById('planner-reload').addEventListener('click', () => location.reload());
  async function check() {
    if (document.hidden || waiting) return;
    try {
      const response = await fetch('/api/state/', {cache:'no-store', signal:AbortSignal.timeout(5000)});
      if (!response.ok) return;
      const state = await response.json();
      if (revision === null) revision = state.revision;
      else if (state.revision !== revision) {
        const editorOpen = !document.querySelector('[data-dinner-app]')?.hidden;
        if (dirty || editorOpen) banner.hidden = false;
        else location.reload();
      }
    } catch { /* The next check retries automatically. */ }
  }
  check(); setInterval(check, 3000);
})();
