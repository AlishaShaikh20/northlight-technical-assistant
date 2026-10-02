
let DOCS = {}, ORDER = [];

// Sends the question to the backend (server.py) and returns { answer, type, sources }
async function askQuestion(q) {
  const r = await fetch('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: q })
  });

  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

const $ = id => document.getElementById(id);
const wrap = $('wrap');
const chat = $('chat');

const esc = s =>
  s.replace(/[&<>"]/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;'
  }[c]));

const inl = s =>
  esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');

function md(t) {
  let h = '', ul = false;

  for (const l of t.split('\n')) {
    if (/^- /.test(l)) {
      if (!ul) {
        h += '<ul>';
        ul = true;
      }
      h += '<li>' + inl(l.slice(2)) + '</li>';
    } else {
      if (ul) {
        h += '</ul>';
        ul = false;
      }

      if (l.trim()) {
        h += '<p>' + inl(l) + '</p>';
      }
    }
  }

  return h + (ul ? '</ul>' : '');
}

const IC = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></svg>';

const BOT = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="8" width="16" height="11" rx="3"/><path d="M12 8V4M9 13h.01M15 13h.01"/></svg>';

const side = $('side');
const scrim = $('scrim');

function renderDocs() {
  $('docs').innerHTML = ORDER.map(f =>
    `<button class="doc" data-f="${f}">
      <i class="di">${IC}</i>
      <span>${esc(DOCS[f].title)}</span>
      <em>PDF</em>
    </button>`
  ).join('');
}

$('docs').onclick = e => {
  const b = e.target.closest('.doc');
  if (b) openDoc(b.dataset.f);
};

function openDoc(f, snip) {
  const d = DOCS[f];
  if (!d) return;

  $('vt').textContent = d.title;
  $('vf').textContent = f;

  let h = esc(d.text);

  if (snip) {
    const re = new RegExp(
      snip.trim()
        .split(/\s+/)
        .map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
        .join('\\s+')
    );

    const m = re.exec(d.text);

    if (m) {
      h =
        esc(d.text.slice(0, m.index)) +
        '<mark id="hit">' +
        esc(m[0]) +
        '</mark>' +
        esc(d.text.slice(m.index + m[0].length));
    }
  }

  $('vb').innerHTML = '<pre>' + h + '</pre>';
  $('view').classList.add('open');

  document.querySelectorAll('.doc').forEach(b =>
    b.classList.toggle('on', b.dataset.f === f)
  );

  closeSide();

  const hit = $('hit');

  if (hit) {
    setTimeout(() =>
      hit.scrollIntoView({
        block: 'center',
        behavior: 'smooth'
      }), 240);
  } else {
    $('vb').scrollTop = 0;
  }
}

function closeDoc() {
  $('view').classList.remove('open');
  document.querySelectorAll('.doc').forEach(b =>
    b.classList.remove('on')
  );
}

$('vc').onclick = closeDoc;

addEventListener('keydown', e => {
  if (e.key === 'Escape') closeDoc();
});

const openSide = () => {
  side.classList.add('open');
  scrim.classList.add('on');
};

const closeSide = () => {
  side.classList.remove('open');
  scrim.classList.remove('on');
};

$('menu').onclick = openSide;
scrim.onclick = closeSide;

$('theme').onclick = () => {
  const r = document.documentElement;
  r.dataset.theme = r.dataset.theme === 'light' ? 'dark' : 'light';
};

const EX = [
  "Where do I request access to a new tool?",
  "What happens to my laptop and account when I leave the company?",
  "How much is the home office stipend and when can I claim it?",
  "I'm on the PPO with a spouse and two kids, what's my monthly cost?",
  "What is the salary band for a senior engineer?"
];

const TEST = [
  ["Documents disagree", EX[0]],
  ["Finds exact numbers", EX[2]],
  ["Handles unclear info", EX[3]],
  ["Refuses when it can't know", EX[4]]
];

function empty() {
  wrap.innerHTML = `
    <div class="empty">
      <h2>Try a question</h2>
      <p>These 4 questions show what the assistant can do. The documents are fictional HR policies for Northlight Analytics, and you can open any of them on the left.</p>
      <div class="ex">
        ${TEST.map(([t, q]) =>
          `<button data-q="${esc(q)}">
            <small>${t}</small>
            ${esc(q)}
          </button>`
        ).join('')}
      </div>
    </div>
  `;

  wrap.querySelector('.ex').onclick = e => {
    const b = e.target.closest('button');
    if (b) ask(b.dataset.q);
  };
}

const bottom = () =>
  chat.scrollTo({
    top: chat.scrollHeight,
    behavior: 'smooth'
  });

let busy = false;

async function ask(q) {
  q = q.trim();

  if (!q || busy) return;

  busy = true;
  $('send').disabled = true;

  if (wrap.querySelector('.empty')) {
    wrap.innerHTML = '';
  }

  wrap.insertAdjacentHTML(
    'beforeend',
    `<div class="u">${esc(q)}</div>`
  );

  const t = document.createElement('div');
  t.className = 'b';
  t.innerHTML = `
    <div class="av">${BOT}</div>
    <div class="bw">
      <div class="dots">
        <i></i><i></i><i></i>
      </div>
    </div>
  `;

  wrap.appendChild(t);
  bottom();

  let r;

  try {
    r = await askQuestion(q);
  } catch (e) {
    r = {
      type: 'none',
      answer: 'Something went wrong reaching the server. Try again.',
      sources: []
    };
  }

  const files = [...new Set(r.sources.map(s => s.file))];

  const head =
    r.type === 'warn'
      ? `<div class="wt">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 3l10 18H2z"/>
            <path d="M12 10v5M12 18h.01"/>
          </svg>
          Sources conflict
        </div>`
      : r.type === 'none'
        ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="9"/>
            <path d="M12 11v5M12 8h.01"/>
          </svg>`
        : '';

  const body = r.type === 'none'
    ? `<div class="card none">
        ${head}
        <span>${esc(r.answer)}</span>
      </div>`
    : `<div class="card ${r.type === 'warn' ? 'warn' : ''}">
        ${head}
        ${md(r.answer)}

        <div class="chips">
          ${files.map(f =>
            `<button class="chip" data-f="${f}">
              ${IC}${f}
            </button>`
          ).join('')}
        </div>

        ${r.sources.length
          ? `<details>
              <summary>Sources (${r.sources.length})</summary>

              ${r.sources.map((s, i) =>
                `<div class="src">
                  <div class="sh">
                    <span>${s.file}</span>
                    <button data-f="${s.file}" data-i="${i}">
                      View in document
                    </button>
                  </div>

                  <div class="bar">
                    <i style="width:${Math.round(s.score * 100)}%"></i>
                  </div>

                  <pre>${esc(s.text)}</pre>
                </div>`
              ).join('')}
            </details>`
          : ''}
      </div>`;

  const bw = t.querySelector('.bw');

  bw.innerHTML = body + `
    <div class="acts">
      <button class="ib" data-a="c" aria-label="Copy answer">⧉</button>
      <button class="ib" data-a="u" aria-label="Good answer">👍</button>
      <button class="ib" data-a="d" aria-label="Bad answer">👎</button>
    </div>
  `;

  bw.onclick = e => {
    const b = e.target.closest('button');
    if (!b) return;

    if (b.dataset.f) {
      const s = b.dataset.i != null
        ? r.sources[+b.dataset.i]
        : r.sources.find(x => x.file === b.dataset.f);

      openDoc(b.dataset.f, s && s.text);

    } else if (b.dataset.a === 'c') {
      navigator.clipboard &&
        navigator.clipboard.writeText(r.answer).catch(() => {});

      b.textContent = '✓';

    } else if (b.dataset.a) {
      bw.querySelectorAll('[data-a=u],[data-a=d]')
        .forEach(x =>
          x.classList.toggle(
            'on',
            x === b && !b.classList.contains('on')
          )
        );
    }
  };

  busy = false;
  $('send').disabled = false;
  bottom();
}

const ta = $('q');

ta.oninput = () => {
  ta.style.height = 'auto';
  ta.style.height = ta.scrollHeight + 'px';
};

ta.onkeydown = e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    go();
  }
};

$('send').onclick = go;

function go() {
  const v = ta.value;
  ta.value = '';
  ta.style.height = 'auto';
  ask(v);
}

const SM = [
  ["Leaving the company", 1],
  ["Tool access requests", 0],
  ["Senior engineer salary", 4]
];

const CH = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';

$('smps').innerHTML = SM.map(([t, i], n) =>
  `<button class="smp" data-i="${i}" data-n="${n}">
    ${CH}
    <span>${t}</span>
  </button>`
).join('');

async function runSample(b) {
  if (busy) return;

  document.querySelectorAll('.smp').forEach(x =>
    x.classList.toggle('on', x === b)
  );

  wrap.innerHTML = '';
  closeSide();
  await ask(EX[+b.dataset.i]);
}

$('smps').onclick = e => {
  const b = e.target.closest('.smp');
  if (b) runSample(b);
};

$('clear').onclick = () => {
  document.querySelectorAll('.smp').forEach(x =>
    x.classList.remove('on')
  );

  empty();
  closeSide();
};

empty();

// Load the document list + text for the sidebar and viewer
fetch('/docs')
  .then(r => r.json())
  .then(d => {
    DOCS = d;
    ORDER = Object.keys(d);
    renderDocs();
  })
  .catch(() => {});
