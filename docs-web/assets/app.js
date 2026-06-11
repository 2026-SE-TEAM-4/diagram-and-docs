/* =========================================================
   설계 문서 뷰어
   - assets/manifest.js 의 DOCS_MANIFEST 가 단일 원본 (tabs > categories > items)
   - 상단 탭: 설계 문서 / 평가 체크리스트 / 보고서 목차 추천
   - 해시 라우팅: #/docs/02-requirements/use-cases.md
   - md 원문을 fetch → marked 렌더(DOMPurify 살균) → mermaid 블록 렌더
   - 상대 링크/이미지는 md 파일 위치 기준으로 재작성
   ========================================================= */

(function () {
  "use strict";

  var manifest = window.DOCS_MANIFEST;
  var tabs = manifest.tabs;
  var contentEl = document.getElementById("content");
  var navEl = document.getElementById("nav");
  var crumbEl = document.getElementById("crumb");
  var tabsEl = document.getElementById("tabs");

  /** 탭별로 문서를 평탄화 — pager(이전/다음)는 같은 탭 안에서만 움직인다. */
  tabs.forEach(function (tab) {
    tab.flat = tab.categories.reduce(function (acc, cat) {
      return acc.concat(
        cat.items.map(function (item) {
          return { cat: cat, title: item.title, path: item.path };
        })
      );
    }, []);
  });

  function findDoc(path) {
    for (var t = 0; t < tabs.length; t++) {
      for (var i = 0; i < tabs[t].flat.length; i++) {
        if (tabs[t].flat[i].path === path) {
          return { doc: tabs[t].flat[i], index: i, tab: tabs[t] };
        }
      }
    }
    return null;
  }

  /* ---------- 상단 탭 ---------- */
  function tabHref(tab) {
    // 첫 탭(설계 문서)은 색인 홈, 나머지는 첫 문서로 직행
    return tab === tabs[0] ? "#/" : "#/" + tab.flat[0].path;
  }

  function buildTabs(activeTab) {
    tabsEl.innerHTML = tabs
      .map(function (tab) {
        return (
          '<a data-tab="' + tab.id + '" href="' + tabHref(tab) + '"' +
          (tab === activeTab ? ' class="active"' : "") + ">" +
          tab.title +
          "</a>"
        );
      })
      .join("");
  }

  /* ---------- 사이드바 ---------- */
  function buildNav(tab) {
    navEl.innerHTML = tab.categories
      .map(function (cat) {
        var links = cat.items
          .map(function (item) {
            return (
              '<a data-path="' + item.path + '" href="#/' + item.path + '">' +
              item.title +
              "</a>"
            );
          })
          .join("");
        return (
          '<div class="nav-cat">' +
          '<div class="nav-cat-label"><span class="no">' + cat.no + "</span>" +
          cat.title +
          "</div>" +
          links +
          "</div>"
        );
      })
      .join("");
  }

  function markActive(path) {
    navEl.querySelectorAll("a").forEach(function (a) {
      a.classList.toggle("active", a.getAttribute("data-path") === path);
    });
  }

  /* ---------- 홈 (설계 문서 색인) ---------- */
  function renderHome() {
    var tab = tabs[0];
    var cats = tab.categories
      .map(function (cat) {
        var cards = cat.items
          .map(function (item) {
            return (
              '<a class="home-card" href="#/' + item.path + '">' +
              item.title +
              '<span class="path">' + item.path + "</span></a>"
            );
          })
          .join("");
        return (
          '<section class="home-cat">' +
          '<div class="home-cat-head"><span class="no">' + cat.no + "</span><h2>" +
          cat.title +
          "</h2></div>" +
          '<div class="home-grid">' + cards + "</div></section>"
        );
      })
      .join("");

    contentEl.innerHTML =
      '<div class="home-hero">' +
      '<div class="kicker">diagram-and-docs / design archive</div>' +
      "<h1>" + manifest.site.title + "</h1>" +
      "<p>설계 산출물의 단일 원본은 <code>docs/</code> 아래 마크다운 파일이며, 이 페이지는 그 원문을 그대로 불러와 보여준다. 다이어그램 원본(drawio)은 <code>diagrams/</code>에 있다.</p>" +
      "</div>" +
      cats;
    crumbEl.innerHTML = "<b>INDEX</b>";
    buildTabs(tab);
    buildNav(tab);
    markActive(null);
    restartRise();
  }

  /* ---------- 마크다운 렌더 ---------- */
  function rewriteRelativeUrls(root, mdDir) {
    root.querySelectorAll("img[src]").forEach(function (img) {
      var src = img.getAttribute("src");
      if (!/^(https?:|data:|\/)/.test(src)) {
        img.setAttribute("src", mdDir + src);
      }
    });
    root.querySelectorAll("a[href]").forEach(function (a) {
      var href = a.getAttribute("href");
      if (/^(https?:|mailto:|#|\/)/.test(href)) {
        if (/^https?:/.test(href)) a.setAttribute("target", "_blank");
        return;
      }
      // 상대 경로를 index.html 기준으로 정규화
      var parts = (mdDir + href).split("/");
      var stack = [];
      parts.forEach(function (p) {
        if (p === "" || p === ".") return;
        if (p === "..") stack.pop();
        else stack.push(p);
      });
      var resolved = stack.join("/");
      var anchorIdx = resolved.indexOf("#");
      var pathOnly = anchorIdx >= 0 ? resolved.slice(0, anchorIdx) : resolved;
      if (/\.md$/.test(pathOnly)) {
        a.setAttribute("href", "#/" + pathOnly); // md 끼리는 뷰어 내부 라우팅
      } else {
        a.setAttribute("href", resolved); // 그 외 파일은 직접 링크
      }
    });
  }

  /* ---------- 표 장식 (뱃지·칩) ----------
     md 원문은 그대로 두고, 렌더된 표의 td 텍스트에서 알려진 토큰만
     뱃지/칩 span으로 감싼다. 문서와 시각 표현의 단일 원본 분리. */
  var CELL_BADGES = {
    "높음": "pri-high", "필수": "pri-high", "매우 높음": "pri-high",
    "중간": "pri-mid", "보통": "pri-mid", "권장": "pri-mid",
    "낮음": "pri-low", "선택": "pri-low",
    "확보": "st-ok", "확보 (강점)": "st-ok", "보완 필요": "st-warn",
    "재앙적": "pri-high", "심각함": "pri-mid", "감내할 수 있음": "pri-low",
  };
  var TOKEN_BADGES = {
    STU: "role-stu", MGR: "role-mgr", ADM: "role-adm", SYS: "role-sys",
    GET: "http-get", POST: "http-post", PATCH: "http-patch", PUT: "http-patch", DELETE: "http-del", WS: "http-ws",
    AVAILABLE: "st-ok", RESERVED: "st-info", IN_USE: "st-warn", MAINTENANCE: "st-mute",
    RETURNED: "st-ok", EXPIRED: "st-bad", RECLAIMED: "st-purple", CANCELED: "st-mute",
    PENDING: "st-warn", APPROVED: "st-ok", REJECTED: "st-bad", AUTO_REJECTED: "st-bad",
    MISSING: "st-bad", NA: "st-mute",
  };
  var TOKEN_RE = /\b(AUTO_REJECTED|AVAILABLE|RESERVED|IN_USE|MAINTENANCE|RETURNED|EXPIRED|RECLAIMED|CANCELED|PENDING|APPROVED|REJECTED|MISSING|NA|STU|MGR|ADM|SYS|GET|POST|PATCH|PUT|DELETE|WS)\b|\b(UC\d{2}(?:-[A-Z]\d+)?|F\d{2}|NFR-[A-Z]+\d+|ADR-\d+|E-\d{2}|API-\d{2})\b/g;

  function makeBadge(cls, text) {
    var s = document.createElement("span");
    s.className = "badge " + cls;
    s.textContent = text;
    return s;
  }

  function decorateTextNode(node) {
    var text = node.nodeValue;
    TOKEN_RE.lastIndex = 0;
    if (!TOKEN_RE.test(text)) return;
    TOKEN_RE.lastIndex = 0;
    var frag = document.createDocumentFragment();
    var last = 0, m;
    while ((m = TOKEN_RE.exec(text)) !== null) {
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      if (m[1]) frag.appendChild(makeBadge(TOKEN_BADGES[m[1]], m[1]));
      else frag.appendChild(makeBadge("chip", m[2]));
      last = m.index + m[0].length;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    node.parentNode.replaceChild(frag, node);
  }

  function decorateTables(root) {
    root.querySelectorAll("table td").forEach(function (td) {
      var exact = CELL_BADGES[td.textContent.trim()];
      if (exact) {
        var label = td.textContent.trim();
        td.textContent = "";
        td.appendChild(makeBadge(exact, label));
        return;
      }
      // a·code 내부는 건너뛰고 순수 텍스트 노드만 토큰 치환
      var walker = document.createTreeWalker(td, NodeFilter.SHOW_TEXT, {
        acceptNode: function (n) {
          var p = n.parentNode;
          while (p && p !== td) {
            if (p.tagName === "A" || p.tagName === "CODE") return NodeFilter.FILTER_REJECT;
            p = p.parentNode;
          }
          return NodeFilter.FILTER_ACCEPT;
        },
      });
      var nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach(decorateTextNode);
    });
  }

  function renderMermaidBlocks(root) {
    var blocks = root.querySelectorAll("pre code.language-mermaid");
    if (!blocks.length || !window.mermaid) return;
    blocks.forEach(function (code, i) {
      var div = document.createElement("div");
      div.className = "mermaid";
      div.id = "mmd-" + Date.now() + "-" + i;
      div.textContent = code.textContent;
      code.closest("pre").replaceWith(div);
    });
    try {
      window.mermaid.run({ querySelector: ".mermaid" });
    } catch (e) {
      /* mermaid 문법 오류는 해당 블록만 실패 — 본문 렌더는 유지 */
    }
  }

  function restartRise() {
    contentEl.style.animation = "none";
    void contentEl.offsetWidth; // reflow로 애니메이션 재시작
    contentEl.style.animation = "";
  }

  function renderPager(found) {
    var prev = found.tab.flat[found.index - 1];
    var next = found.tab.flat[found.index + 1];
    if (!prev && !next) return "";
    var html = '<nav class="pager">';
    if (prev) {
      html +=
        '<a href="#/' + prev.path + '"><span class="dir">← Prev</span><span class="t">' +
        prev.title + "</span></a>";
    }
    if (next) {
      html +=
        '<a class="next" href="#/' + next.path + '"><span class="dir">Next →</span><span class="t">' +
        next.title + "</span></a>";
    }
    return html + "</nav>";
  }

  function renderNotFound(path) {
    // path는 신뢰할 수 없는 입력(URL 해시) — textContent로만 다룬다.
    var box = document.createElement("div");
    box.className = "err";
    var b = document.createElement("b");
    b.textContent = "등록되지 않은 문서다.";
    var code = document.createElement("code");
    code.textContent = path;
    box.appendChild(b);
    box.appendChild(document.createElement("br"));
    box.appendChild(code);
    var p = document.createElement("p");
    p.textContent = "assets/manifest.js에 등록된 문서만 열 수 있다. 색인으로 돌아가 문서를 선택하라.";
    box.appendChild(p);
    contentEl.innerHTML = "";
    contentEl.appendChild(box);
    crumbEl.innerHTML = '<a href="#/">INDEX</a> / <b>404</b>';
    buildTabs(tabs[0]);
    buildNav(tabs[0]);
    markActive(null);
  }

  function renderDoc(path) {
    var found = findDoc(path);
    fetch(path)
      .then(function (res) {
        if (!res.ok) throw new Error(res.status + " " + res.statusText);
        return res.text();
      })
      .then(function (md) {
        var mdDir = path.slice(0, path.lastIndexOf("/") + 1);
        var article = document.createElement("article");
        article.className = "md";
        var html = window.marked.parse(md);
        // 문서 원문은 레포 내부 md지만, 방어적으로 살균 후 삽입한다.
        if (window.DOMPurify) html = window.DOMPurify.sanitize(html);
        article.innerHTML = html;
        rewriteRelativeUrls(article, mdDir);
        decorateTables(article);

        contentEl.innerHTML = "";
        contentEl.appendChild(article);
        contentEl.insertAdjacentHTML("beforeend", renderPager(found));

        renderMermaidBlocks(article);
        crumbEl.innerHTML =
          '<a href="#/">INDEX</a> / ' +
          found.tab.title + " / " +
          found.doc.cat.no + " " + found.doc.cat.title +
          " / <b></b>";
        crumbEl.querySelector("b").textContent = found.doc.title;
        buildTabs(found.tab);
        buildNav(found.tab);
        markActive(path);
        restartRise();
        window.scrollTo(0, 0);
      })
      .catch(function (err) {
        // path·err.message를 innerHTML에 섞지 않는다 — 노드 + textContent로 조립.
        var box = document.createElement("div");
        box.className = "err";
        var b = document.createElement("b");
        b.textContent = "문서를 불러오지 못했다.";
        var code = document.createElement("code");
        code.textContent = path + " — " + err.message;
        var p = document.createElement("p");
        p.textContent =
          "이 뷰어는 fetch로 md를 읽으므로 로컬에서는 정적 서버가 필요하다: " +
          "python3 -m http.server 실행 후 http://localhost:8000 접속.";
        box.appendChild(b);
        box.appendChild(document.createElement("br"));
        box.appendChild(code);
        box.appendChild(p);
        contentEl.innerHTML = "";
        contentEl.appendChild(box);
        crumbEl.innerHTML = '<a href="#/">INDEX</a> / <b>오류</b>';
      });
  }

  /* ---------- 라우터 ---------- */
  function route() {
    var hash = location.hash.replace(/^#\/?/, "");
    if (!hash) {
      renderHome();
    } else if (findDoc(hash)) {
      renderDoc(hash); // manifest에 등록된 문서만 fetch 허용
    } else {
      renderNotFound(hash);
    }
  }

  if (window.mermaid) {
    window.mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict" });
  }
  window.addEventListener("hashchange", route);
  route();
})();
