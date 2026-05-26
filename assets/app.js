/* =========================================================
   문서 사이트 공통 스크립트
   - 테마 토글 (localStorage 영속화 / prefers-color-scheme)
   - 마크다운 렌더링 (marked 기본 렌더러 + DOM 후처리)
   - 섹션 점프 시트 (TOC)
   ========================================================= */

(function () {
  var STORAGE_KEY = "docsite.theme";

  /* ---------- Theme ---------- */
  var root = document.documentElement;
  var saved = localStorage.getItem(STORAGE_KEY);
  var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  root.setAttribute("data-theme", saved || (prefersDark ? "dark" : "light"));

  function setupThemeToggle() {
    var btn = document.querySelector(".theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      localStorage.setItem(STORAGE_KEY, next);
    });
  }

  /* ---------- Slug ---------- */
  var slugCounts = {};
  function slugify(text) {
    var base = String(text || "")
      .trim()
      .toLowerCase()
      .replace(/[!@#$%^&*()=+{}\[\]:;"'<>,.?/\\|~`]/g, "")
      .replace(/\s+/g, "-")
      .replace(/--+/g, "-");
    if (!base) base = "section";
    var n = slugCounts[base] || 0;
    slugCounts[base] = n + 1;
    return n === 0 ? base : base + "-" + n;
  }

  /* ---------- Link remap (.md → .html) ---------- */
  var linkMap = {
    "./docs/project_plan.md": "project-plan.html",
    "docs/project_plan.md": "project-plan.html",
    "./project_plan.md": "project-plan.html",
    "project_plan.md": "project-plan.html",
    "./docs/tech_stacks.md": "tech-stacks.html",
    "docs/tech_stacks.md": "tech-stacks.html",
    "./tech_stacks.md": "tech-stacks.html",
    "tech_stacks.md": "tech-stacks.html",
    "./docs/소프트웨어공학_01_4조_유스케이스_명세서.md": "use-case-spec.html",
    "docs/소프트웨어공학_01_4조_유스케이스_명세서.md": "use-case-spec.html",
    "./소프트웨어공학_01_4조_유스케이스_명세서.md": "use-case-spec.html",
    "소프트웨어공학_01_4조_유스케이스_명세서.md": "use-case-spec.html",
    "./README.md": "index.html",
    "README.md": "index.html"
  };

  function remapHref(href) {
    if (!href) return href;
    var hashIdx = href.indexOf("#");
    var path = hashIdx >= 0 ? href.substring(0, hashIdx) : href;
    var hash = hashIdx >= 0 ? href.substring(hashIdx) : "";
    return linkMap[path] ? linkMap[path] + hash : href;
  }

  /* ---------- Markdown ---------- */
  function renderMarkdown() {
    var holder = document.getElementById("md-source");
    var target = document.getElementById("md-output");
    if (!holder || !target || !window.marked) return;

    var raw = holder.textContent;

    if (typeof marked.setOptions === "function") {
      marked.setOptions({ gfm: true, breaks: false });
    }

    target.innerHTML = marked.parse(raw);

    // 1) 헤딩에 id 부여
    var headings = target.querySelectorAll("h1, h2, h3, h4");
    for (var i = 0; i < headings.length; i++) {
      var h = headings[i];
      if (!h.id) h.id = slugify(h.textContent);
    }

    // 2) 테이블 래핑 (수평 스크롤)
    var tables = target.querySelectorAll("table");
    for (var j = 0; j < tables.length; j++) {
      var t = tables[j];
      if (t.parentNode && t.parentNode.classList && t.parentNode.classList.contains("table-wrap")) continue;
      var wrap = document.createElement("div");
      wrap.className = "table-wrap";
      t.parentNode.insertBefore(wrap, t);
      wrap.appendChild(t);
    }

    // 3) 링크 리매핑 (.md → .html)
    var anchors = target.querySelectorAll("a[href]");
    for (var k = 0; k < anchors.length; k++) {
      var a = anchors[k];
      var href = a.getAttribute("href");
      var mapped = remapHref(href);
      if (mapped !== href) a.setAttribute("href", mapped);
    }

    // 4) hash로 진입 시 스크롤
    if (location.hash) {
      var el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (el) requestAnimationFrame(function () { el.scrollIntoView({ block: "start" }); });
    }
  }

  /* ---------- TOC sheet ---------- */
  function buildToc() {
    var sheet = document.getElementById("toc-sheet");
    var btn = document.getElementById("toc-btn");
    var output = document.getElementById("md-output");
    if (!sheet || !btn || !output) return;

    var list = sheet.querySelector(".toc-list");
    var headings = output.querySelectorAll("h2, h3");

    if (headings.length < 4) {
      btn.style.display = "none";
      return;
    }

    var items = [];
    var h2Counter = 0;
    for (var i = 0; i < headings.length; i++) {
      var h = headings[i];
      var level = h.tagName.toLowerCase();
      var text = (h.textContent || "").replace(/#$/, "").trim();
      if (level === "h2") {
        h2Counter += 1;
        var marker = ("0" + h2Counter).slice(-2);
        items.push('<li class="toc-h2"><a href="#' + h.id + '"><span>' + text + '</span><span class="toc-marker">' + marker + '</span></a></li>');
      } else {
        items.push('<li class="toc-h3"><a href="#' + h.id + '"><span>' + text + '</span></a></li>');
      }
    }
    list.innerHTML = items.join("");

    function open() { sheet.setAttribute("data-open", "true"); }
    function close() { sheet.setAttribute("data-open", "false"); }

    btn.addEventListener("click", function () {
      sheet.getAttribute("data-open") === "true" ? close() : open();
    });
    sheet.addEventListener("click", function (e) {
      if (e.target === sheet) close();
      var a = e.target.closest && e.target.closest("a[href^='#']");
      if (a) close();
    });
    var closeBtn = sheet.querySelector(".toc-close");
    if (closeBtn) closeBtn.addEventListener("click", close);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && sheet.getAttribute("data-open") === "true") close();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupThemeToggle();
    renderMarkdown();
    buildToc();
  });
})();
