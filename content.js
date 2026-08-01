(function () {
  'use strict';

  // ---------- Config ----------
  const TICK_MS = 1000;
  const MAX_HISTORY_MS = 60 * 60 * 1000; // guarda até 3h de amostras (para o modo "Sessão")
  const WINDOWS = [
    { key: '1h', label: '1h', ms: 60 * 60 * 1000 },
  ];
  const LABEL_REGEX = /^xp\s*gain$/i;

  // ---------- Estado ----------
  let samples = []; // { t: timestamp, delta: number }
  let lastValue = null;
  let selectedWindow = '1h';
  let collapsed = false;
  let overlayFound = false;
  let lastRealXph = 0;

  // Gold (balance)
  let goldSamples = []; // { t: timestamp, delta: number } (delta pode ser negativo)
  let lastGoldValue = null;
  let goldFound = false;

  // Canvas history
  let xphHistory = [];
  let goldhHistory = [];
  let lastGraphUpdate = 0;

  // ---------- Utils ----------
  function parseBRNumber(text) {
    if (!text) return NaN;
    let cleaned = text.replace(/[^\d.,\-]/g, '').trim();
    if (!cleaned) return NaN;
    if (cleaned.includes(',')) {
      // vírgula = decimal, ponto = milhar
      cleaned = cleaned.replace(/\./g, '').replace(',', '.');
    } else {
      // só pontos: assume milhar (formato BR), a menos que pareça decimal (ex: 12.5)
      const parts = cleaned.split('.');
      if (parts.length > 1 && parts[parts.length - 1].length === 3) {
        cleaned = cleaned.replace(/\./g, '');
      }
    }
    const n = parseFloat(cleaned);
    return isNaN(n) ? NaN : n;
  }

  function extractNumberFrom(el) {
    if (!el) return NaN;
    const n = parseBRNumber(el.textContent);
    return n;
  }

  // Acha o elemento "XP Gain" e o valor numérico associado a ele.
  function findXpGainValue() {
    // Método principal: o jogo usa <b id="an-raw"> dentro de <div class="row">
    const direct = document.getElementById('an-raw');
    if (direct) {
      const v = extractNumberFrom(direct);
      if (!isNaN(v)) return v;
    }

    // Fallback: procura por texto, caso o ID mude no futuro
    const candidates = document.querySelectorAll('body *');
    for (const el of candidates) {
      if (el.children.length > 0) continue; // queremos nós "folha"
      const t = (el.textContent || '').trim();
      if (LABEL_REGEX.test(t)) {
        // 1) tenta o próximo irmão
        let sib = el.nextElementSibling;
        while (sib) {
          const v = extractNumberFrom(sib);
          if (!isNaN(v)) return v;
          sib = sib.nextElementSibling;
        }
        // 2) tenta os irmãos dentro do mesmo pai
        const parent = el.parentElement;
        if (parent) {
          for (const child of parent.children) {
            if (child === el) continue;
            const v = extractNumberFrom(child);
            if (!isNaN(v)) return v;
          }
          // 3) tenta o texto do pai inteiro, removendo o rótulo
          const remaining = parent.textContent.replace(t, '').trim();
          const v = parseBRNumber(remaining);
          if (!isNaN(v)) return v;
        }
      }
    }
    return null;
  }

  // Acha o elemento do balance (gold) do jogo.
  function findBalanceValue() {
    const direct = document.getElementById('an-balance');
    if (direct) {
      const v = extractNumberFrom(direct);
      if (!isNaN(v)) return v;
    }
    return null;
  }

  // ---------- Cálculo ----------
  function registerGoldSample(value) {
    const now = Date.now();
    if (lastGoldValue === null) {
      lastGoldValue = value;
      return;
    }
    const delta = value - lastGoldValue;
    if (delta !== 0) {
      // Gold pode subir ou descer (gastos), então não resetamos em deltas negativos.
      goldSamples.push({ t: now, delta });
    }
    lastGoldValue = value;

    const cutoff = now - MAX_HISTORY_MS;
    goldSamples = goldSamples.filter((s) => s.t >= cutoff);
  }

  function computeGoldH(windowMs) {
    const now = Date.now();
    const cutoff = windowMs === Infinity ? 0 : now - windowMs;
    const relevant = goldSamples.filter((s) => s.t >= cutoff);
    if (relevant.length === 0) return { goldh: 0, elapsedSec: 0 };

    const totalGain = relevant.reduce((acc, s) => acc + s.delta, 0);
    const firstT = relevant[0].t;
    const elapsedMs = Math.max(now - firstT, 60000); // 60s warm-up to prevent initial spikes
    const elapsedHours = elapsedMs / 3600000;
    return { goldh: totalGain / elapsedHours, elapsedSec: elapsedMs / 1000 };
  }

  function registerSample(value) {
    const now = Date.now();
    if (lastValue === null) {
      lastValue = value;
      return;
    }
    let delta = value - lastValue;
    if (delta < 0) {
      // Reset de sessão detectado (contador voltou para trás / zerou)
      samples = [];
      delta = value >= 0 ? value : 0;
    }
    if (delta > 0) {
      samples.push({ t: now, delta });
    }
    lastValue = value;

    const cutoff = now - MAX_HISTORY_MS;
    samples = samples.filter((s) => s.t >= cutoff);
  }

  function computeXpH(windowMs) {
    const now = Date.now();
    const cutoff = windowMs === Infinity ? 0 : now - windowMs;
    const relevant = samples.filter((s) => s.t >= cutoff);
    if (relevant.length === 0) return { xph: 0, elapsedSec: 0 };

    const totalGain = relevant.reduce((acc, s) => acc + s.delta, 0);
    const firstT = relevant[0].t;
    const elapsedMs = Math.max(now - firstT, 60000); // 60s warm-up to prevent initial spikes
    const elapsedHours = elapsedMs / 3600000;
    return { xph: totalGain / elapsedHours, elapsedSec: elapsedMs / 1000 };
  }

  function formatNumber(n) {
    return Math.round(n).toLocaleString('pt-BR');
  }

  function formatSignedNumber(n) {
    const rounded = Math.round(n);
    const sign = rounded > 0 ? '+' : rounded < 0 ? '−' : '';
    return `${sign}${Math.abs(rounded).toLocaleString('pt-BR')}`;
  }

  function formatElapsed(sec) {
    if (sec < 60) return `${Math.round(sec)}s`;
    const m = Math.floor(sec / 60);
    const s = Math.round(sec % 60);
    return `${m}m${s > 0 ? s + 's' : ''}`;
  }

  function formatCompact(n) {
    if (isNaN(n) || n === 0) return '0';
    const absN = Math.abs(n);
    const sign = n < 0 ? '-' : '';
    if (absN >= 1e6) return sign + (absN / 1e6).toFixed(1).replace('.0', '') + 'M';
    if (absN >= 1e3) return sign + (absN / 1e3).toFixed(1).replace('.0', '') + 'k';
    return sign + Math.round(absN).toString();
  }

  function formatDuration(hours) {
    if (!isFinite(hours) || hours <= 0) return '—';
    const totalMinutes = hours * 60;
    const days = Math.floor(totalMinutes / 1440);
    const remAfterDays = totalMinutes - days * 1440;
    const hrs = Math.floor(remAfterDays / 60);
    const mins = Math.round(remAfterDays % 60);
    let out = '';
    if (days > 0) out += `${days}d `;
    if (hrs > 0 || days > 0) out += `${hrs}h `;
    out += `${mins}m`;
    return out.trim();
  }

  // Acha os personagens listados (party) com barra de XP e "Faltam X XP para o nível Y"
  const TIP_REGEX = /Faltam\s+([\d.,]+)\s*XP para o n\S*vel\s+(\d+)/i;

  function findPartyMembers() {
    const metas = document.querySelectorAll('.m-meta');
    const result = [];
    let anyBarFound = false;

    metas.forEach((metaEl) => {
      const label = metaEl.textContent.trim();
      if (!label) return;
      const barEl = findBarForMeta(metaEl);
      if (barEl) anyBarFound = true;
      result.push({ label, barEl });
    });

    // Plano B: se a busca por container não achou NENHUMA barra, pareia por ordem
    if (!anyBarFound) {
      const bars = document.querySelectorAll('.bar.xp');
      result.forEach((r, i) => {
        r.barEl = bars[i] || null;
      });
    }

    return result.map(({ label, barEl }) => {
      let missingXp = null;
      let targetLevel = null;
      let percent = null;

      if (barEl) {
        const tip = barEl.getAttribute('data-tip') || '';
        const m = tip.match(TIP_REGEX);
        if (m) {
          missingXp = parseBRNumber(m[1]);
          targetLevel = parseInt(m[2], 10);
        }
        const bEl = barEl.querySelector('b');
        if (bEl) {
          const pm = bEl.textContent.match(/([\d.,]+)\s*%/);
          if (pm) percent = parseFloat(pm[1].replace(',', '.'));
        }
      }

      return { label, missingXp, targetLevel, percent };
    });
  }

  // Sobe pelos ancestrais do .m-meta até achar um container que tenha
  // exatamente um .m-meta (o próprio) e contenha um .bar.xp — isso isola
  // cada personagem mesmo se a estrutura real tiver mais elementos no meio.
  function findBarForMeta(metaEl) {
    let el = metaEl.parentElement;
    let hops = 0;
    while (el && el !== document.body && hops < 8) {
      const metaCount = el.querySelectorAll('.m-meta').length;
      if (metaCount === 1) {
        const bar = el.querySelector('.bar.xp');
        if (bar) return bar;
      } else if (metaCount > 1) {
        // subimos demais e já pegamos outros personagens também; para por aqui
        break;
      }
      el = el.parentElement;
      hops++;
    }
    return null;
  }

  // ---------- UI ----------
  let overlayEl, bodyEl, statusEl, windowsEl;
  let levelOverlayEl, levelListEl, levelCollapsed = false;
  let docked = false;
  let mainIndex = 0;
  const mainPercent = 65; // fixo: principal recebe 65%, o restante divide os 35%

  function getOtherPanel(el) {
    if (el === overlayEl) return levelOverlayEl;
    if (el === levelOverlayEl) return overlayEl;
    return null;
  }

  function setDocked(newVal) {
    docked = newVal;
    chrome.storage.local.set({ bxph_docked: docked });
    updateDockUI();
  }

  function updateDockUI() {
    document.querySelectorAll('.bxph-dock-toggle').forEach((elx) => {
      elx.classList.toggle('bxph-dock-active', docked);
    });
  }

  function savePosition(el) {
    const key = el === overlayEl ? 'bxph_pos' : 'bxph_level_pos';
    chrome.storage.local.set({ [key]: { top: el.style.top, left: el.style.left } });
  }

  function buildOverlay() {
    overlayEl = document.createElement('div');
    overlayEl.id = 'bxph-overlay';
    
    overlayEl.innerHTML = `
      <div id="bxph-header">
        <span>Performance</span>
        <span class="bxph-header-icons">
          <span class="bxph-toggle" title="Minimizar/expandir">▾</span>
        </span>
      </div>
      <div class="bxph-body">
        <div class="bxph-row">
          <span class="bxph-label">XP/h</span>
          <span class="bxph-value" id="bxph-real-xph">–</span>
        </div>
        <canvas id="bxph-canvas-xp" class="bxph-canvas"></canvas>
        <div class="bxph-row">
          <span class="bxph-label">Gold/h</span>
          <span class="bxph-value" id="bxph-gold-h">–</span>
        </div>
        <canvas id="bxph-canvas-gold" class="bxph-canvas"></canvas>
        <div class="bxph-windows" id="bxph-windows"></div>
        <button id="bxph-reset-btn" class="bxph-reset-btn">Reiniciar</button>
        <div id="bxph-status"></div>
      </div>
    `;

    document.body.appendChild(overlayEl);

    bodyEl = overlayEl.querySelector('.bxph-body');
    statusEl = overlayEl.querySelector('#bxph-status');
    windowsEl = overlayEl.querySelector('#bxph-windows');

    WINDOWS.forEach((w) => {
      const btn = document.createElement('button');
      btn.className = 'bxph-win-btn' + (w.key === selectedWindow ? ' bxph-active' : '');
      btn.textContent = w.label;
      btn.dataset.key = w.key;
      btn.addEventListener('click', () => {
        selectedWindow = w.key;
        chrome.storage.local.set({ bxph_window: selectedWindow });
        refreshWindowButtons();
        render();
      });
      windowsEl.appendChild(btn);
    });

    overlayEl.querySelector('#bxph-reset-btn').addEventListener('click', () => {
      xphHistory = [];
      goldhHistory = [];
      samples = [];
      lastValue = null;
      goldSamples = [];
      lastGoldValue = null;
      render();
    });

    

    overlayEl.querySelector('.bxph-toggle').addEventListener('click', () => {
      collapsed = !collapsed;
      overlayEl.classList.toggle('bxph-collapsed', collapsed);
      chrome.storage.local.set({ bxph_collapsed: collapsed });
    });

    makeDraggable(overlayEl, overlayEl.querySelector('#bxph-header'));
    restoreState();
  }

  function refreshWindowButtons() {
    windowsEl.querySelectorAll('.bxph-win-btn').forEach((b) => {
      b.classList.toggle('bxph-active', b.dataset.key === selectedWindow);
    });
  }

  function restoreState() {
    chrome.storage.local.get(['bxph_window', 'bxph_collapsed', 'bxph_pos'], (res) => {
      if (res.bxph_window) {
        selectedWindow = res.bxph_window;
        refreshWindowButtons();
      }
      if (res.bxph_collapsed) {
        collapsed = true;
        overlayEl.classList.add('bxph-collapsed');
      }
      if (res.bxph_pos) {
        overlayEl.style.top = res.bxph_pos.top;
        overlayEl.style.left = res.bxph_pos.left;
        overlayEl.style.right = 'auto';
      }
    });
  }

  function makeDraggable(el, handle) {
    let dragging = false;
    let startMouseX = 0;
    let startMouseY = 0;
    let startLeftEl = 0;
    let startTopEl = 0;
    let other = null;
    let startLeftOther = 0;
    let startTopOther = 0;

    handle.addEventListener('mousedown', (e) => {
      dragging = true;
      const rect = el.getBoundingClientRect();
      startMouseX = e.clientX;
      startMouseY = e.clientY;
      startLeftEl = rect.left;
      startTopEl = rect.top;

      other = docked ? getOtherPanel(el) : null;
      if (other) {
        const orect = other.getBoundingClientRect();
        startLeftOther = orect.left;
        startTopOther = orect.top;
      }
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!dragging) return;
      const dx = e.clientX - startMouseX;
      const dy = e.clientY - startMouseY;

      el.style.left = `${startLeftEl + dx}px`;
      el.style.top = `${startTopEl + dy}px`;
      el.style.right = 'auto';

      if (other) {
        other.style.left = `${startLeftOther + dx}px`;
        other.style.top = `${startTopOther + dy}px`;
        other.style.right = 'auto';
      }
    });

    document.addEventListener('mouseup', () => {
      if (!dragging) return;
      dragging = false;
      savePosition(el);
      if (other) savePosition(other);
      other = null;
    });
  }

  function buildLevelOverlay() {
    levelOverlayEl = document.createElement('div');
    levelOverlayEl.id = 'bxph-level-overlay';
    levelOverlayEl.innerHTML = `
      <div id="bxph-level-header" class="bxph-level-header">
        <span>Tempo p/ Up</span>
        <span class="bxph-header-icons">
          <span class="bxph-dock-toggle" title="Colar painéis">🔗</span>
          <span class="bxph-toggle" title="Minimizar/expandir">▾</span>
        </span>
      </div>
      <div class="bxph-body">
        <div class="bxph-config-row">
          <span class="bxph-label">Principal</span>
          <select id="bxph-main-select"></select>
        </div>
        <div id="bxph-level-list"></div>
        <div class="bxph-hint">Baseado no XP/h real (<span id="bxph-level-window-label"></span>)</div>
      </div>
    `;
    // document.body.appendChild(levelOverlayEl);

    levelListEl = levelOverlayEl.querySelector('#bxph-level-list');
    const mainSelectEl = levelOverlayEl.querySelector('#bxph-main-select');

    mainSelectEl.addEventListener('change', () => {
      mainIndex = parseInt(mainSelectEl.value, 10) || 0;
      chrome.storage.local.set({ bxph_main_index: mainIndex });
      renderLevelOverlay();


    });

    levelOverlayEl.querySelector('.bxph-dock-toggle').addEventListener('click', () => {
      setDocked(!docked);
    });

    levelOverlayEl.querySelector('.bxph-toggle').addEventListener('click', () => {
      levelCollapsed = !levelCollapsed;
      levelOverlayEl.classList.toggle('bxph-collapsed', levelCollapsed);
      chrome.storage.local.set({ bxph_level_collapsed: levelCollapsed });
    });

    makeDraggable(levelOverlayEl, levelOverlayEl.querySelector('#bxph-level-header'));

    chrome.storage.local.get(
      ['bxph_level_collapsed', 'bxph_level_pos', 'bxph_main_index'],
      (res) => {
        if (res.bxph_level_collapsed) {
          levelCollapsed = true;
          levelOverlayEl.classList.add('bxph-collapsed');
        }
        if (res.bxph_level_pos) {
          levelOverlayEl.style.top = res.bxph_level_pos.top;
          levelOverlayEl.style.left = res.bxph_level_pos.left;
          levelOverlayEl.style.right = 'auto';
        } else {
          levelOverlayEl.style.top = '80px';
          levelOverlayEl.style.right = '230px';
        }
        if (typeof res.bxph_main_index === 'number') mainIndex = res.bxph_main_index;
      renderLevelOverlay();


      }
    );
  }

  function renderLevelOverlay() {
    if (!levelOverlayEl) return;
    const winDef = WINDOWS.find((w) => w.key === selectedWindow) || WINDOWS[0];
    levelOverlayEl.querySelector('#bxph-level-window-label').textContent = winDef.label;

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

        const missingStr = m.missingXp !== null ? formatNumber(m.missingXp) : '–';
        let etaStr = '–';
        if (m.missingXp !== null && effectiveXph > 0) {
          etaStr = formatDuration(m.missingXp / effectiveXph);
        }
        const percentStr = m.percent !== null ? `${m.percent}%` : '';
        const roleTag = i === mainIndex ? ' (Principal)' : '';
        return `
          <div class="bxph-level-row">
            <div class="bxph-level-name">${m.label}${roleTag} ${percentStr ? `· ${percentStr}` : ''}</div>
            <div class="bxph-row">
              <span class="bxph-label">Falta</span>
              <span class="bxph-value">${missingStr}</span>
            </div>
            <div class="bxph-row">
              <span class="bxph-label">Tempo p/ Up</span>
              <span class="bxph-value">${etaStr}</span>
            </div>
          </div>
        `;
      })
      .join('');

    if (members.every((m) => m.missingXp === null)) {
      levelListEl.innerHTML +=
        '<div class="bxph-hint">⚠ Achei os nomes, mas não a barra de XP correspondente.</div>';
    }
  }

  function findGameXphValue() {
    // Tenta achar o "XP/h" nativo do jogo (rótulo exato "XP/h", não "XP/h Real")
    const candidates = document.querySelectorAll('body *');
    for (const el of candidates) {
      if (el.children.length > 0) continue;
      const t = (el.textContent || '').trim();
      if (/^xp\/h$/i.test(t)) {
        let sib = el.nextElementSibling;
        while (sib) {
          const v = extractNumberFrom(sib);
          if (!isNaN(v)) return v;
          sib = sib.nextElementSibling;
        }
      }
    }
    return null;
  }

  
  function drawGraph(canvasId, history, r, g, b) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0) return; // not visible
    canvas.width = rect.width;
    canvas.height = 85; // fixed

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (history.length < 2) return;

    // EMA Smoothing
    const smoothed = [];
    let ema = history[0].val;
    const alpha = 0.6; // Sensitivity value to micro-variations
    for (let i = 0; i < history.length; i++) {
      ema = alpha * history[i].val + (1 - alpha) * ema;
      smoothed.push({ t: history[i].t, val: ema });
    }

    const now = Date.now();
    const maxTime = now;
    const minTime = now - 60 * 60 * 1000;

    const rawMin = Math.min(...smoothed.map(h => h.val));
    const rawMax = Math.max(...smoothed.map(h => h.val));
    
    let range = rawMax - rawMin;
    if (range === 0) range = 1;
    
    // Dynamic scale highlighting micro-variations
    let maxVal = rawMax + range * 0.35; // 35% top padding for max text
    let minVal = rawMin - range * 0.35; // 35% bottom padding for min text

    const getX = (t) => ((t - minTime) / (maxTime - minTime)) * canvas.width;
    const getY = (v) => canvas.height - ((v - minVal) / (maxVal - minVal)) * canvas.height;

    ctx.beginPath();
    ctx.strokeStyle = `rgb(${r}, ${g}, ${b})`;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    for (let i = 0; i < smoothed.length; i++) {
      const x = getX(smoothed[i].t);
      const y = getY(smoothed[i].val);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    
    ctx.lineTo(getX(smoothed[smoothed.length - 1].t), canvas.height);
    ctx.lineTo(getX(smoothed[0].t), canvas.height);
    ctx.closePath();
    
    const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
    grad.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.4)`);
    grad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
    ctx.fillStyle = grad;
    ctx.fill();

    // Draw text overlays
    ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
    ctx.font = '9px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText("-1h", 2, canvas.height - 2);
    
    ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
    ctx.textAlign = 'right';
    // Use true max for the text
    ctx.fillText(`Máx: ${formatCompact(rawMax)}/h`, canvas.width - 2, 10);
    // Use true min for the text
    ctx.fillText(`Mín: ${formatCompact(rawMin)}/h`, canvas.width - 2, canvas.height - 2);
  }

  function render() {

    if (!overlayEl) return;
    
    // Fast reactivity: use a 3-minute rolling window for the instantaneous rate calculation
    const REACTIVE_WINDOW_MS = 3 * 60 * 1000;
    
    const { xph, elapsedSec } = computeXpH(REACTIVE_WINDOW_MS);
    lastRealXph = xph;

    overlayEl.querySelector('#bxph-real-xph').textContent = formatNumber(xph);
    
    const { goldh } = computeGoldH(REACTIVE_WINDOW_MS);
    const goldEl = overlayEl.querySelector('#bxph-gold-h');
    if (goldFound) {
      goldEl.textContent = formatSignedNumber(goldh);
      goldEl.classList.remove('bxph-dim');
      goldEl.classList.toggle('bxph-positive', goldh > 0);
      goldEl.classList.toggle('bxph-negative', goldh < 0);
    } else {
      goldEl.textContent = '–';
      goldEl.classList.add('bxph-dim');
      goldEl.classList.remove('bxph-positive', 'bxph-negative');
    }

    if (!overlayFound) {
      statusEl.textContent = '⚠ Não encontrei "XP Gain" na página ainda.';
    } else {
      statusEl.textContent = '';
    }

    const now = Date.now();
    if (now - lastGraphUpdate >= 5000) {
      xphHistory.push({ t: now, val: xph });
      goldhHistory.push({ t: now, val: goldh });
      
      const cutoff = now - 60 * 60 * 1000;
      xphHistory = xphHistory.filter(h => h.t >= cutoff);
      goldhHistory = goldhHistory.filter(h => h.t >= cutoff);

      lastGraphUpdate = now;
    }
    
    try {
      drawGraph('bxph-canvas-xp', xphHistory, 107, 255, 176); // #6bffb0
      drawGraph('bxph-canvas-gold', goldhHistory, 255, 215, 106); // #ffd76a
    } catch (e) {
      console.error('Error drawing canvas', e);
    }

      renderLevelOverlay();


  }

  // Permite que o popup peça um reset dos dados coletados
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.bxph_reset_request) {
      xphHistory = [];
      goldhHistory = [];
      samples = [];
      lastValue = null;
      goldSamples = [];
      lastGoldValue = null;
      render();
    }
  });

  // ---------- Loop ----------
  function tick() {
    const goldVal = findBalanceValue();
    if (goldVal === null) {
      goldFound = false;
    } else {
      goldFound = true;
      registerGoldSample(goldVal);
    }

    const val = findXpGainValue();
    if (val === null) {
      overlayFound = false;
      render();
      return;
    }
    overlayFound = true;
    registerSample(val);
    render();
  }

  function init() {
    buildOverlay();
    buildLevelOverlay();
    chrome.storage.local.get(['bxph_docked'], (res) => {
      docked = !!res.bxph_docked;
      updateDockUI();
    });
    setInterval(tick, TICK_MS);
    const ro = new ResizeObserver(() => {
      try {
        drawGraph('bxph-canvas-xp', xphHistory, 107, 255, 176);
        drawGraph('bxph-canvas-gold', goldhHistory, 255, 215, 106);
      } catch(e) {}
    });
    if (overlayEl) ro.observe(overlayEl);
    tick();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
