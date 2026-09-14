# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "web" / "js" / "console.js"
t = p.read_text(encoding="utf-8")
start = t.find('    var btnChat = $("btn-chat-run");')
end = t.find('    var btnShared = $("btn-continue-shared");')
if start < 0 or end < 0 or end <= start:
    raise SystemExit(f"markers not found start={start} end={end}")

new = r'''    var btnChat = $("btn-chat-run");
    if (btnChat) {
      btnChat.addEventListener("click", function () {
        var out = $("chat-out");
        var useKey = $("chat-use-api-key") && $("chat-use-api-key").checked;
        var key = ($("api-key").value || AI24X_API.getApiKey() || "").trim();
        if (useKey) {
          if (!key) {
            showMsg(
              $("consoleMsg"),
              tr(
                "已勾选「用 API Key 发送」，请先在调用设置粘贴本账号完整 Key。",
                "“Use API key” is checked — paste your own full key in call settings first."
              ),
              false
            );
            return;
          }
          AI24X_API.setApiKey(key);
        }
        if (!AI24X_API.getAuthToken() && !key) {
          showMsg(
            $("consoleMsg"),
            tr("请先登录，或创建并保存 API Key", "Sign in first, or create and save an API key"),
            false
          );
          return;
        }
        var model = ($("chat-model").value || "auto").trim() || "auto";
        out.textContent = tr("请求中…", "Requesting…");
        AI24X_API.chatRun(
          {
            prompt: ($("chat-prompt").value || "").trim() || tr("你好", "Hello"),
            model: model,
            max_tokens: model === "shared" ? 400 : 1000,
          },
          null,
          { preferApiKey: !!useKey }
        )
          .then(function (r) {
            var requested = ($("chat-model").value || "auto").trim() || "auto";
            out.textContent = formatChatOut(r, requested);
            var reply = (r && r.response) || "";
            if (/\bon(\s+on){8,}\b/i.test(reply) || /AIon4X|AI on4X/i.test(reply)) {
              showMsg(
                $("consoleMsg"),
                tr(
                  "上游免费小模型偶发复读/串音。请再试一次，或改用 flash（需余额）。品牌名应为 AI24X。",
                  "Free-pool models sometimes repeat or garble the brand. Retry, or use flash (needs credits). Brand is AI24X."
                ),
                false
              );
            } else if (requested === "shared") {
              var rem = r && r.remaining_quota;
              if (rem != null && Number(rem) > 1000000) {
                showMsg(
                  $("consoleMsg"),
                  tr(
                    "返回额度很大，可能仍走了付费 Key。请取消勾选「用 API Key 发送」后重试。",
                    "remaining looks like a paid wallet — uncheck “Use API key” and retry."
                  ),
                  false
                );
              } else {
                showMsg(
                  $("consoleMsg"),
                  tr("免费共享试调完成（model=shared）。", "Free shared try-call done (model=shared)."),
                  true
                );
              }
            }
            return refreshAll();
          })
          .catch(function (e) {
            out.textContent = e.message || tr("失败", "Failed");
            showMsg($("consoleMsg"), e.message || tr("试调失败", "Try-call failed"), false);
            if (e && e.status === 402) {
              var cta = $("balance-cta");
              if (cta) cta.style.display = "";
              showConsolePanel("overview");
            }
          });
      });
    }
'''

# tickets bind near DOMContentLoaded
bind_marker = "    refreshAll();\n"
bind_tickets = """    var navTickets = $("nav-tickets");
    if (navTickets) {
      navTickets.addEventListener("click", function (e) {
        e.preventDefault();
        if (window.AI24X_SUPPORT_WIDGET && typeof AI24X_SUPPORT_WIDGET.open === "function") {
          AI24X_SUPPORT_WIDGET.open("ticket");
        } else {
          showMsg(
            $("consoleMsg"),
            tr("请使用右下角「协助」打开工单。", "Use the help widget (bottom-right) for tickets."),
            true
          );
        }
      });
    }
    refreshAll();
"""

t2 = t[:start] + new + t[end:]
if bind_marker in t2 and "nav-tickets" not in t2[t2.find("DOMContentLoaded") :]:
    t2 = t2.replace(bind_marker, bind_tickets, 1)

p.write_text(t2, encoding="utf-8")
print("patched", p, "len", len(t2))
