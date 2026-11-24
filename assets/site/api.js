(() => {
  const form = document.querySelector(".api-search");
  const input = form.querySelector("input");
  const results = form.querySelector(".api-results");
  const empty = form.querySelector(".api-no-results");
  const entries = Array.from(document.querySelector("#api-search-data").content.querySelectorAll("a"), link => ({
    link, name: link.dataset.name.toLowerCase(), full: link.textContent.toLowerCase(),
    aliases: (link.dataset.aliases || "").toLowerCase().split(" "), terms: (link.dataset.terms || "").toLowerCase()
  }));
  function search() {
    const query = input.value.toLowerCase().trim();
    results.replaceChildren();
    if (query) {
      const rank = entry => (entry.name === query || entry.aliases.includes(query)) ? 0 : entry.name.startsWith(query) ? 1 :
        entry.full.includes(query) ? 2 : entry.terms.includes(query) ? 3 : 4;
      const matches = entries.map(entry => ({entry, score: rank(entry)})).filter(item => item.score < 4);
      matches.sort((a, b) => a.score - b.score);
      for (const {entry} of matches.slice(0, 15)) {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = entry.link.href;
        link.textContent = entry.link.textContent;
        item.append(link);
        results.append(item);
      }
    }
    results.hidden = !results.children.length;
    empty.hidden = !query || results.children.length > 0;
  }
  input.addEventListener("input", search);
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (results.firstChild) results.firstChild.firstChild.click();
  });
  form.addEventListener("keydown", event => {
    if (event.key === "Escape") { input.value = ""; search(); input.focus(); }
  });
  form.hidden = false;
  const navigation = document.querySelector(".api-navigation");
  const narrow = window.matchMedia("(max-width: 760px)");
  navigation.open = !narrow.matches;
  narrow.addEventListener("change", () => { navigation.open = !narrow.matches; });
  function keepLocation() {
    document.querySelectorAll("[data-locale]").forEach(link => { link.hash = location.hash; });
  }
  keepLocation();
  window.addEventListener("hashchange", keepLocation);
})();
