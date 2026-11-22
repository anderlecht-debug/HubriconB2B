// /learn: a returning reader sees where they left off. Read from this browser's own storage,
// written by the course page as lessons are finished (/assets/learn-course.js). Nothing is sent.
const KEY = (slug) => `hubricon:learn:${slug}`;

for (const card of document.querySelectorAll("[data-hub-course]")) {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(KEY(card.dataset.hubCourse)) || "null"); } catch { saved = null; }
  if (!saved || !Array.isArray(saved.done)) continue;
  const links = [...card.querySelectorAll("[data-lesson]")];
  const done = new Set(saved.done);
  links.forEach((a) => { if (done.has(a.dataset.lesson)) a.setAttribute("data-done", ""); });
  const next = links.find((a) => !done.has(a.dataset.lesson));
  const n = links.filter((a) => done.has(a.dataset.lesson)).length;
  if (!n) continue;
  const start = card.querySelector("[data-resume]");
  const progress = card.querySelector("[data-progress]");
  if (next) {
    next.setAttribute("data-next", "");
    const i = links.indexOf(next) + 1;
    start.href = next.getAttribute("href");
    start.firstChild.textContent = `Continue with lesson ${i} `;
  } else {
    start.firstChild.textContent = "Open the course again ";
  }
  progress.innerHTML = `<b>${n} of ${links.length}</b> lessons done`;
  progress.hidden = false;
}
