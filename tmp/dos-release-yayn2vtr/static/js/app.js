document.addEventListener("htmx:configRequest", (event) => {
  const token = document.querySelector('meta[name="csrf-token"]')?.content;
  if (token) event.detail.headers["X-CSRFToken"] = token;
});

for (const eventName of ["htmx:responseError", "htmx:sendError", "htmx:timeout"]) {
  document.addEventListener(eventName, () => {
    const notice = document.getElementById("request-error");
    if (notice) notice.hidden = false;
  });
}

document.addEventListener("htmx:beforeRequest", () => {
  const notice = document.getElementById("request-error");
  if (notice) notice.hidden = true;
});

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-dismiss-request-error]")) {
    const notice = document.getElementById("request-error");
    if (notice) notice.hidden = true;
  }
});
document.addEventListener("input", (event) => {
  if (event.target.closest("#portal-sign-in, #sign-in-panel")) {
    const notice = document.getElementById("request-error");
    if (notice) notice.hidden = true;
  }
});

// Shared form dialogs retain their ordinary page destinations as a fallback.
const configurationDialog = document.getElementById("configuration-dialog");
if (configurationDialog && window.htmx && configurationDialog.showModal) {
  const content = document.getElementById("configuration-dialog-content");
  let opener;
  let dirty = false;
  let busy = false;
  let restoreLinkAfterRefresh = null;
  const closeDialog = () => {
    if (busy || (dirty && !window.confirm("Discard your unsaved changes?"))) return;
    configurationDialog.close();
  };
  configurationDialog.addEventListener("input", () => { dirty = true; });
  configurationDialog.addEventListener("change", () => { dirty = true; });
  window.addEventListener("beforeunload", (event) => {
    if (!configurationDialog.open || !dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });
  configurationDialog.addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (event.target.closest("[data-dialog-cancel], .back-link") || link?.textContent.trim() === "Cancel") {
      event.preventDefault();
      event.stopPropagation();
      closeDialog();
    }
  }, true);
  configurationDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeDialog();
  });
  // Oat's backdrop touch handler closes dialogs directly; protect entered data.
  configurationDialog.addEventListener("touchstart", (event) => {
    if (event.target === configurationDialog) event.stopPropagation();
  });
  configurationDialog.addEventListener("close", () => {
    dirty = false;
    opener?.focus();
  });
  document.addEventListener("htmx:beforeRequest", (event) => {
    if (event.detail.target !== content) return;
    const link = event.detail.elt.closest("[data-configuration-dialog]");
    if (link) {
      const insideDialog = configurationDialog.contains(link);
      if (busy || (configurationDialog.open && !insideDialog) || (dirty && !window.confirm("Discard your unsaved changes?"))) {
        event.preventDefault();
        return;
      }
      if (!insideDialog) opener = link;
      dirty = false;
      content.innerHTML = '<h2 id="configuration-dialog-title">Loading form</h2><p role="status">Please wait…</p><button type="button" class="outline" data-dialog-cancel>Cancel</button>';
      if (!configurationDialog.open) configurationDialog.showModal();
    }
    busy = true;
    content.setAttribute("aria-busy", "true");
    const error = content.querySelector(".dialog-error");
    if (error) error.hidden = true;
  });
  document.addEventListener("htmx:afterRequest", (event) => {
    if (event.detail.target !== content) return;
    busy = false;
    content.removeAttribute("aria-busy");
    if (event.detail.failed) {
      const error = content.querySelector(".dialog-error");
      if (error) error.hidden = false;
      else content.innerHTML = '<h2 id="configuration-dialog-title">Unable to load form</h2><p role="alert">Please close this dialog and try again.</p><button type="button" class="outline" data-dialog-cancel>Close</button>';
    }
  });
  document.addEventListener("htmx:beforeSwap", (event) => {
    if (event.detail.target !== content || event.detail.xhr.status !== 200) return;
    // A session expiry may redirect to a full login page.
    if (!event.detail.serverResponse.includes('id="configuration-dialog-title"')) {
      event.detail.shouldSwap = false;
      event.detail.isError = true;
    }
  });
  document.addEventListener("htmx:afterSwap", (event) => {
    if (["configuration-results", "workspace-content"].includes(event.detail.target.id) && restoreLinkAfterRefresh) {
      const link = Array.from(document.querySelectorAll("[data-configuration-dialog]")).find((item) => item.href === restoreLinkAfterRefresh);
      (link || document.querySelector("[data-configuration-dialog]"))?.focus();
      restoreLinkAfterRefresh = null;
    }
    if (event.detail.target !== content) return;
    configurationDialog.classList.toggle("wide-dialog", Boolean(content.querySelector("table")) || content.querySelectorAll(".form-field").length > 8);
    const invalid = content.querySelector('[aria-invalid="true"]');
    (invalid || content.querySelector('input:not([type="hidden"]), select, textarea, button'))?.focus();
  });
  document.addEventListener("configurationSaved", () => {
    busy = false;
    dirty = false;
    configurationDialog.close();
    const feedback = document.getElementById("configuration-feedback");
    feedback.textContent = "Changes saved.";
    feedback.hidden = false;
    restoreLinkAfterRefresh = opener?.href;
    const results = document.getElementById("configuration-results");
    htmx.ajax("GET", results.dataset.refreshUrl, {target: results, select: "#configuration-results", swap: "outerHTML"});
  });
  document.addEventListener("formSaved", (event) => {
    busy = false;
    dirty = false;
    if (event.detail.followup) {
      htmx.ajax("GET", event.detail.url, {target: content, swap: "innerHTML"});
      return;
    }
    configurationDialog.close();
    const feedback = document.getElementById("configuration-feedback");
    feedback.replaceChildren(document.createTextNode(event.detail.message + " "));
    const destination = new URL(event.detail.url, window.location.href);
    if (destination.origin === window.location.origin && destination.href !== window.location.href) {
      const link = document.createElement("a");
      link.href = destination.href;
      link.textContent = "View saved result";
      feedback.append(link);
    }
    feedback.hidden = false;
    restoreLinkAfterRefresh = opener?.href;
    htmx.ajax("GET", window.location.href, {target: "#workspace-content", select: "#workspace-content", swap: "outerHTML"});
  });
}

// Whole-class entry: Enter moves between results; explicit buttons save/submit.
let marksSheetDirty = Boolean(document.querySelector("[data-marks-sheet][data-unsaved]"));
for (const eventName of ["input", "change"]) {
  document.addEventListener(eventName, (event) => {
    const sheet = event.target.closest("[data-marks-sheet][data-editable]");
    if (!sheet) return;
    marksSheetDirty = true;
    sheet.querySelector("[data-sheet-dirty]").textContent = "Unsaved changes";
  });
}
document.addEventListener("keydown", (event) => {
  const sheet = event.target.closest("[data-marks-sheet][data-editable]");
  if (!sheet || event.key !== "Enter" || event.target.tagName !== "INPUT" || !event.target.matches("[data-mark-value]")) return;
  event.preventDefault();
  const fields = Array.from(sheet.querySelectorAll("[data-mark-value]"));
  const next = fields.indexOf(event.target) + (event.shiftKey ? -1 : 1);
  (fields[next] || sheet.querySelector('button[value="save"]'))?.focus();
});
document.addEventListener("submit", (event) => {
  const sheet = event.target.closest("[data-marks-sheet]");
  if (sheet) {
    if (sheet.dataset.submitting) { event.preventDefault(); return; }
    sheet.dataset.submitting = "true";
    sheet.setAttribute("aria-busy", "true");
    marksSheetDirty = false;
  } else if (event.target.matches("[data-sheet-selector]") && marksSheetDirty) {
    if (!window.confirm("Leave this sheet and discard unsaved marks?")) event.preventDefault();
    else marksSheetDirty = false;
  }
});
document.addEventListener("click", (event) => {
  if (!marksSheetDirty || !event.target.closest("a[href]")) return;
  if (!window.confirm("Leave this sheet and discard unsaved marks?")) {
    event.preventDefault();
    event.stopPropagation();
  } else marksSheetDirty = false;
}, true);
window.addEventListener("beforeunload", (event) => {
  if (!marksSheetDirty) return;
  event.preventDefault();
  event.returnValue = "";
});

// Oat handles toggling; keep keyboard access and expanded state in sync.
const sidebarLayout = document.querySelector(".app-layout[data-sidebar-layout]");
if (sidebarLayout) {
  const sidebar = document.getElementById("app-sidebar");
  const mobile = window.matchMedia("(max-width: 768px)");
  const syncSidebar = () => {
    const open = sidebarLayout.hasAttribute("data-sidebar-open");
    sidebar.inert = mobile.matches && !open;
    sidebarLayout.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
      button.setAttribute("aria-expanded", String(open));
    });
  };
  new MutationObserver(syncSidebar).observe(sidebarLayout, { attributes: true, attributeFilter: ["data-sidebar-open"] });
  mobile.addEventListener("change", syncSidebar);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && mobile.matches && sidebarLayout.hasAttribute("data-sidebar-open")) {
      sidebarLayout.removeAttribute("data-sidebar-open");
      sidebarLayout.querySelector("main [data-sidebar-toggle]")?.focus();
    }
  });
  syncSidebar();
}
