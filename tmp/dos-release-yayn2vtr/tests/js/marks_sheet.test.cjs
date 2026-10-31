const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function setup(unsaved = false) {
  const handlers = {};
  const notice = { textContent: '' };
  let focused;
  const save = { focus() { focused = 'save'; } };
  const sheet = {
    dataset: {}, setAttribute() {}, closest() { return this; },
    querySelector() { return notice; }, querySelectorAll() { return fields; },
  };
  sheet.querySelector = (selector) => selector.includes('button') ? save : notice;
  const fields = [0, 1].map((index) => ({
    tagName: 'INPUT', closest: () => sheet, matches: () => true,
    focus() { focused = index; },
  }));
  const listen = (name, handler) => (handlers[name] ||= []).push(handler);
  const window = { addEventListener: listen, confirm: () => false };
  const document = {
    addEventListener: listen, getElementById: () => null,
    querySelector: (selector) => unsaved && selector.includes('data-unsaved') ? sheet : null,
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../static/js/app.js'), 'utf8'), { document, window });
  function dispatch(name, details = {}) {
    const event = { target: fields[0], prevented: false,
      preventDefault() { this.prevented = true; }, stopPropagation() {}, ...details };
    for (const handler of handlers[name] || []) handler(event);
    return event;
  }
  return { dispatch, fields, sheet, notice, window, focused: () => focused };
}

test('Enter moves down the sheet and Shift+Enter moves up without submitting', () => {
  const s = setup();
  assert.equal(s.dispatch('keydown', { key: 'Enter' }).prevented, true);
  assert.equal(s.focused(), 1);
  s.dispatch('keydown', { key: 'Enter', target: s.fields[1], shiftKey: true });
  assert.equal(s.focused(), 0);
  s.dispatch('keydown', { key: 'Enter', target: s.fields[1] });
  assert.equal(s.focused(), 'save');
});

test('unsaved edits protect navigation; saving clears the warning and prevents duplicate submission', () => {
  const s = setup();
  s.dispatch('input');
  assert.equal(s.notice.textContent, 'Unsaved changes');
  assert.equal(s.dispatch('beforeunload').prevented, true);
  const selector = { closest: () => null, matches: () => true };
  assert.equal(s.dispatch('submit', { target: selector }).prevented, true);
  assert.equal(s.dispatch('click', { target: { closest: () => ({}) } }).prevented, true);
  assert.equal(s.dispatch('submit', { target: s.sheet }).prevented, false);
  assert.equal(s.dispatch('beforeunload').prevented, false);
  assert.equal(s.dispatch('submit', { target: s.sheet }).prevented, true);
});

test('a validation response retains unsaved protection until navigation is confirmed', () => {
  const s = setup(true);
  assert.equal(s.dispatch('beforeunload').prevented, true);
  s.window.confirm = () => true;
  s.dispatch('submit', { target: { closest: () => null, matches: () => true } });
  assert.equal(s.dispatch('beforeunload').prevented, false);
});
