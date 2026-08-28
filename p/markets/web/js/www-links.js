/**
 * Markets → www 链接本机改写。
 * HTML 仍写 https://www.ai24x.com/...（生产正确）；
 * 本机默认改成 http://127.0.0.1:8000；localStorage.ai24x_local_products=0 则保持正式站。
 */
(function () {
  function preferLocal() {
    try {
      var h = String(location.hostname || "").toLowerCase();
      if (h !== "127.0.0.1" && h !== "localhost") return false;
      var flag = "";
      try {
        flag = String(localStorage.getItem("ai24x_local_products") || "").trim();
      } catch (e) {}
      return flag !== "0";
    } catch (e) {
      return false;
    }
  }

  function wwwBase() {
    return preferLocal() ? "http://127.0.0.1:8000" : "https://www.ai24x.com";
  }

  function openBase() {
    return preferLocal() ? "http://127.0.0.1:18080" : "https://open.ai24x.com";
  }

  function rewrite() {
    var base = wwwBase();
    if (base !== "https://www.ai24x.com") {
      var nodes = document.querySelectorAll('a[href^="https://www.ai24x.com"]');
      for (var i = 0; i < nodes.length; i++) {
        var a = nodes[i];
        var href = a.getAttribute("href") || "";
        a.setAttribute("href", href.replace(/^https:\/\/www\.ai24x\.com/, base));
      }
    }
    var ob = openBase();
    if (ob !== "https://open.ai24x.com") {
      var onodes = document.querySelectorAll("a[data-open]");
      for (var j = 0; j < onodes.length; j++) {
        var oa = onodes[j];
        var ohref = oa.getAttribute("href") || "";
        if (/^https?:\/\/open\.ai24x\.com(?:\/|$)/.test(ohref)) {
          oa.setAttribute("href", ohref.replace(/^https:\/\/open\.ai24x\.com/, ob));
        }
      }
    }
  }

  window.AI24X_WWW_BASE = wwwBase;
  window.AI24X_OPEN_BASE = openBase;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", rewrite);
  } else {
    rewrite();
  }
})();
