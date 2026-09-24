const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

function setupDialog() {
  const handlers = new Map();
  const dialogHandlers = new Map();
  const ajaxCalls = [];
  const feedback = { hidden: true, replaceChildren() {}, append() {} };
  const content = {
    innerHTML: "", querySelector: () => null,
    setAttribute() {}, removeAttribute() {},
  };
  const dialog = {
    open: false, contains: (element) => Boolean(element.inside),
    addEventListener(name, handler) { dialogHandlers.set(name, handler); },
    showModal() { this.open = true; },
    close() { this.open = false; },
  };
  const document = {
    getElementById(id) {
      return { "configuration-dialog": dialog, "configuration-dialog-content": content, "configuration-feedback": feedback }[id];
    },
    createTextNode: (text) => text, createElement: () => ({}),
    querySelector: () => null,
    addEventListener(name, handler) {
      handlers.set(name, [...(handlers.get(name) || []), handler]);
    },
  };
  const htmx = { ajax(...args) { ajaxCalls.push(args); } };
  const window = { htmx, addEventListener() {}, confirm: () => false, location: {href: "http://localhost/students/?q=Mary&page=2", origin: "http://localhost"} };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../../static/js/app.js"), "utf8"), {
    document, window, htmx, URL,
  });
  const dispatch = (name, detail) => {
    const event = { detail, prevented: false, preventDefault() { this.prevented = true; } };
    for (const handler of handlers.get(name) || []) handler(event);
    return event;
  };
  return { dispatch, content, dialog, dialogHandlers, ajaxCalls, feedback, window };
}

test("configuration requests open a modal and preserve it for form submissions", () => {
  const { dispatch, content, dialog } = setupDialog();
  const link = { closest: () => link };
  const request = dispatch("htmx:beforeRequest", { target: content, elt: link });
  assert.equal(request.prevented, false);
  assert.equal(dialog.open, true);
  assert.match(content.innerHTML, /Loading form/);
  assert.equal(dispatch("htmx:beforeRequest", { target: content, elt: link }).prevented, true);
  dispatch("htmx:afterRequest", { target: content });
  content.innerHTML = "Existing form with entered data";
  const submit = dispatch("htmx:beforeRequest", { target: content, elt: { closest: () => null } });
  assert.equal(submit.prevented, false);
  assert.equal(dialog.open, true);
  assert.equal(content.innerHTML, "Existing form with entered data");
});


test("saving refreshes the filtered workspace and closes the dialog", () => {
  const { dispatch, dialog, ajaxCalls, feedback, window } = setupDialog();
  dialog.open = true;
  dispatch("formSaved", {url: "/students/12/", message: "Student saved.", followup: false});
  assert.equal(dialog.open, false);
  assert.equal(feedback.hidden, false);
  assert.equal(ajaxCalls[0][1], window.location.href);
  assert.equal(ajaxCalls[0][2].target, "#workspace-content");
});

test("promotion steps load inside the open dialog", () => {
  const { dispatch, dialog, content, ajaxCalls } = setupDialog();
  dialog.open = true;
  dispatch("formSaved", {url: "/promotions/1/edit/", followup: true});
  assert.equal(dialog.open, true);
  assert.equal(ajaxCalls[0][1], "/promotions/1/edit/");
  assert.equal(ajaxCalls[0][2].target, content);
});

test("cancel protects unsaved input and request failures reveal an error", () => {
  const { dispatch, dialog, content, dialogHandlers, window } = setupDialog();
  const error = {hidden: true};
  content.querySelector = () => error;
  dialog.open = true;
  dialogHandlers.get("input")();
  const event = {preventDefault() {}};
  dialogHandlers.get("cancel")(event);
  assert.equal(dialog.open, true);
  dispatch("htmx:afterRequest", {target: content, failed: true});
  assert.equal(error.hidden, false);
  window.confirm = () => true;
  dialogHandlers.get("cancel")(event);
  assert.equal(dialog.open, false);
});
