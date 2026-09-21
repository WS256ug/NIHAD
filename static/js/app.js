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
