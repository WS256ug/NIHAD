const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');

function setup(fetch) {
  const handlers = {};
  vm.runInNewContext(fs.readFileSync('templates/pwa/service-worker.js', 'utf8'), {
    self: { location: { origin: 'https://school.test' },
      clients: { claim: async () => {} },
      addEventListener: (name, handler) => { handlers[name] = handler; } },
    URL, Response, fetch,
    // Any accidental persistent storage usage fails the test.
    caches: new Proxy({}, { get() { throw new Error('Must not cache school data'); } }),
  });
  return async (overrides = {}) => {
    let result;
    handlers.fetch({ request: { method: 'GET', mode: 'navigate', url: 'https://school.test/reports/1/', ...overrides },
      respondWith(value) { result = value; } });
    return result;
  };
}

test('online navigation bypasses HTTP cache and preserves server responses', async () => {
  const response = new Response('denied', { status: 403 });
  const run = setup(async (request, options) => {
    assert.equal(options.cache, 'no-store');
    return response;
  });
  assert.equal(await run(), response);
});

test('offline navigation returns a non-cacheable generic page', async () => {
  const run = setup(async () => { throw new TypeError('offline'); });
  const response = await run();
  assert.equal(response.status, 503);
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
});

test('mutations, HTMX, downloads and external requests are never intercepted', async () => {
  const run = setup(() => { throw new Error('Unexpected fetch'); });
  for (const request of [{ method: 'POST' }, { mode: 'cors' }, { mode: 'same-origin' },
    { url: 'https://external.test/' }]) {
    assert.equal(await run(request), undefined);
  }
});
