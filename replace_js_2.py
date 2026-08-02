import re

with open('content.js', 'r') as f:
    js = f.read()

# 1. Add syncLevelOverlay function right before buildOverlay
sync_fn = """function syncLevelOverlay() {
    if (!overlayEl || !levelOverlayEl) return;
    const rect = overlayEl.getBoundingClientRect();
    levelOverlayEl.style.top = (rect.bottom + 8) + 'px';
    levelOverlayEl.style.left = rect.left + 'px';
    levelOverlayEl.style.width = rect.width + 'px';
  }

  function buildOverlay"""
js = re.sub(r"function buildOverlay", sync_fn, js)

# 2. Modify toggle in buildOverlay to sync
toggle_repl = """overlayEl.querySelector('.bxph-toggle').addEventListener('click', () => {
      collapsed = !collapsed;
      overlayEl.classList.toggle('bxph-collapsed', collapsed);
      chrome.storage.local.set({ bxph_collapsed: collapsed });
      setTimeout(syncLevelOverlay, 10); // sync after layout updates
    });"""
js = re.sub(r"overlayEl\.querySelector\('\.bxph-toggle'\)\.addEventListener\('click',\s*\(\) => \{.*?chrome\.storage\.local\.set\(\{ bxph_collapsed: collapsed \}\);\s*\}\);", toggle_repl, js, flags=re.DOTALL)

# 3. Simplify makeDraggable
drag_repl = """function makeDraggable(el, handle) {
    let dragging = false;
    let startMouseX = 0;
    let startMouseY = 0;
    let startLeftEl = 0;
    let startTopEl = 0;

    handle.addEventListener('mousedown', (e) => {
      dragging = true;
      const rect = el.getBoundingClientRect();
      startMouseX = e.clientX;
      startMouseY = e.clientY;
      startLeftEl = rect.left;
      startTopEl = rect.top;
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!dragging) return;
      const dx = e.clientX - startMouseX;
      const dy = e.clientY - startMouseY;

      el.style.left = `${startLeftEl + dx}px`;
      el.style.top = `${startTopEl + dy}px`;
      el.style.right = 'auto';
      syncLevelOverlay();
    });

    document.addEventListener('mouseup', () => {
      if (!dragging) return;
      dragging = false;
      savePosition(el);
    });
  }"""
js = re.sub(r"function makeDraggable\(el, handle\) \{.*?(?=function buildLevelOverlay\(\) \{)", drag_repl + "\n\n  ", js, flags=re.DOTALL)

# 4. Update buildLevelOverlay
level_build_repl = """function buildLevelOverlay() {
    levelOverlayEl = document.createElement('div');
    levelOverlayEl.id = 'bxph-level-overlay';
    levelOverlayEl.innerHTML = `
      <div id="bxph-level-header" class="bxph-level-header">
        <span>Level up</span>
        <span class="bxph-header-icons">
          <span class="bxph-toggle" title="Minimizar/expandir">▾</span>
        </span>
      </div>
      <div class="bxph-body">
        <div class="bxph-config-row">
          <select id="bxph-main-select"></select>
        </div>
        <div id="bxph-level-list"></div>
      </div>
    `;
    document.body.appendChild(levelOverlayEl);

    levelListEl = levelOverlayEl.querySelector('#bxph-level-list');
    const mainSelectEl = levelOverlayEl.querySelector('#bxph-main-select');

    mainSelectEl.addEventListener('change', () => {
      mainIndex = parseInt(mainSelectEl.value, 10) || 0;
      chrome.storage.local.set({ bxph_main_index: mainIndex });
      renderLevelOverlay();
    });

    levelOverlayEl.querySelector('.bxph-toggle').addEventListener('click', () => {
      levelCollapsed = !levelCollapsed;
      levelOverlayEl.classList.toggle('bxph-collapsed', levelCollapsed);
      chrome.storage.local.set({ bxph_level_collapsed: levelCollapsed });
    });

    chrome.storage.local.get(
      ['bxph_level_collapsed', 'bxph_main_index'],
      (res) => {
        if (res.bxph_level_collapsed) {
          levelCollapsed = true;
          levelOverlayEl.classList.add('bxph-collapsed');
        }
        if (typeof res.bxph_main_index === 'number') mainIndex = res.bxph_main_index;
        renderLevelOverlay();
      }
    );
  }"""
js = re.sub(r"function buildLevelOverlay\(\) \{.*?(?=function renderLevelOverlay\(\) \{)", level_build_repl + "\n\n  ", js, flags=re.DOTALL)

# 5. Update renderLevelOverlay UI
render_level_repl = """function renderLevelOverlay() {
    if (!levelOverlayEl) return;

    const members = findPartyMembers();
    const mainSelectEl = levelOverlayEl.querySelector('#bxph-main-select');

    if (members.length === 0) {
      mainSelectEl.innerHTML = '';
      levelListEl.innerHTML = '<div class="bxph-hint">Nenhum personagem encontrado.</div>';
      return;
    }

    if (mainIndex >= members.length) mainIndex = 0;

    // Repopula o select mantendo a seleção atual
    mainSelectEl.innerHTML = members
      .map((m, i) => `<option value="${i}" ${i === mainIndex ? 'selected' : ''}>${m.label}</option>`)
      .join('');

    const nonMainCount = Math.max(members.length - 1, 1);
    const mainShare = mainPercent / 100;
    const otherShare = members.length > 1 ? (1 - mainShare) / nonMainCount : 1;

    levelListEl.innerHTML = members
      .map((m, i) => {
        const share = i === mainIndex ? mainShare : otherShare;
        const effectiveXph = lastRealXph * share;

        let etaStr = '–';
        if (m.missingXp !== null && effectiveXph > 0) {
          etaStr = formatDuration(m.missingXp / effectiveXph);
        }
        const percentStr = m.percent !== null ? `${m.percent}%` : '0%';
        const roleTag = i === mainIndex ? ' ★' : '';
        
        return `
          <div class="bxph-level-row-compact">
            <div class="bxph-level-text-row">
              <span class="bxph-level-name">${m.label}${roleTag}</span>
              <span class="bxph-level-eta">${etaStr}</span>
            </div>
            <div class="bxph-level-progress-bg">
              <div class="bxph-level-progress-fill" style="width: ${percentStr}"></div>
            </div>
          </div>
        `;
      })
      .join('');
  }"""
js = re.sub(r"function renderLevelOverlay\(\) \{.*?(?=function findGameXphValue\(\) \{)", render_level_repl + "\n\n  ", js, flags=re.DOTALL)

# 6. Add syncLevelOverlay to init observer
init_find = """const ro = new ResizeObserver(() => {
      try {
        const winDef = WINDOWS.find((w) => w.key === selectedWindow) || WINDOWS[2];
        drawGraph('bxph-canvas-xp', xphHistory, 107, 255, 176, winDef);
        drawGraph('bxph-canvas-gold', goldhHistory, 255, 215, 106, winDef);
      } catch(e) {}
    });"""
init_repl = """const ro = new ResizeObserver(() => {
      syncLevelOverlay();
      try {
        const winDef = WINDOWS.find((w) => w.key === selectedWindow) || WINDOWS[2];
        drawGraph('bxph-canvas-xp', xphHistory, 107, 255, 176, winDef);
        drawGraph('bxph-canvas-gold', goldhHistory, 255, 215, 106, winDef);
      } catch(e) {}
    });"""
js = js.replace(init_find, init_repl)
js = js.replace('buildLevelOverlay();\n    chrome.storage.local.get', 'buildLevelOverlay();\n    syncLevelOverlay();\n    chrome.storage.local.get')

with open('content.js', 'w') as f:
    f.write(js)
