(function () {
  'use strict';

  var EMOTION_LABEL = {
    joy: '快乐', trust: '信任', fear: '恐惧', surprise: '惊讶',
    sadness: '悲伤', disgust: '厌恶', anger: '愤怒', anticipation: '期待', neutral: '中性',
  };
  var EMOTION_COLOR = {
    joy: '#FFD54F', trust: '#9CCC65', fear: '#AB47BC', surprise: '#26C6DA',
    sadness: '#42A5F5', disgust: '#66BB6A', anger: '#EF5350', anticipation: '#FFA726', neutral: '#BDBDBD',
  };

  var state = {
    session: null,
    seed: '',
    round: 1,
    candidates: [],
    startTime: 0,
    prevScreen: 'screen-result',
    networkData: null,
  };

  function $(id) { return document.getElementById(id); }

  function show(id) {
    var screens = document.querySelectorAll('.screen');
    for (var i = 0; i < screens.length; i++) screens[i].classList.add('hidden');
    $(id).classList.remove('hidden');
  }

  function api(path, opts) {
    return fetch(path, opts).then(function (res) { return res.json(); });
  }

  function resetTimer() {
    state.startTime = performance.now();
  }

  function chainWords(seed) {
    var s = state.session;
    var chain = (s.chains || []).filter(function (c) { return c.seed === seed; })[0];
    if (!chain) return [];
    return chain.node_ids
      .map(function (id) { return s.nodes[id] ? s.nodes[id].text : null; })
      .filter(Boolean);
  }

  function emotionLabel(t) { return EMOTION_LABEL[t] || t; }
  function emotionColor(t) { return EMOTION_COLOR[t] || '#BDBDBD'; }

  // ---- 种子输入 ----
  async function startSession() {
    var raw = $('seed-input').value;
    var seeds = raw.split(/[\s,，、]+/).map(function (s) { return s.trim(); }).filter(Boolean);
    if (!seeds.length) { alert('请输入至少一个种子词'); return; }
    $('btn-start').disabled = true;
    var data = await api('/api/v1/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed_words: seeds }),
    });
    $('btn-start').disabled = false;
    if (data.error) { alert(data.error.message); return; }
    state.session = data.session;
    applyRound(data);
    show('screen-exp');
  }

  function applyRound(data) {
    state.seed = data.current_seed;
    state.round = data.round;
    state.candidates = data.candidates || [];
    renderExperiment();
    resetTimer();
    $('free-word').value = '';
    $('free-word').focus();
  }

  function toggleContinue(on) {
    var banner = $('continue-banner');
    var btn = $('btn-finish');
    if (on) {
      banner.classList.remove('hidden');
      btn.textContent = '结束并查看结果';
    } else {
      banner.classList.add('hidden');
      btn.textContent = '提前结束';
    }
  }

  function renderExperiment() {
    $('exp-seed').textContent = state.seed;
    $('exp-round').textContent = state.round;

    var chainEl = $('exp-chain');
    chainEl.innerHTML = '';
    var words = chainWords(state.seed);
    var full = [state.seed].concat(words);
    full.forEach(function (w, i) {
      var span = document.createElement('span');
      span.className = 'chain-word';
      span.textContent = w;
      chainEl.appendChild(span);
      if (i < full.length - 1) {
        var arrow = document.createElement('span');
        arrow.className = 'chain-arrow';
        arrow.textContent = '\u2192';
        chainEl.appendChild(arrow);
      }
    });

    var candEl = $('candidates');
    candEl.innerHTML = '';
    (state.candidates || []).forEach(function (word) {
      var b = document.createElement('button');
      b.className = 'cand';
      b.textContent = word;
      b.addEventListener('click', function () { submit(word, 'selected'); });
      candEl.appendChild(b);
    });

    $('last-result').classList.add('hidden');
  }

  async function submit(word, source) {
    var rt = Math.max(0, Math.round(performance.now() - state.startTime));
    var data = await api('/api/v1/sessions/' + state.session.id + '/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word: word, reaction_time_ms: rt, source: source }),
    });
    if (data.error) { alert(data.error.message); return; }

    var st = await api('/api/v1/sessions/' + state.session.id);
    state.session = st.session;

    showLastResult(data.node);
    if (data.finished) {
      await showResult();
    } else {
      applyRound({ current_seed: data.current_seed, round: data.round, candidates: data.candidates });
      toggleContinue(data.rounds_complete);
    }
  }

  function showLastResult(node) {
    var box = $('last-result');
    box.innerHTML = '';
    box.classList.remove('hidden');
    var t = document.createElement('span');
    t.className = 'lr-word';
    t.textContent = node.text + '  ' + emotionLabel(node.emotion_type);
    t.style.color = emotionColor(node.emotion_type);
    var s = document.createElement('span');
    s.className = 'lr-score';
    s.textContent = '综合分 ' + (node.scores.total * 100).toFixed(0) + ' · 反应时 ' + node.reaction_time_ms + 'ms';
    if (node.is_back) s.textContent += ' · 历史词(back)';
    box.appendChild(t);
    box.appendChild(document.createElement('br'));
    box.appendChild(s);
  }

  async function reshuffle() {
    var data = await api('/api/v1/sessions/' + state.session.id + '/reshuffle', { method: 'POST' });
    if (data.error) { alert(data.error.message); return; }
    state.session = data.session;
    applyRound(data);
  }

  async function finishEarly() {
    var data = await api('/api/v1/sessions/' + state.session.id + '/finish', { method: 'POST' });
    if (data.error) { alert(data.error.message); return; }
    state.session = data;
    await showResult();
  }

  async function showResult() {
    var s = state.session;
    var ns = s.network_state || {};
    var summary = $('result-summary');
    summary.innerHTML =
      '共 ' + Object.keys(s.nodes).length + ' 个词 · ' + (s.edges || []).length + ' 条连接 · ' +
      '主导情绪：' + emotionLabel(ns.dominant_emotion) +
      (ns.top_central_words && ns.top_central_words.length
        ? ' · 核心词：' + ns.top_central_words.join('、') : '');

    var chainsEl = $('result-chains');
    chainsEl.innerHTML = '';
    (s.chains || []).forEach(function (chain) {
      var card = document.createElement('div');
      card.className = 'chain-card';
      var h = document.createElement('div');
      h.className = 'chain-card-title';
      h.textContent = '种子：' + chain.seed;
      card.appendChild(h);

      var list = document.createElement('div');
      list.className = 'chain-card-words';
      chain.node_ids.forEach(function (id) {
        var n = s.nodes[id];
        if (!n) return;
        var row = document.createElement('div');
        row.className = 'word-row';
        var dot = document.createElement('span');
        dot.className = 'dot';
        dot.style.background = emotionColor(n.emotion_type);
        var name = document.createElement('span');
        name.className = 'w-name';
        name.textContent = n.text + (n.is_back ? ' *' : '');
        var meta = document.createElement('span');
        meta.className = 'w-meta';
        meta.textContent =
          emotionLabel(n.emotion_type) + ' · 分' + (n.scores.total * 100).toFixed(0) +
          ' · ' + (n.reaction_time_ms != null ? n.reaction_time_ms + 'ms' : '-');
        row.appendChild(dot);
        row.appendChild(name);
        row.appendChild(meta);
        list.appendChild(row);
      });
      card.appendChild(list);
      chainsEl.appendChild(card);
    });

    show('screen-result');
  }

  // ---- 可视化（M2）----
  function buildVizLegend() {
    var box = $('viz-legend');
    box.innerHTML = '';
    Object.keys(EMOTION_LABEL).forEach(function (t) {
      var item = document.createElement('span');
      item.className = 'legend-item';
      var dot = document.createElement('span');
      dot.className = 'dot';
      dot.style.background = EMOTION_COLOR[t];
      item.appendChild(dot);
      item.appendChild(document.createTextNode(EMOTION_LABEL[t]));
      box.appendChild(item);
    });
    var note = document.createElement('span');
    note.className = 'legend-note';
    note.textContent = '· 大球 = 簇核心，小球围绕其旁 · 大小 = 综合分';
    box.appendChild(note);
  }

  function showViz() {
    state.prevScreen = (state.session && state.session.status === 'finished')
      ? 'screen-result' : 'screen-exp';
    buildVizLegend();
    show('screen-viz');
    api('/api/v1/sessions/' + state.session.id + '/network').then(function (net) {
      if (net.error) { alert(net.error.message); return; }
      state.networkData = net;
      drawGraph(net);
    });
  }

  function drawGraph(network, canvasId) {
    var canvas = $(canvasId || 'viz-canvas');
    var ctx = canvas.getContext('2d');
    var W = canvas.clientWidth || 880;
    var H = canvas.clientHeight || 560;
    canvas.width = W;
    canvas.height = H;

    var nodes = (network.nodes || []).map(function (n) {
      return {
        id: n.id,
        text: n.text,
        emotion: n.emotion_type || 'neutral',
        color: n.color || '#BDBDBD',
        total: n.total || 0,
        r: Math.max(10, 8 + 20 * (n.total || 0)),
        x: W / 2 + (Math.random() - 0.5) * 260,
        y: H / 2 + (Math.random() - 0.5) * 260,
        vx: 0, vy: 0,
      };
    });
    var idx = {};
    nodes.forEach(function (n) { idx[n.id] = n; });
    var edges = (network.edges || []).map(function (e) {
      return { a: idx[e.from], b: idx[e.to] };
    }).filter(function (e) { return e.a && e.b && e.a !== e.b; });

    // 按情绪分组，每组的「核心」= 综合分最高的大球
    var groups = {};
    nodes.forEach(function (n) {
      (groups[n.emotion] = groups[n.emotion] || []).push(n);
    });
    var coreOf = {};
    var cores = [];
    Object.keys(groups).forEach(function (emo) {
      var g = groups[emo];
      var core = g.slice().sort(function (a, b) { return b.total - a.total; })[0];
      cores.push(core);
      g.forEach(function (n) { coreOf[n.id] = core; });
    });

    var cx = W / 2, cy = H / 2, alpha = 1.0, rest = 80;

    function tick() {
      var i, j, n, e, m, dx, dy, d, d2, f, a, b;

      // 1) 斥力 + 2) 碰撞（按半径，防止重叠 → 小球被大球挤到周围）
      for (i = 0; i < nodes.length; i++) {
        for (j = i + 1; j < nodes.length; j++) {
          a = nodes[i]; b = nodes[j];
          dx = a.x - b.x; dy = a.y - b.y;
          d2 = dx * dx + dy * dy;
          if (d2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
          d = Math.sqrt(d2);
          f = 1500 / d2;
          a.vx += dx / d * f; a.vy += dy / d * f;
          b.vx -= dx / d * f; b.vy -= dy / d * f;

          var minD = a.r + b.r + 12;
          if (d < minD) {
            var push = (minD - d) * 0.5;
            a.vx += dx / d * push; a.vy += dy / d * push;
            b.vx -= dx / d * push; b.vy -= dy / d * push;
          }
        }
      }

      // 3) 联想路径弹簧
      for (e = 0; e < edges.length; e++) {
        m = edges[e];
        var sdx = m.b.x - m.a.x, sdy = m.b.y - m.a.y;
        var sd = Math.sqrt(sdx * sdx + sdy * sdy) || 1;
        var sf = (sd - rest) * 0.02;
        m.a.vx += sdx / sd * sf; m.a.vy += sdy / sd * sf;
        m.b.vx -= sdx / sd * sf; m.b.vy -= sdy / sd * sf;
      }

      // 4) 小球围绕大球：同情绪的小球被拉向本组核心
      nodes.forEach(function (nn) {
        var core = coreOf[nn.id];
        if (core && core !== nn) {
          nn.vx += (core.x - nn.x) * 0.03;
          nn.vy += (core.y - nn.y) * 0.03;
        }
      });

      // 5) 向心 + 阻尼 + 积分
      for (i = 0; i < nodes.length; i++) {
        n = nodes[i];
        n.vx += (cx - n.x) * 0.005;
        n.vy += (cy - n.y) * 0.005;
        n.vx *= 0.82; n.vy *= 0.82;
        n.x += n.vx * alpha;
        n.y += n.vy * alpha;
      }
      alpha *= 0.97;

      // ---- 渲染 ----
      ctx.clearRect(0, 0, W, H);

      // 集群光晕：核心外一圈淡色，标出「相似颜色聚在一起」
      cores.forEach(function (core) {
        ctx.beginPath();
        ctx.arc(core.x, core.y, 86, 0, Math.PI * 2);
        ctx.fillStyle = core.color + '26';
        ctx.fill();
      });

      // 联想路径
      ctx.strokeStyle = 'rgba(110,120,150,0.5)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (e = 0; e < edges.length; e++) {
        ctx.moveTo(edges[e].a.x, edges[e].a.y);
        ctx.lineTo(edges[e].b.x, edges[e].b.y);
      }
      ctx.stroke();

      // 节点：核心大球描边加粗
      for (i = 0; i < nodes.length; i++) {
        n = nodes[i];
        var isCore = cores.indexOf(n) !== -1;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.fill();
        ctx.strokeStyle = isCore ? 'rgba(20,25,40,0.6)' : 'rgba(0,0,0,0.25)';
        ctx.lineWidth = isCore ? 2.5 : 1;
        ctx.stroke();
        ctx.fillStyle = '#1f2430';
        ctx.font = (n.r >= 15 ? 'bold 12px' : '10px') + ' "Microsoft YaHei", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(n.text, n.x, n.y + n.r + 13);
      }

      if (alpha > 0.05) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  // ---- 报告（M3）----
  async function generateReport() {
    var btn = $('btn-report');
    btn.disabled = true;
    btn.textContent = '生成中…';
    var data = await api('/api/v1/sessions/' + state.session.id + '/report', { method: 'POST' });
    if (data.error) { alert(data.error.message); btn.disabled = false; btn.textContent = '生成报告'; return; }
    renderReport(data);
    var net = await api('/api/v1/sessions/' + state.session.id + '/network');
    if (!net.error) {
      $('report-viz-canvas').classList.remove('hidden');
      drawGraph(net, 'report-viz-canvas');
    }
    btn.disabled = false;
    btn.textContent = '生成报告';
  }

  function renderReport(r) {
    var box = $('report');
    box.innerHTML = '';
    box.classList.remove('hidden');

    if (r.summary) {
      var s = document.createElement('div');
      s.className = 'report-summary';
      s.textContent = r.summary;
      box.appendChild(s);
    }

    (r.complexes || []).forEach(function (c) {
      var card = document.createElement('div');
      card.className = 'report-complex';
      var title = document.createElement('div');
      title.className = 'report-complex-title';
      var dot = document.createElement('span');
      dot.className = 'dot';
      dot.style.background = EMOTION_COLOR[c.emotion] || '#BDBDBD';
      title.appendChild(dot);
      title.appendChild(document.createTextNode(
        c.emotion_label + ' 情结候选 · 核心「' + c.core + '」 · signal ' + (c.signal * 100).toFixed(0)
      ));
      card.appendChild(title);
      var nodes = document.createElement('div');
      nodes.className = 'report-complex-nodes';
      nodes.textContent = '相关词：' + c.nodes.join('、');
      card.appendChild(nodes);
      if (c.description) {
        var desc = document.createElement('div');
        desc.className = 'report-complex-desc';
        desc.textContent = c.description;
        card.appendChild(desc);
      }
      box.appendChild(card);
    });

    var st = r.stats || {};
    var stats = document.createElement('div');
    stats.className = 'report-stats';
    stats.textContent =
      '统计：' + st.word_count + ' 个词 · ' + st.edge_count + ' 条路径 · ' +
      '平均反应时 ' + st.avg_rt_ms + 'ms · 主导情绪 ' + (st.dominant_emotion_label || '');
    box.appendChild(stats);

    var disc = document.createElement('div');
    disc.className = 'report-disclaimer';
    disc.textContent = r.disclaimer || '';
    box.appendChild(disc);
  }

  // ---- 事件绑定 ----
  $('btn-start').addEventListener('click', startSession);
  $('btn-reshuffle').addEventListener('click', reshuffle);
  $('btn-finish').addEventListener('click', finishEarly);
  $('btn-restart').addEventListener('click', function () { location.reload(); });
  $('btn-viz').addEventListener('click', showViz);
  $('btn-viz-result').addEventListener('click', showViz);
  $('btn-report').addEventListener('click', generateReport);
  $('btn-viz-back').addEventListener('click', function () { show(state.prevScreen || 'screen-result'); });
  $('btn-viz-reshuffle').addEventListener('click', function () {
    if (state.networkData) drawGraph(state.networkData);
  });
  $('free-word').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      var word = this.value.trim();
      if (word) submit(word, 'free');
    }
  });
})();
