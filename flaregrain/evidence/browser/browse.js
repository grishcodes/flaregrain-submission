const categoryFilter = document.querySelector("#filter");
const evidence = [...document.querySelectorAll("article[data-category]")];
const count = document.querySelector("#count");

function showEvidence() {
  const category = categoryFilter.value;
  let visible = 0;

  for (const entry of evidence) {
    entry.hidden = category !== "all" && entry.dataset.category !== category;
    if (!entry.hidden) visible += 1;
  }

  count.textContent = visible === 1 ? "1 entry" : visible + " entries";
}

categoryFilter.addEventListener("change", showEvidence);
categoryFilter.closest("label").hidden = false;
showEvidence();
