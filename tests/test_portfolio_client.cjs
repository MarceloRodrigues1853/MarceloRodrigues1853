const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(process.argv[2] || path.resolve(__dirname, '../../challenge-ONE-portfolio/github-projects.js'), 'utf8');
const owner = 'MarceloRodrigues1853';
const makeRepo = (name = 'example') => ({ full_name: `${owner}/${name}`, pushed_at: '2026-01-01T12:00:00Z', language: 'Go', stars: 2 });

function page(respond, names = ['example']) {
  let listener;
  const calls = [];
  const controls = { hidden: true, setAttribute() {}, removeAttribute() {} };
  const button = { textContent: '', disabled: false, addEventListener(event, handler) { listener = handler; } };
  const status = { textContent: '' };
  const displayName = { textContent: 'Marcelo Rodrigues' };
  const cards = names.map(name => {
    let metadata;
    const link = { href: `https://github.com/${owner}/${name}` };
    return {
      querySelectorAll: () => [link],
      querySelector(selector) {
        if (selector === '.github-metadata') return metadata;
        if (selector === '.project-card__body') return { append(node) { metadata = node; } };
        return null;
      },
      get text() { return metadata?.textContent || ''; }
    };
  });
  const document = {
    title: 'Portfólio',
    getElementById: id => ({ githubControls: controls, githubLoad: button, githubStatus: status }[id]),
    querySelectorAll: selector => selector === '.curated-projects .project-card' ? cards : selector === '.hero__name, .header__logo-text' ? [displayName] : [],
    querySelector: () => null,
    createElement: () => ({ textContent: '', className: '' })
  };
  vm.runInNewContext(source, {
    document, URL, AbortController, Date, setTimeout, clearTimeout,
    async fetch(url) {
      calls.push(url);
      const result = await respond(url);
      if (result instanceof Error) throw result;
      return { ok: true, json: async () => result };
    }
  });
  return { run: () => listener(), cards, button, status, calls, displayName };
}

const feed = (repositories, extras = {}) => ({ schema_version: 1, owner, collected_at: '2026-01-02T12:00:00Z', repositories, ...extras });

test('uses one shared feed for all cards and synchronizes identity', async () => {
  const app = page(() => feed([makeRepo('one'), makeRepo('two')], { profile: { name: 'Updated Name', career_focus: 'Back-end' } }), ['one', 'two']);
  await app.run();
  assert.equal(app.calls.length, 1);
  assert.match(app.calls[0], /raw\.githubusercontent\.com/);
  assert.ok(app.cards.every(card => card.text.includes('Stars: 2') && card.text.includes('Dados de')));
  assert.equal(app.displayName.textContent, 'Updated Name');
  assert.equal(app.button.disabled, true);
});

test('falls back to direct GitHub when feed is unavailable', async () => {
  const app = page(url => url.includes('raw.githubusercontent') ? new Error('404') : makeRepo());
  await app.run();
  assert.equal(app.calls.length, 2);
  assert.match(app.cards[0].text, /Consulta direta ao GitHub/);
  assert.match(app.status.textContent, /arquivo sincronizado não está disponível/);
});

test('preserves static content and enables retry when all requests fail', async () => {
  const app = page(() => new Error('offline'));
  await app.run();
  assert.equal(app.cards[0].text, '');
  assert.equal(app.button.disabled, false);
  assert.match(app.status.textContent, /0 de 1/);
});

test('rejects incompatible and malformed feeds', async () => {
  for (const bad of [feed([], { owner: 'other' }), feed([], { schema_version: 2 }), feed([null]), feed([], { collected_at: 'invalid' })]) {
    const app = page(url => url.includes('raw.githubusercontent') ? bad : makeRepo());
    await app.run();
    assert.match(app.cards[0].text, /Consulta direta/);
  }
});

test('only fetches missing projects directly', async () => {
  const app = page(url => url.includes('raw.githubusercontent') ? feed([makeRepo('one')]) : makeRepo('two'), ['one', 'two']);
  await app.run();
  assert.equal(app.calls.length, 2);
  assert.match(app.status.textContent, /1 consultas diretas complementares/);
});

test('invalid cached dates fall back instead of replacing content', async () => {
  const bad = makeRepo(); bad.pushed_at = 'invalid';
  const app = page(url => url.includes('raw.githubusercontent') ? feed([bad]) : makeRepo());
  await app.run();
  assert.equal(app.calls.length, 2);
  assert.match(app.cards[0].text, /Consulta direta/);
});

test('renders remote strings as text and refuses a different repository', async () => {
  const dangerous = makeRepo(); dangerous.language = '<img onerror=alert(1)>';
  const app = page(() => feed([dangerous]));
  await app.run();
  assert.match(app.cards[0].text, /<img onerror=alert\(1\)>/);
  assert.equal(app.cards[0].querySelector('.github-metadata').innerHTML, undefined);
  const wrong = page(url => url.includes('raw.githubusercontent') ? new Error('404') : { ...makeRepo(), full_name: 'other/example' });
  await wrong.run();
  assert.equal(wrong.cards[0].text, '');
});

test('prevents repeated requests immediately after failure', async () => {
  const app = page(() => new Error('offline'));
  await app.run();
  const calls = app.calls.length;
  await app.run();
  assert.equal(app.calls.length, calls);
  assert.match(app.status.textContent, /Aguarde alguns segundos/);
});
