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
