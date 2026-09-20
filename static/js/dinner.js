(() => {
  'use strict';
  const root = document.querySelector('[data-dinner-app]');
  const dataEl = document.getElementById('dinner-data');
  if (!root || !dataEl) return;
  const data = JSON.parse(dataEl.textContent);
  const $ = selector => root.querySelector(selector);
  const $$ = selector => Array.from(root.querySelectorAll(selector));
  const fallback = document.querySelector('[data-js-fallback]');
  const launch = $('[data-dinner-launch]');
  const picker = $('[data-dinner-picker]');
  const editor = $('[data-dinner-editor]');
  const search = $('[data-dinner-search]');
  const createBtn = $('[data-dinner-create]');
  const nameInput = $('[data-editor-name]');
  const cookSelect = $('[data-editor-cook]');
  const dateInput = $('[data-editor-date]');
  const ingredientsBox = $('[data-ingredients]');
  const addIngredientBtn = $('[data-add-ingredient]');
  const saveBtn = $('[data-save-plan]');
  const shoppingBtn = $('[data-add-shopping]');
  const updateSavedBtn = $('[data-update-saved]');
  const cancelEditorBtn = $('[data-editor-cancel]');
  const feedbackEl = $('[data-editor-feedback]');
  const template = document.getElementById('ingredient-row-template');

  const session = { savedId: null, planId: null, date: data.today };

  function feedback(message, kind = 'error') {
    feedbackEl.textContent = message;
    feedbackEl.hidden = !message;
    feedbackEl.classList.toggle('error', kind === 'error');
  }
  function csrf() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
  }
  async function api(payload) {
    feedback('');
    const body = { ...payload, operation_id: crypto.randomUUID() };
    const response = await fetch('/api/dinners/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(12000),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not save.');
    return result;
  }
  function showPicker() {
    launch.hidden = true;
    picker.hidden = false;
    editor.hidden = true;
    renderPickerGroups();
  }
  function showEditor() {
    launch.hidden = false;
    picker.hidden = true;
    editor.hidden = false;
    updateSavedBtn.hidden = !session.savedId;
    $('[data-editor-eyebrow]').textContent = session.savedId ? session.saved.name : 'NEW DINNER';
    $('[data-editor-title]').textContent = session.savedId ? session.saved.name : 'What are we eating?';
    nameInput.focus();
  }
  function pickerButton(saved) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'dinner-picker-item';
    button.append(Object.assign(document.createElement('strong'), { textContent: saved.name }));
    const meta = document.createElement('span');
    meta.textContent = `${saved.ingredients.length} ${saved.ingredients.length === 1 ? 'ingredient' : 'ingredients'}${saved.uses ? ` · used ${saved.uses} ${saved.uses === 1 ? 'time' : 'times'}` : ''}`;
    button.append(meta);
    button.addEventListener('click', () => openEditorForSaved(saved));
    return button;
  }
  function renderPickerGroups() {
    const query = search.value.trim().toLowerCase();
    const all = data.saved;
    const filtered = query ? all.filter(d => d.name.toLowerCase().includes(query)) : all;
    const recentIds = new Set(data.recent_ids);
    const recent = filtered.filter(d => recentIds.has(d.id));
    const frequent = query ? [] : filtered.filter(d => !recentIds.has(d.id)).sort((a, b) => b.uses - a.uses).slice(0, 4);
    const remaining = filtered.filter(d => !recentIds.has(d.id) && !frequent.includes(d));
    const fill = (el, items, show, className) => {
      el.replaceChildren(...items.map(pickerButton));
      el.parentElement.hidden = !(show && items.length);
    };
    fill($('[data-recent-list]'), recent, !query, 'recent');
    fill($('[data-frequent-list]'), frequent, !query, 'frequent');
    fill($('[data-saved-list]'), remaining, true, 'saved');
  }
  function newRow() {
    const row = template.content.firstElementChild.cloneNode(true);
    row.querySelector('[data-remove]').addEventListener('click', () => row.remove());
    ingredientsBox.append(row);
    return row;
  }
  function fillRow(row, ingredient) {
    if (ingredient) {
      row.querySelector('[data-name]').value = ingredient.name;
      row.querySelector('[data-qty]').value = ingredient.quantity;
      row.querySelector('[data-category]').value = ingredient.category || 'other';
    }
    row.querySelector('[data-name]').focus();
  }
  function readRows() {
    const rows = [];
    for (const row of $$('[data-ingredients] .ingredient-row')) {
      const name = row.querySelector('[data-name]').value.trim();
      if (!name) continue;
      rows.push({
        buy: row.querySelector('[data-buy]').checked,
        name,
        quantity: Math.max(1, Math.min(999, Number(row.querySelector('[data-qty]').value) || 1)),
        category: row.querySelector('[data-category]').value,
      });
    }
    return rows;
  }
  function setEditor(name, cookId, savedId, ingredients, date) {
    session.savedId = savedId;
    session.planId = null;
    session.date = date || data.today;
    session.saved = data.saved.find(d => d.id === savedId) || null;
    nameInput.value = name || '';
    cookSelect.value = cookId === null || cookId === undefined ? '' : String(cookId);
    dateInput.value = session.date;
    ingredientsBox.querySelectorAll('.ingredient-row').forEach(row => row.remove());
    const list = ingredients && ingredients.length ? ingredients : [];
    if (!list.length) {
      fillRow(newRow(), null);
    } else {
      list.forEach(ingredient => fillRow(newRow(), ingredient));
    }
    showEditor();
  }
  function openEditorForSaved(saved) {
    setEditor(saved.name, null, saved.id, saved.ingredients, data.today);
  }
  function openEditorForPlan(plan) {
    const ingredients = (plan.ingredients || []).map(ingredient => ({ ...ingredient, buy: true }));
    session.planId = plan.id;
    session.savedId = plan.saved_dinner_id;
    session.saved = data.saved.find(d => d.id === plan.saved_dinner_id) || null;
    session.date = plan.date;
    nameInput.value = plan.meal || '';
    cookSelect.value = plan.cook_id === null || plan.cook_id === undefined ? '' : String(plan.cook_id);
    dateInput.value = plan.date;
    ingredientsBox.querySelectorAll('.ingredient-row').forEach(row => row.remove());
    if (!ingredients.length) {
      fillRow(newRow(), null);
    } else {
      ingredients.forEach(ingredient => fillRow(newRow(), ingredient));
    }
    showEditor();
  }
  function planPayload(checkedOnly) {
    return {
      action: 'plan',
      date: dateInput.value || data.today,
      name: nameInput.value.trim(),
      cook_id: cookSelect.value ? Number(cookSelect.value) : null,
      ingredients: readRows()
        .filter(row => !checkedOnly || row.buy)
        .map(({ name, quantity, category }) => ({ name, quantity, category })),
    };
  }
  launch.addEventListener('click', () => { search.value = ''; showPicker(); });
  search.addEventListener('input', renderPickerGroups);
  createBtn.addEventListener('click', () => setEditor('', null, null, [], data.today));
  cancelEditorBtn.addEventListener('click', () => { picker.hidden = true; editor.hidden = true; launch.hidden = false; });
  addIngredientBtn.addEventListener('click', () => newRow());
  saveBtn.addEventListener('click', async () => {
    if (!nameInput.value.trim()) { feedback('Give the dinner a name first.'); nameInput.focus(); return; }
    saveBtn.disabled = true;
    try {
      const plan = await api(planPayload(false));
      session.planId = plan.plan.id;
      feedback('Dinner plan saved.');
      setTimeout(() => location.reload(), 500);
    } catch (error) {
      feedback(error.message);
      saveBtn.disabled = false;
    }
  });
  shoppingBtn.addEventListener('click', async () => {
    const rows = readRows();
    const selected = rows.filter(row => row.buy);
    if (!selected.length) { feedback('Tick the ingredients you want to add to shopping first.'); return; }
    shoppingBtn.disabled = true;
    try {
      let planId = session.planId;
      if (!planId) {
        const planned = await api(planPayload(false));
        planId = planned.plan.id;
      }
      const shopping = await api({
        action: 'add_shopping',
        plan_id: planId,
        ingredients: selected.map(({ name, quantity, category }) => ({ name, quantity, category })),
      });
      feedback(`${shopping.count} ${shopping.count === 1 ? 'item' : 'items'} added to the shopping list.`);
      setTimeout(() => location.reload(), 500);
    } catch (error) {
      feedback(error.message);
      shoppingBtn.disabled = false;
    }
  });
  updateSavedBtn.addEventListener('click', async () => {
    if (!session.savedId) return;
    if (!nameInput.value.trim()) { feedback('Give the saved dinner a name first.'); return; }
    updateSavedBtn.disabled = true;
    try {
      await api({
        action: 'update_saved',
        saved_dinner_id: session.savedId,
        name: nameInput.value.trim(),
        ingredients: readRows().map(({ name, quantity, category }) => ({ name, quantity, category })),
      });
      feedback('Saved dinner updated.');
      setTimeout(() => location.reload(), 500);
    } catch (error) {
      feedback(error.message);
      updateSavedBtn.disabled = false;
    }
  });
  document.querySelectorAll('.dinner-edit').forEach(button => {
    button.addEventListener('click', () => {
      const plan = data.plans.find(p => String(p.id) === String(button.dataset.edit));
      if (plan) openEditorForPlan(plan);
    });
  });
  if (!fallback || !data.saved) return;
  fallback.hidden = true;
  root.hidden = false;
})();