// Progressive enhancement only — every page works without JavaScript.
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("select[data-autosubmit]").forEach((el) =>
    el.addEventListener("change", () => el.form.submit()));

  // Destructive actions ask for confirmation (CSP forbids inline onsubmit handlers).
  document.querySelectorAll("form[data-confirm]").forEach((f) =>
    f.addEventListener("submit", (e) => { if (!window.confirm(f.dataset.confirm)) e.preventDefault(); }));

  // Move keyboard / screen-reader focus to a validation problem after a failed submit.
  const problem = document.querySelector("[data-autofocus]");
  if (problem) problem.focus();

  // FR-019: recommend existing dashboards / data products while the requester types.
  const panel = document.getElementById("suggest-panel");
  if (!panel) return;
  const list = document.getElementById("suggest-list");
  const inputs = document.querySelectorAll("[data-suggest]");
  let timer;
  const run = async () => {
    const q = Array.from(inputs).map((i) => i.value).join(" ").trim();
    if (q.length < 3) return;
    try {
      const res = await fetch(panel.dataset.endpoint + "?q=" + encodeURIComponent(q), { credentials: "same-origin" });
      if (!res.ok) return;
      const items = await res.json();
      list.replaceChildren();
      if (!items.length) { list.textContent = "No close matches found yet."; return; }
      items.forEach((it) => {
        const row = document.createElement("div");
        row.style.cssText = "padding:8px 0;border-bottom:1px solid #eef2f4";
        const kind = document.createElement("div");
        kind.className = "kind";
        kind.textContent = it.type + (it.domain ? " · " + it.domain : "");
        const a = document.createElement("a");
        a.href = it.url; a.target = "_blank"; a.rel = "noopener";
        a.textContent = it.title; a.style.fontWeight = "600";
        row.append(kind, a);
        list.append(row);
      });
    } catch (_) { /* suggestions are optional */ }
  };
  inputs.forEach((i) => i.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 350); }));
});
