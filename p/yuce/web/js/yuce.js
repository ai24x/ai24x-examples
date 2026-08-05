(function () {
  "use strict";

  /** 人类票未达此数时：先展示 AI */
  var HUMAN_LIGHT_N = 50;

  var EVENTS = [
    {
      id: "cpi",
      cat: "macro",
      catLabel: "物价与景气",
      difficulty: "★★",
      title: "下月 CPI 同比是否高于本月读数？",
      close: "对照国家统计局公布结果",
      humanVotes: 128,
      humanYes: 47,
      aiAvg: 53,
      ais: [
        { name: "DeepSeek Flash", yes: true, p: 55, reason: "食品项季节性回升概率偏高。" },
        { name: "Kimi", yes: true, p: 51, reason: "能源价格波动带来上行扰动。" },
        { name: "Qwen Flash", yes: false, p: 48, reason: "核心 CPI 仍弱，同比上行空间有限。" },
      ],
    },
    {
      id: "pmi",
      cat: "macro",
      catLabel: "物价与景气",
      difficulty: "★★",
      title: "下月制造业 PMI 是否重回扩张区间（≥ 50）？",
      close: "对照国家统计局公布结果",
      humanVotes: 22,
      humanYes: 41,
      aiAvg: 46,
      ais: [
        { name: "DeepSeek Flash", yes: false, p: 44, reason: "新订单指数仍偏弱，扩张动能不足。" },
        { name: "Kimi", yes: true, p: 51, reason: "季节性补库与政策预期或推升读数。" },
        { name: "Qwen Flash", yes: false, p: 43, reason: "外需不确定，整体难稳站 50 上方。" },
      ],
    },
    {
      id: "house",
      cat: "housing",
      catLabel: "二手房",
      difficulty: "★★",
      title: "70 城二手房价格指数本月是否环比上涨？",
      close: "对照国家统计局公开口径",
      humanVotes: 96,
      humanYes: 28,
      aiAvg: 31,
      ais: [
        { name: "DeepSeek Flash", yes: false, p: 29, reason: "成交套数回暖但挂牌价仍偏弱。" },
        { name: "Kimi", yes: false, p: 33, reason: "核心城分化，整体指数难现环比正增长。" },
        { name: "Qwen Flash", yes: false, p: 30, reason: "政策托底未充分传导至二手挂牌。" },
      ],
    },
    {
      id: "house2",
      cat: "housing",
      catLabel: "二手房",
      difficulty: "★★",
      title: "70 城二手房成交套数本月是否同比增加？",
      close: "只谈官方统计，不论个案楼盘",
      humanVotes: 18,
      humanYes: 52,
      aiAvg: 45,
      ais: [
        { name: "DeepSeek Flash", yes: true, p: 54, reason: "局部放开与降成本或提振成交量。" },
        { name: "Kimi", yes: false, p: 42, reason: "观望情绪仍浓，同比增量有限。" },
        { name: "Qwen Flash", yes: false, p: 40, reason: "高基数下同比转正难度较大。" },
      ],
    },
    {
      id: "box",
      cat: "boxoffice",
      catLabel: "票房",
      difficulty: "★",
      title: "本月院线总票房是否突破 40 亿元？",
      close: "对照公开票房口径结算",
      humanVotes: 86,
      humanYes: 63,
      aiAvg: 57,
      ais: [
        { name: "DeepSeek Flash", yes: true, p: 60, reason: "档期片单集中，周末场次利用率偏高。" },
        { name: "Kimi", yes: true, p: 54, reason: "头部影片口碑稳定，长尾贡献可观。" },
        { name: "Qwen Flash", yes: false, p: 46, reason: "工作日上座偏淡，总量或略低于阈值。" },
      ],
    },
    {
      id: "box2",
      cat: "boxoffice",
      catLabel: "票房",
      difficulty: "★",
      title: "本月票房冠军影片是否突破 8 亿元？",
      close: "揭晓后可分享本场人机对照",
      humanVotes: 12,
      humanYes: 58,
      aiAvg: 52,
      ais: [
        { name: "DeepSeek Flash", yes: true, p: 56, reason: "预售与想看指数偏强。" },
        { name: "Kimi", yes: false, p: 48, reason: "同档竞争分流，单片冲线压力大。" },
        { name: "Qwen Flash", yes: true, p: 53, reason: "口碑若稳住，仍有过线可能。" },
      ],
    },
  ];

  var state = {
    filter: "all",
    activeId: "house",
    choice: null,
  };

  function $(id) {
    return document.getElementById(id);
  }

  function isCold(ev) {
    return (ev.humanVotes || 0) < HUMAN_LIGHT_N;
  }

  function tagFor(ev) {
    var aiYes = ev.ais.filter(function (a) {
      return a.yes;
    }).length;
    var aiSplit = aiYes > 0 && aiYes < ev.ais.length;
    if (aiSplit) return { cls: "tag-split", text: "AI 看法不一" };
    if (isCold(ev)) return { cls: "tag-split", text: "先看 AI" };
    var diff = Math.abs(ev.humanYes - ev.aiAvg);
    if (diff >= 12) return { cls: "tag-oppose", text: "人机看法不同" };
    return { cls: "tag-agree", text: "人机看法接近" };
  }

  function filtered() {
    if (state.filter === "all") return EVENTS;
    return EVENTS.filter(function (e) {
      return e.cat === state.filter;
    });
  }

  function activeEvent() {
    return (
      EVENTS.find(function (e) {
        return e.id === state.activeId;
      }) || EVENTS[0]
    );
  }

  function renderList() {
    var list = $("eventList");
    if (!list) return;
    var rows = filtered();
    if (!rows.length) {
      list.innerHTML = "<p class='sub'>该分类暂无题目。</p>";
      return;
    }
    if (
      !rows.some(function (e) {
        return e.id === state.activeId;
      })
    ) {
      state.activeId = rows[0].id;
    }
    list.innerHTML = rows
      .map(function (ev) {
        var tag = tagFor(ev);
        return (
          '<button type="button" class="event-item' +
          (ev.id === state.activeId ? " is-active" : "") +
          '" data-id="' +
          ev.id +
          '">' +
          '<div class="meta"><span>' +
          ev.catLabel +
          "</span><span>" +
          ev.difficulty +
          '</span><span class="tag ' +
          tag.cls +
          '">' +
          tag.text +
          "</span></div>" +
          "<h3>" +
          ev.title +
          "</h3></button>"
        );
      })
      .join("");
  }

  function renderPanel() {
    var ev = activeEvent();
    var tag = tagFor(ev);
    var cold = isCold(ev);
    $("pkTitle").textContent = ev.title;
    $("pkMeta").textContent = ev.catLabel + " · " + ev.close;
    $("pkTag").className = "tag " + tag.cls;
    $("pkTag").textContent = tag.text;

    var rowHuman = $("rowHuman");
    var coldHint = $("coldHint");
    if (cold) {
      rowHuman.classList.add("is-muted");
      $("humanLabel").textContent = "大家的判断";
      $("humanPct").textContent = "样本还少";
      requestAnimationFrame(function () {
        $("barHuman").style.width = "0%";
      });
      if (coldHint) {
        coldHint.hidden = false;
        coldHint.textContent =
          "目前 " +
          ev.humanVotes +
          " 人作答（满 " +
          HUMAN_LIGHT_N +
          " 人后展示大家的比例）。先看看各家 AI。";
      }
    } else {
      rowHuman.classList.remove("is-muted");
      $("humanLabel").textContent = "大家的判断";
      $("humanPct").textContent = ev.humanYes + "% 选「是」";
      requestAnimationFrame(function () {
        $("barHuman").style.width = ev.humanYes + "%";
      });
      if (coldHint) coldHint.hidden = true;
    }

    $("aiPct").textContent = ev.aiAvg + "% 倾向「是」";
    requestAnimationFrame(function () {
      $("barAi").style.width = ev.aiAvg + "%";
    });

    $("aiList").innerHTML = ev.ais
      .map(function (a) {
        return (
          "<li><div><div class='model'>" +
          a.name +
          "</div><div class='verdict'>" +
          a.reason +
          "</div></div><div>" +
          (a.yes ? "是" : "否") +
          " · " +
          a.p +
          "%</div></li>"
        );
      })
      .join("");

    state.choice = null;
    document.querySelectorAll("[data-choice]").forEach(function (btn) {
      btn.classList.remove("is-active");
    });
    $("voteReason").value = "";
    $("voteMsg").textContent = "";
    $("voteMsg").className = "vote-msg";
  }

  function bind() {
    document.querySelectorAll("[data-filter]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.filter = btn.getAttribute("data-filter");
        document.querySelectorAll("[data-filter]").forEach(function (b) {
          b.classList.toggle("is-active", b === btn);
        });
        renderList();
        renderPanel();
      });
    });

    $("eventList").addEventListener("click", function (e) {
      var item = e.target.closest(".event-item");
      if (!item) return;
      state.activeId = item.getAttribute("data-id");
      renderList();
      renderPanel();
    });

    document.querySelectorAll("[data-choice]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.choice = btn.getAttribute("data-choice");
        document.querySelectorAll("[data-choice]").forEach(function (b) {
          b.classList.toggle("is-active", b === btn);
        });
      });
    });

    $("btnVote").addEventListener("click", function () {
      var msg = $("voteMsg");
      var reason = String($("voteReason").value || "").trim();
      if (!state.choice) {
        msg.textContent = "请先选择「是」或「否」。";
        msg.className = "vote-msg err";
        return;
      }
      if (reason.length < 10) {
        msg.textContent = "理由至少写 10 个字（当前 " + reason.length + " 字）。";
        msg.className = "vote-msg err";
        return;
      }
      if (reason.length > 200) {
        msg.textContent = "理由最多 200 字。";
        msg.className = "vote-msg err";
        return;
      }
      var quality =
        reason.length >= 20
          ? "理由较完整，展示时会优先一些。"
          : "已记下。写满 20 字更容易被展示。";
      msg.textContent = "已提交。本题每人限答一次。" + quality;
      msg.className = "vote-msg ok";
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bind();
    renderList();
    renderPanel();
  });
})();
