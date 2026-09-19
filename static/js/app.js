(() => {
  'use strict';
  const app = document.getElementById('shopping-app');
  if (!app) return;
  const pairedDisplay = app.dataset.mode === 'display';
  const display = pairedDisplay || app.dataset.mode === 'preview';
  const $ = id => document.getElementById(id);
  const snapshotKey = 'flatscreen.display.v1';
  const pendingKey = `flatscreen.pending.${app.dataset.member}`;
  let state = null, etag = '', fetching = false, busy = false, presenceBusy = false, failures = 0;
  let lastSuccess = null, editing = null, pending = null, retrying = false;
  const storage = {
    get(key, session = false) { try { return JSON.parse((session ? sessionStorage : localStorage).getItem(key)); } catch { return null; } },
    set(key, value, session = false) { try { (session ? sessionStorage : localStorage).setItem(key, JSON.stringify(value)); } catch { /* Private browsing may disable storage. */ } },
    remove(key, session = false) { try { (session ? sessionStorage : localStorage).removeItem(key); } catch {} }
  };
  function node(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function button(text, label, fn, cls = 'text-button') {
    const b = node('button', cls, text); b.type = 'button'; b.setAttribute('aria-label', label);
    b.addEventListener('click', fn); return b;
  }
  function connection(online, message) {
    $('connection-status').textContent = message;
    $('connection-status').parentElement.classList.toggle('offline', !online);
    if (display && $('display-freshness')) $('display-freshness').textContent = online ? 'Live household information' : staleMessage();
  }
  function staleMessage() {
    return lastSuccess ? `Offline · last updated ${new Date(lastSuccess).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}` : 'Offline · waiting for connection';
  }
  function feedback(message, action, label = 'Retry') {
    if (display) return;
    const box = $('feedback'); box.replaceChildren(document.createTextNode(message)); box.hidden = false;
    if (action) box.append(button(label, label, action));
    else box.append(button('×', 'Dismiss message', () => { box.hidden = true; }));
  }
  function render() {
    if (!state) return;
    $('household-name').textContent = state.household;
    const remaining = state.items.filter(i => !i.purchased);
    const bought = state.items.filter(i => i.purchased);
    $('remaining-count').textContent = remaining.length;
    const list = $('shopping-list'); list.replaceChildren();
    const visible = display ? remaining.slice(0, 4) : remaining;
    visible.forEach((item, index) => list.append(row(item, index)));
    if (!remaining.length) list.append(node('p', 'empty', display ? 'All stocked up. Lovely.' : 'All stocked up. Add the next thing we need.'));
    if (display) {
      $('display-overflow').textContent = remaining.length > visible.length ? `+ ${remaining.length - visible.length} more on the shared list` : 'Add something from your personal device.';
      renderDinner();
      renderEvents();
      renderNotice();
      renderWeather();
      renderChores();
      renderPresence();
      tick();
    } else {
      renderToday();
      $('purchased-count').textContent = bought.length;
      $('purchased-list').replaceChildren(...bought.map(row));
      $('purchased-section').hidden = !bought.length;
      $('clear-purchased').disabled = !bought.length;
      $('clear-all').disabled = !state.items.length;
      $('member-list').replaceChildren(...state.members.map(m => {
        const chip = node('span', 'member-chip'); chip.append(node('span', 'avatar', m.initials), document.createTextNode(m.name)); return chip;
      }));
      const me = state.members.find(member => member.is_self);
      const current = me?.presence || 'UNKNOWN';
      $('presence-copy').textContent = current === 'HOME' ? 'The household knows you’re home.' : current === 'OUT' ? 'The household knows you’re out.' : 'Your presence has not been set yet.';
      $('presence-home').classList.toggle('secondary', current !== 'HOME');
      $('presence-out').classList.toggle('secondary', current !== 'OUT');
      $('presence-home').setAttribute('aria-pressed', String(current === 'HOME'));
      $('presence-out').setAttribute('aria-pressed', String(current === 'OUT'));
    }
  }
  function renderToday() {
    const tonight = (state.dinners || []).find(plan => plan.date === state.local_date);
    $('today-dinner').textContent = !tonight ? 'Dinner is undecided' : !tonight.happening ? 'No shared dinner tonight' : tonight.cook ? `${tonight.cook} is cooking` : 'Cook not decided';
    $('today-dinner-detail').textContent = tonight?.happening ? [tonight.meal, tonight.time ? formatTime(tonight.time) : ''].filter(Boolean).join(' · ') : '';
    const me = state.members.find(member => member.is_self);
    const mine = (state.chores || []).filter(chore => !chore.assigned_to_id || chore.assigned_to_id === me?.id).slice(0, 2);
    $('today-chores').textContent = mine.length ? `${mine.length} ${mine.length === 1 ? 'responsibility' : 'responsibilities'}` : 'Nothing assigned today';
    $('today-chores-detail').textContent = mine.map(chore => `${chore.title} · ${chore.due_label}`).join(' / ');
    const event = state.events?.[0];
    $('today-event').textContent = event?.title || 'Nothing coming up';
    $('today-event-detail').textContent = event ? `${event.countdown}${event.time ? ` · ${formatTime(event.time)}` : ''}` : '';
    const notice = state.notices?.[0];
    $('today-notice').textContent = notice?.title || 'No active notices';
    $('today-notice-detail').textContent = notice?.message || '';
    $('today-notice-card').classList.toggle('important', notice?.importance === 'important');
  }
  function renderDinner() {
    const box = $('dinner-content');
    const tonight = (state.dinners || []).find(plan => plan.date === state.local_date);
    box.replaceChildren();
    $('dinner-time').textContent = tonight?.time ? formatTime(tonight.time) : '';
    if (!tonight) {
      box.append(node('p', 'dinner-main', 'Dinner hasn’t been decided.'));
      box.append(node('p', 'dinner-support', 'Open the household plan to choose a cook and meal.'));
      return;
    }
    if (!tonight.happening) {
      box.append(node('p', 'dinner-main', 'No shared dinner tonight.'));
      box.append(node('p', 'dinner-support', 'Dinner has been marked as cancelled.'));
      return;
    }
    box.append(node('p', 'dinner-main', tonight.cook ? `${tonight.cook} is cooking` : 'Cook not decided'));
    box.append(node('p', 'dinner-meal', tonight.meal || 'Meal not decided'));
    const next = (state.dinners || []).find(plan => plan.date > state.local_date && plan.happening);
    if (next) {
      const label = dateLabel(next.date);
      box.append(node('p', 'dinner-support', `${label} · ${next.cook || 'Cook not decided'}${next.meal ? ` · ${next.meal}` : ''}`));
    }
  }
  function renderEvents() {
    const list = $('display-events-list'); list.replaceChildren();
    for (const event of state.events || []) {
      const row = node('div', 'display-event-row');
      const timing = node('div', 'display-event-timing');
      timing.append(node('strong', '', event.countdown), node('span', '', event.time ? formatTime(event.time) : event.category));
      const copy = node('div', 'display-event-copy');
      copy.append(node('span', 'display-event-title', event.title));
      if (event.creator) copy.append(node('small', 'display-event-creator', `Added by ${event.creator}`));
      row.append(timing, copy);
      list.append(row);
    }
    if (!state.events?.length) list.append(node('p', 'empty', 'Nothing coming up.'));
  }
  function renderNotice() {
    const box = $('display-notice');
    const notice = state.notices?.[0];
    box.replaceChildren(); box.hidden = !notice;
    if (!notice) return;
    box.className = `display-notice ${notice.importance === 'important' ? 'important' : ''}`;
    box.append(node('p', 'eyebrow', notice.importance === 'important' ? 'IMPORTANT HOUSE NOTE' : 'HOUSE NOTE'));
    box.append(node('strong', '', notice.title), node('span', '', notice.message));
  }
  function renderWeather() {
    const box = $('display-weather');
    const weather = state.weather;
    box.replaceChildren();
    if (!weather?.available) {
      box.append(node('p', 'weather-unavailable', weather?.disabled ? 'Today’s weather is ready to connect in Settings.' : `Weather for ${weather?.location || 'your location'} is unavailable.`));
      return;
    }
    const heading = node('div', 'weather-heading');
    const copy = node('div', '');
    copy.append(node('p', 'eyebrow', `TODAY · ${weather.location}${weather.stale ? ' · LAST UPDATE' : ''}`), node('strong', '', weather.description));
    heading.append(copy, node('span', 'weather-temperature', `${weather.temperature}°`));
    box.append(heading);
    const metrics = node('div', 'weather-metrics');
    [['High', `${weather.high}°`], ['Low', `${weather.low}°`], ['Feels', `${weather.feels_like}°`], ['UV', String(weather.uv)]].forEach(([label, value]) => {
      const metric = node('span', 'weather-metric');
      metric.append(node('small', '', label), node('b', '', value));
      metrics.append(metric);
    });
    box.append(metrics);
    if (weather.alerts?.length) box.append(node('p', 'weather-alert', weather.alerts.join(' · ')));
    box.append(node('small', 'weather-source', 'Forecast: Open-Meteo · values rounded'));
  }
  function formatTime(value) {
    const [hour, minute] = value.split(':').map(Number);
    const date = new Date(2000, 0, 1, hour, minute);
    return new Intl.DateTimeFormat('en-NZ', {hour:'numeric', minute:'2-digit'}).format(date);
  }
  function dateLabel(value) {
    const [year, month, day] = value.split('-').map(Number);
    return new Intl.DateTimeFormat('en-NZ', {weekday:'short', day:'numeric', month:'short'}).format(new Date(year, month - 1, day));
  }
  function renderPresence() {
    const list = $('display-presence-list');
    list.replaceChildren();
    for (const member of state.members || []) {
      const row = node('div', `display-presence-person presence-${member.presence.toLowerCase()}`);
      row.append(node('span', 'display-avatar', member.initials));
      const identity = node('div', 'display-presence-name');
      identity.append(node('strong', '', member.name), node('span', '', member.presence === 'UNKNOWN' ? 'Not set' : member.presence === 'HOME' ? 'At home' : 'Out'));
      row.append(identity, node('span', 'presence-indicator'));
      list.append(row);
    }
    if (!state.members?.length) list.append(node('p', 'empty', 'No active household members.'));
  }
  function renderChores() {
    const list = $('display-chores-list');
    list.replaceChildren();
    for (const chore of state.chores || []) {
      const row = node('div', `display-chore-row${chore.overdue ? ' overdue' : ''}`);
      const due = node('span', 'display-chore-due', chore.due_label);
      const copy = node('div', 'display-chore-copy');
      copy.append(node('strong', '', chore.title), node('span', '', `${chore.assigned_to} · ${chore.repeat}`));
      row.append(due, copy); list.append(row);
    }
    if (!state.chores?.length) list.append(node('p', 'empty', 'Everything is taken care of.'));
  }
  function row(item, index) {
    const r = node('div', `shopping-row${item.purchased ? ' purchased' : ''}`);
    if (display) r.append(node('span', 'display-item-number', String(index + 1).padStart(2, '0')));
    else {
      const check = button(item.purchased ? '✓' : '', `${item.purchased ? 'Reopen' : 'Mark purchased'}: ${item.name}`, () => send({action:'purchase', id:item.id, version:item.version, purchased:!item.purchased}), 'check-button');
      check.setAttribute('aria-pressed', String(item.purchased)); r.append(check);
    }
    const copy = node('div', 'item-copy'); copy.append(node('span', 'item-name', item.name));
    if (!display) copy.append(node('span', 'item-note', item.note || `Added by ${item.added_by}`));
    r.append(copy);
    if (display) r.append(node('span', 'display-quantity', `×${item.quantity}`));
    else {
      const quantity = node('div', 'quantity-control');
      const minus = button('−', `Decrease quantity of ${item.name}`, () => send({action:'quantity', id:item.id, version:item.version, delta:-1}));
      minus.disabled = item.quantity === 1;
      const plus = button('+', `Increase quantity of ${item.name}`, () => send({action:'quantity', id:item.id, version:item.version, delta:1}));
      plus.disabled = item.quantity === 999;
      quantity.append(minus, node('span', '', item.quantity), plus); r.append(quantity);
      const menu = node('details', 'item-menu'); const summary = node('summary', '', '···'); summary.setAttribute('aria-label', `Options for ${item.name}`);
      const actions = node('div', 'menu-actions'); actions.append(button('Edit', `Edit ${item.name}`, () => { menu.open = false; edit(item); }), button('Remove', `Remove ${item.name}`, () => send({action:'delete', id:item.id, version:item.version}), 'text-button danger'));
      menu.append(summary, actions); r.append(menu);
    }
    return r;
  }
  async function refresh(force = false) {
    if (fetching) return;
    fetching = true;
    try {
      const response = await fetch(`/api/state/${pairedDisplay ? '?view=display' : ''}`, {headers: etag && !force ? {'If-None-Match':etag} : {}, cache:'no-store', signal:AbortSignal.timeout(8000)});
      if (response.status === 401 || response.status === 403) {
        if (pairedDisplay) { storage.remove(snapshotKey); state = null; $('shopping-list').replaceChildren(node('p', 'empty', 'Display access ended. Reconnect this screen.')); }
        else storage.remove(pendingKey, true);
        location.replace(pairedDisplay ? '/display/' : '/login/'); return;
      }
      if (!response.ok && response.status !== 304) throw new Error('unavailable');
      lastSuccess = new Date().toISOString(); failures = 0;
      connection(true, 'Connected · updates automatically');
      if (response.status !== 304) {
        state = await response.json(); etag = response.headers.get('ETag'); render();
      }
      if (pairedDisplay && state) storage.set(snapshotKey, {state, lastSuccess});
    } catch {
      failures++; connection(false, staleMessage());
    } finally { fetching = false; }
  }
  async function loop() {
    if (!document.hidden) await refresh();
    setTimeout(loop, Math.min(30000, 2000 * Math.pow(2, Math.min(failures, 4))));
  }
  function csrf() { return document.querySelector('[name=csrfmiddlewaretoken]').value; }
  async function send(payload) {
    if (busy) return false;
    if (pending && !retrying) {
      feedback('An earlier change is awaiting confirmation. Retry it first.', retryPending); return false;
    }
    busy = true;
    const body = pending || {...payload, operation_id:crypto.randomUUID()};
    pending = body; storage.set(pendingKey, body, true);
    let result;
    try {
      const response = await fetch('/api/shopping/', {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken':csrf()}, body:JSON.stringify(body), signal:AbortSignal.timeout(10000)});
      if (response.status >= 500) throw new Error('server');
      result = await response.json();
      pending = null; storage.remove(pendingKey, true);
      if (!response.ok) {
        if (result.duplicate) {
          busy = false;
          const merge = await confirm('Already on the list', `${result.error} The existing note will be kept. Cancel to leave the list unchanged.`, 'Increase quantity');
          if (merge) return send({...payload, duplicate:'merge'});
          return false;
        }
        feedback(result.error || 'Could not save this change.');
        if (editing) $('edit-error').textContent = result.error || 'Could not save.';
        await refresh(true); return false;
      }
      await refresh(true);
      if (result.undo) feedback('Item removed.', () => send({action:'restore', ...result.undo}), 'Undo');
      else feedback('Saved to your household.');
      return true;
    } catch {
      connection(false, staleMessage());
      feedback('Save not confirmed. Your change is kept in this tab; retry safely.', retryPending);
      return false;
    } finally { busy = false; }
  }
  async function retryPending() {
    if (!pending || busy) return;
    retrying = true;
    const wasAdd = pending.action === 'add';
    try { if (await send(pending) && wasAdd) $('add-form').reset(); }
    finally { retrying = false; }
  }
  async function setPresence(status) {
    if (presenceBusy) return;
    presenceBusy = true;
    $('presence-home').disabled = true; $('presence-out').disabled = true;
    try {
      const response = await fetch('/api/presence/', {
        method:'POST',
        headers:{'Content-Type':'application/json', 'X-CSRFToken':csrf()},
        body:JSON.stringify({status, operation_id:crypto.randomUUID()}),
        signal:AbortSignal.timeout(10000),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Could not update your presence.');
      feedback(result.changed ? `You’re marked ${status === 'HOME' ? 'home' : 'out'}.` : `You’re already marked ${status === 'HOME' ? 'home' : 'out'}.`);
      await refresh(true);
    } catch (error) {
      feedback(error.message === 'The operation was aborted.' ? 'Presence update timed out. Check your current state before trying again.' : error.message || 'Could not update your presence.');
    } finally {
      presenceBusy = false; $('presence-home').disabled = false; $('presence-out').disabled = false;
    }
  }
  function confirm(title, description, okLabel) {
    return new Promise(resolve => {
      const dialog = $('confirm-dialog');
      $('confirm-title').textContent = title; $('confirm-description').textContent = description; $('confirm-ok').textContent = okLabel;
      let answer = false;
      $('confirm-ok').onclick = () => { answer = true; dialog.close(); };
      $('confirm-cancel').onclick = () => dialog.close();
      dialog.addEventListener('close', () => resolve(answer), {once:true}); dialog.showModal();
      $('confirm-cancel').focus();
    });
  }
  function edit(item) {
    editing = item; $('edit-name').value = item.name; $('edit-note').value = item.note;
    $('edit-error').textContent = ''; $('edit-dialog').showModal();
  }
  function tick() {
    if (!display || !state) return;
    const now = new Date();
    try {
      $('display-time').textContent = new Intl.DateTimeFormat('en-GB', {timeZone:state.timezone, hour:'2-digit', minute:'2-digit'}).format(now);
      $('display-date').textContent = new Intl.DateTimeFormat('en-NZ', {timeZone:state.timezone, weekday:'long', day:'numeric', month:'long'}).format(now);
      const hour = Number(new Intl.DateTimeFormat('en-GB', {timeZone:state.timezone, hour:'numeric', hourCycle:'h23'}).format(now));
      $('display-greeting').textContent = hour < 5 ? 'Still awake?' : hour < 12 ? 'Good morning.' : hour < 18 ? 'Good afternoon.' : 'Good evening.';
    } catch { connection(false, 'Household timezone unavailable'); }
  }
  if (display) {
    const cached = pairedDisplay ? storage.get(snapshotKey) : null;
    if (cached?.state) { state = cached.state; lastSuccess = cached.lastSuccess; render(); connection(false, staleMessage()); }
    setInterval(tick, 1000);
    if (pairedDisplay && 'serviceWorker' in navigator) navigator.serviceWorker.register('/display/sw.js', {scope:'/display/'}).catch(() => {});
  } else {
    pending = storage.get(pendingKey, true);
    if (pending) feedback('An earlier change needs confirmation.', retryPending);
    $('add-form').addEventListener('submit', async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const payload = {action:'add', name:form.elements.name.value, quantity:Number(form.elements.quantity.value), note:form.elements.note.value};
      if (await send(payload)) { form.reset(); $('item-name').focus(); }
    });
    $('edit-form').addEventListener('submit', async event => {
      event.preventDefault();
      if (await send({action:'edit', id:editing.id, version:editing.version, name:$('edit-name').value, note:$('edit-note').value})) { $('edit-dialog').close(); editing = null; }
    });
    $('cancel-edit').onclick = () => { $('edit-dialog').close(); editing = null; };
    $('presence-home').onclick = () => setPresence('HOME');
    $('presence-out').onclick = () => setPresence('OUT');
    for (const action of ['clear_all', 'clear_purchased']) {
      $(action.replace('_','-')).onclick = async () => {
        const revision = state?.revision;
        if (await confirm(action === 'clear_all' ? 'Clear the entire list?' : 'Clear purchased items?', 'These items will disappear for everyone. Cancel to keep them.', 'Clear items')) await send({action, confirmed:true, revision});
      };
    }
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  window.addEventListener('online', () => refresh());
  loop();
})();
