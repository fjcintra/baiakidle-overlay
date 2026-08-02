import re

# ------------- content.js -------------
with open('content.js', 'r') as f:
    js = f.read()

# 1. Update buildLevelOverlay
build_level_find = r"function buildLevelOverlay\(\) \{.*?(?=function renderLevelOverlay\(\) \{)"
build_level_repl = """function buildLevelOverlay() {
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
        <div id="bxph-level-list"></div>
      </div>
    `;
    document.body.appendChild(levelOverlayEl);

    levelListEl = levelOverlayEl.querySelector('#bxph-level-list');

    levelOverlayEl.querySelector('.bxph-toggle').addEventListener('click', () => {
      levelCollapsed = !levelCollapsed;
      levelOverlayEl.classList.toggle('bxph-collapsed', levelCollapsed);
      chrome.storage.local.set({ bxph_level_collapsed: levelCollapsed });
    });

    chrome.storage.local.get(
      ['bxph_level_collapsed'],
      (res) => {
        if (res.bxph_level_collapsed) {
          levelCollapsed = true;
          levelOverlayEl.classList.add('bxph-collapsed');
        }
        renderLevelOverlay();
      }
    );
  }"""
js = re.sub(build_level_find, build_level_repl + "\n\n  ", js, flags=re.DOTALL)

# 2. Update renderLevelOverlay
render_level_find = r"function renderLevelOverlay\(\) \{.*?(?=function findGameXphValue\(\) \{)"
render_level_repl = """function renderLevelOverlay() {
    if (!levelOverlayEl) return;

    const members = findPartyMembers();

    if (members.length === 0) {
      levelListEl.innerHTML = '<div class="bxph-hint">Nenhum personagem encontrado.</div>';
      return;
    }

    const nonMainCount = Math.max(members.length - 1, 1);
    const mainShare = mainPercent / 100;
    const otherShare = members.length > 1 ? (1 - mainShare) / nonMainCount : 1;

    levelListEl.innerHTML = members
      .map((m, i) => {
        const share = i === 0 ? mainShare : otherShare;
        const effectiveXph = lastRealXph * share;

        let etaStr = '–';
        if (m.missingXp !== null && effectiveXph > 0) {
          etaStr = formatDuration(m.missingXp / effectiveXph);
        }
        const percentStr = m.percent !== null ? `${m.percent}%` : '0%';
        
        // Limpar "lvl" ou "Lvl" da string
        const cleanName = m.label.replace(/lvl\s*/i, '').trim();
        
        const rowClass = i === 0 ? 'bxph-level-row-compact bxph-level-main' : 'bxph-level-row-compact';

        return `
          <div class="${rowClass}">
            <div class="bxph-level-text-row">
              <span class="bxph-level-name">${cleanName}</span>
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
js = re.sub(render_level_find, render_level_repl + "\n\n  ", js, flags=re.DOTALL)

# 3. Fix drawGraph canvas sizing
draw_find = """    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0) return; // not visible
    canvas.width = rect.width;"""
draw_repl = """    const parentWidth = canvas.parentElement.clientWidth;
    if (parentWidth === 0) return; // not visible
    canvas.width = parentWidth;"""
js = js.replace(draw_find, draw_repl)

with open('content.js', 'w') as f:
    f.write(js)


# ------------- overlay.css -------------
with open('overlay.css', 'r') as f:
    css = f.read()

# Add main char gold styling
main_style = """
/* Highlight Main Character (Gold) */
.bxph-level-main .bxph-level-name,
.bxph-level-main .bxph-level-eta {
  color: #ffd76a;
}
.bxph-level-main .bxph-level-progress-fill {
  background: #ffd76a;
}
"""
css += main_style

# Remove .bxph-config-row as it's no longer needed
css = re.sub(r"\.bxph-config-row \{.*?(?=\/\* Level Up Compact UI \*\/)", "", css, flags=re.DOTALL)

with open('overlay.css', 'w') as f:
    f.write(css)

