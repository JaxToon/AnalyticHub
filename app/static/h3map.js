// Regional potential map (H3): wilayah filter auto-submits; clicking a hexagon or a priority item
// fills the detail panel from the hexagon's own data attributes. The page works without this script.
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("select[data-autosubmit]").forEach((el) =>
    el.addEventListener("change", () => el.form.submit()));

  // Same fallback as the Integrated Platform: say so when the basemap cannot load (offline / blocked).
  const banner = document.getElementById("hx-tile-error");
  document.querySelectorAll(".hx-tiles img").forEach((img) => {
    const fail = () => { if (banner) banner.hidden = false; };
    if (img.complete && img.naturalWidth === 0) fail();
    img.addEventListener("error", fail);
  });

  const cells = document.querySelectorAll(".hx-cells polygon");
  const dl = document.getElementById("hx-dl");
  if (!cells.length || !dl) return;
  const show = (el) => {
    cells.forEach((c) => c.classList.remove("sel"));
    el.classList.add("sel");
    el.parentNode.appendChild(el); // draw the selected outline on top of its neighbours
    dl.querySelectorAll("[data-k]").forEach((dd) => {
      const v = el.dataset[dd.dataset.k];
      dd.textContent = /^\d+(\.\d+)?$/.test(v) ? Number(v).toLocaleString("en-US") : v;
    });
    dl.hidden = false;
    document.getElementById("hx-empty").hidden = true;
  };
  cells.forEach((c) => {
    c.addEventListener("click", () => show(c));
    c.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); show(c); }
    });
  });
  document.querySelectorAll("[data-goto]").forEach((b) =>
    b.addEventListener("click", () => {
      const el = document.getElementById(b.dataset.goto);
      if (el) { show(el); el.focus(); }
    }));
});
