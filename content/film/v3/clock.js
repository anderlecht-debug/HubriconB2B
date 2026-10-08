// The stage's own clock (render.mjs calls window.__seek(t) every frame, after the CSS
// animations are set to t). Kinds declare behaviour in data attributes; nothing here knows
// a figure or a word, it only reveals what the shot already carries, at the plan's times.
//   data-count="75000" data-count-at="1.2" data-count-dur="0.9" data-count-fmt="$#,###"
//       counts up to the value; the element's own text is the final, exact figure
//   data-type-at="0.4" data-type-cps="38"   types the element's text, a character at a time
//   data-flicker                             a projector's faint unevenness on its opacity
(() => {
  const ease = (x) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);
  const fmt = (n, f) => {
    const dec = (f.split(".")[1] || "").replace(/[^#0]/g, "").length;
    const s = Math.abs(n).toFixed(dec).split(".");
    const int = f.includes(",") ? s[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",") : s[0];
    const body = s[1] ? `${int}.${s[1]}` : int;
    return f.replace(/[#0,]+(\.[#0]+)?/, body);
  };
  window.__seek = (t) => {
    // data-count no longer counts (the critique of 2026-10-06: "2, 6, 9, 11, 13, 14 cents" on the way
    // to 15 cents is a figure that is not a fact). A figure is its exact final text on every frame;
    // its entrance is a CSS land (blur, scale, tracking), never intermediate numbers.
    document.querySelectorAll("[data-count]").forEach((el) => {
      if (!el.dataset.final) el.dataset.final = el.textContent;
      if (el.textContent !== el.dataset.final) el.textContent = el.dataset.final;
    });
    document.querySelectorAll("[data-type-at]").forEach((el) => {
      if (el.dataset.full === undefined) el.dataset.full = el.textContent;
      const n = Math.max(0, Math.floor((t - +el.dataset.typeAt) * (+el.dataset.typeCps || 40)));
      el.textContent = el.dataset.full.slice(0, n);
      el.style.visibility = n > 0 ? "visible" : "hidden";
    });
    document.querySelectorAll("[data-flicker]").forEach((el) => {
      const k = Math.sin(t * 37.1) * 0.5 + Math.sin(t * 11.7 + 1.3) * 0.5;
      el.style.opacity = String(1 - 0.035 * (k * 0.5 + 0.5));
    });
  };
})();
