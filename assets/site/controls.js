(() => {
  const button = document.querySelector(".theme-button");
  const key = "pricegenerator-docs-theme";
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    button.textContent = theme === "dark" ? button.dataset.light : button.dataset.dark;
    document.querySelector('meta[name="theme-color"]').content = theme === "dark" ? "#07090d" : "#f4f8fa";
  }
  let theme = "dark";
  try { if (localStorage.getItem(key) === "light") theme = "light"; } catch {}
  applyTheme(theme);
  button.hidden = false;
  button.addEventListener("click", () => {
    theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(theme);
    try { localStorage.setItem(key, theme); } catch {}
  });
  document.querySelectorAll("[data-copy]").forEach((copy) => {
    if (!navigator.clipboard) return;
    copy.hidden = false;
    copy.addEventListener("click", async () => {
      const code = document.getElementById(copy.dataset.copy);
      try {
        await navigator.clipboard.writeText(code.textContent);
        const status = document.querySelector(".copy-status");
        status.textContent = status.dataset.copied;
      } catch {
        const range = document.createRange();
        range.selectNodeContents(code);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      }
    });
  });
})();
