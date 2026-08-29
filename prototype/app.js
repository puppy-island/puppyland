/* ==========================================================================
   记忆家园 Memory Home — 前端原型逻辑
   对应 PRD v2.1：场景驱动采集 → 后台记忆整理 → 唯一 Companion 叙事陪伴
   全部 AI / ASR 均为 Mock，可离线完成演示。
   ========================================================================== */
(function () {
  'use strict';

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var pick = function (a) { return a[Math.floor(Math.random() * a.length)]; };
  var stage = $('#stage');

  /* ────────────────────────────────────────────────────────────────────
     1. 状态（对应 PRD §7 数据与状态）
     ──────────────────────────────────────────────────────────────────── */
  var KEY = 'memoryhome.guest.v1';   // Guest Session：当前设备永久保存
  // 后端地址可通过 window.MEMORY_HOME_API 覆盖；本地开发默认 FastAPI 端口 8000。
  var API_BASE = (window.MEMORY_HOME_API || 'http://localhost:8001/api/v1').replace(/\/$/, '');
  var API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '');

  var S = {
    scene: 'intro',
    petName: '',
    hasPhoto: false,
    detail: 0,                      // 形象清晰度 0–1，信息不足即保持低细节 Base 形象
    journey: {
      stage: 'PET_CREATION',
      sceneIndex: 0,
      currentMemoryIndex: 0,
      petCompletion: 0.25,
      worldLevel: 0,
      homeConfig: null,
      memories: [],
      voiceDescription: '',
      petImage: 'assets/pet-idle.webp'
    },
    memories: [],                   // MemoryItem
    pawMarks: [],                   // PawMark
    profile: {                      // CharacterProfile（安全、可 grounding 的部分）
      place: '', traits: [], objects: [], habits: [], precious: ''
    },
    story: {                        // StoryState：唯一活跃的想象性剧情
      scene: 'home', beat: 0, petState: 'idle', used: [], mood: '灯还亮着', homeLightsOn: true
    },
    backendPetId: null,
    conversations: [],              // 当天对话摘要，用于生成小狗来信（Guest Session）
    dailyLetters: []
  };

  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {}
  }
  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (!raw) return false;
      var d = JSON.parse(raw);
      if (!d || !d.story) return false;
      Object.assign(S, d);
      if (!S.journey) S.journey = { stage: 'PET_CREATION', sceneIndex: 0, currentMemoryIndex: 0, petCompletion: 0.25, worldLevel: 0, homeConfig: null, memories: [], voiceDescription: '', petImage: 'assets/pet-idle.webp' };
      if (typeof S.journey.sceneIndex !== 'number') S.journey.sceneIndex = 0;
      if (typeof S.story.homeLightsOn !== 'boolean') S.story.homeLightsOn = true;
      if (!Array.isArray(S.conversations)) S.conversations = [];
      if (!Array.isArray(S.dailyLetters)) S.dailyLetters = [];
      return true;
    } catch (e) { return false; }
  }
  function reset() {
    try { localStorage.removeItem(KEY); } catch (e) {}
    location.reload();
  }

  function apiRequest(path, options) {
    options = options || {};
    var controller = window.AbortController ? new AbortController() : null;
    var timer = controller ? setTimeout(function () { controller.abort(); }, options.timeout || 8000) : null;
    var headers = options.headers || {};
    if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    var req = Object.assign({}, options, { headers: headers });
    if (controller) req.signal = controller.signal;
    return fetch(API_BASE + path, req).then(function (res) {
      if (!res.ok) throw new Error('API ' + res.status);
      return res.json();
    }).finally(function () { if (timer) clearTimeout(timer); });
  }

  function publicAssetUrl(url) {
    if (!url) return '';
    return /^https?:\/\//i.test(url) ? url : API_ORIGIN + (url.charAt(0) === '/' ? url : '/' + url);
  }

  async function ensureBackendPet() {
    if (S.backendPetId) return S.backendPetId;
    var voice = S.journey.voiceDescription || '';
    try {
      var pet = await apiRequest('/pets', {
        method: 'POST',
        body: JSON.stringify({
          name: S.petName || 'TA',
          personality: voice || null,
          likes: voice || null,
          avatar_url: null
        })
      });
      S.backendPetId = pet.id;
      save();
      return pet.id;
    } catch (e) {
      // 原型仍可离线演示，后端不可用时保留本地状态。
      return null;
    }
  }

  async function syncPetPhoto(file) {
    if (!file) return null;
    try {
      var form = new FormData(); form.append('file', file);
      var uploaded = await apiRequest('/upload-image', { method: 'POST', body: form, timeout: 12000 });
      var url = publicAssetUrl(uploaded.url);
      if (S.backendPetId) {
        await apiRequest('/pets/' + S.backendPetId, { method: 'PUT', body: JSON.stringify({ avatar_url: url }) });
      }
      S.journey.petReferenceImage = url;
      save();
      return url;
    } catch (e) { return null; }
  }

  var MEMORY_TYPE_MAP = {
    first_meeting: 'first_sight', first_home: 'wonderful_moment', habit: 'funny_eating',
    favorite_activity: 'wonderful_moment', happiest_memory: 'wonderful_moment'
  };

  async function persistJourneyMemory(node, narrative) {
    if (!S.backendPetId) return null;
    var content = [S.journey.voiceDescription, narrative.reveal].filter(Boolean).join('；');
    try {
      return await apiRequest('/pets/' + S.backendPetId + '/narrations/auto-grow?narration_text=' + encodeURIComponent(node.title + '：' + content), {
        method: 'POST', timeout: 7000
      });
    } catch (e) {
      try {
        return await apiRequest('/pets/' + S.backendPetId + '/memories', {
          method: 'POST', body: JSON.stringify({ memory_type: MEMORY_TYPE_MAP[node.id] || 'wonderful_moment', title: narrative.title, content: content || narrative.reveal })
        });
      } catch (ignored) { return null; }
    }
  }

  async function syncHomeConfig() {
    if (!S.backendPetId) return;
    try {
      var profile = await apiRequest('/pets/' + S.backendPetId + '/profile', { timeout: 7000 });
      var items = profile.virtual_home_items || [];
      S.journey.homeConfig = {
        theme: 'warm_nature', lighting: 'sunny',
        assets: items.map(function (item) { return item.item_type || item.item_name; }),
        memoryCount: (profile.memories || []).length
      };
      save();
    } catch (e) {}
  }

  async function backendChat(text) {
    if (!S.backendPetId) return null;
    try {
      var reply = await apiRequest('/pets/' + S.backendPetId + '/chat', {
        method: 'POST', body: JSON.stringify({ message: text }), timeout: 12000
      });
      return reply && reply.content ? reply.content : null;
    } catch (e) { return null; }
  }

  var POSE = {
    idle:     'assets/pet-idle.webp',
    approach: 'assets/pet-approach.webp',
    happy:    'assets/pet-approach.webp',
    run:      'assets/pet-run.webp',
    down:     'assets/pet-down.webp'
  };

  function setDetail(v) {
    S.detail = Math.max(0, Math.min(1, v));
    stage.style.setProperty('--detail', S.detail.toFixed(2));
  }
  function bumpDetail(step) { setDetail(S.detail + (step || 0.18)); }

  /* ────────────────────────────────────────────────────────────────────
     2. Mock：记忆解释器 / ASR
     ──────────────────────────────────────────────────────────────────── */
  var TRAIT_WORDS = ['胆小', '黏人', '贪吃', '安静', '爱叫', '爱撒娇', '慢吞吞', '闹腾', '聪明', '倔'];
  var PLACE_WORDS = ['路边', '楼下', '纸箱', '雨', '宠物店', '收容所', '朋友', '市场', '桥', '院子', '车站', '窗台'];

  // Multimodal Memory Interpreter（Mock）：只抽取用户明确说出的非敏感事实
  function interpret(text) {
    var t = String(text || '');
    PLACE_WORDS.forEach(function (w) { if (t.indexOf(w) >= 0 && !S.profile.place) S.profile.place = w; });
    TRAIT_WORDS.forEach(function (w) {
      if (t.indexOf(w) >= 0 && S.profile.traits.indexOf(w) < 0) S.profile.traits.push(w);
    });
    if (/球|玩具/.test(t) && S.profile.objects.indexOf('球') < 0) S.profile.objects.push('球');
    if (/毯|窝|垫/.test(t) && S.profile.objects.indexOf('毯子') < 0) S.profile.objects.push('毯子');
  }

  // 敏感内容（MVP 完全不进入 grounding / 角色资产 / 叙事资产）
  var SENSITIVE = /走了|离开|不在了|去世|最后|生病|治疗|安乐|遗憾|对不起|后悔|骨灰|坟|天堂|彩虹桥/;
  var DISTRESS  = /受不了|撑不住|好难过|哭|崩溃|活不下去|不想活|没有意义|喘不过气|难受死/;

  function addMemory(sceneId, text, priority) {
    var sensitive = SENSITIVE.test(text);
    var m = {
      id: 'm' + (S.memories.length + 1),
      sceneId: sceneId,
      rawText: text,
      priority: priority || 1,
      visibility: 'hidden',            // MVP 不展示记忆卡
      groundingAllowed: !sensitive,    // 敏感 Memory 完全排除
      createdAt: Date.now()
    };
    S.memories.push(m);
    if (!sensitive) interpret(text);
    bumpDetail(0.16);
    save();
    return m;
  }

  function addPaw(sceneId, label, memoryId) {
    var p = { id: 'p' + (S.pawMarks.length + 1), sceneId: sceneId, label: label,
              sourceMemoryIds: memoryId ? [memoryId] : [], lit: true, persisted: true };
    S.pawMarks.push(p);
    save();
    return p;
  }

  var ASR = {
    name:  ['豆豆', '年糕', '团子', '煤球', '花卷', '布丁'],
    meet:  ['是在楼下的纸箱里捡到的，那天下着雨，它一直躲着不出来，特别胆小。',
            '朋友家的狗生了一窝，我去看的时候它自己跑过来，就这么带回家了。',
            '在路边的宠物店，它隔着玻璃一直看我，我走了两步又回头。'],
    day:   ['它每天早上都会先跑到窗台上晒太阳，然后再来叫我起床。',
            '一听到钥匙的声音就冲过来，地板太滑经常刹不住。',
            '吃饭之前一定要转两圈，特别贪吃。'],
    keep:  ['有一次我很晚才回家，它一直在门口等，看到我就一直摇尾巴，什么都没有说。',
            '它每次都趴在我脚边睡，我一动它就抬头看我一眼，再趴回去。']
  };

  function mockASR(key) { return pick(ASR[key] || ASR.day); }

  // 腾讯云实时语音识别（WebSocket）
  function doASR(audioBlob, callback) {
    // 1. 从后端获取签名后的 WebSocket URL
    fetch(API_BASE + '/asr')
      .then(function(res) { return res.json(); })
      .then(function(data) {
        var url = data.url;
        var ws = new WebSocket(url);
        var done = false;          // callback 是否已调用，防止重复
        var transcripts = [];

        // 通用完成处理：只调用一次 callback
        function finish(text) {
          if (done) return;
          done = true;
          ws.close();
          callback(text || null);
        }

        // 超时兜底：8 秒内没有结果则降级
        var timer = setTimeout(function() { finish(''); }, 8000);

        ws.onopen = function() {
          // 2. 将音频 blob 转为 ArrayBuffer，再逐片发送
          var reader = new FileReader();
          reader.onload = function(ev) {
            var buffer = ev.target.result;
            ws.send(buffer);                        // 发送音频
            ws.send(JSON.stringify({ type: 'end' })); // 发送结束信号
          };
          reader.readAsArrayBuffer(audioBlob);
        };

        ws.onmessage = function(ev) {
          clearTimeout(timer);
          try {
            var msg = JSON.parse(ev.data);
            // 腾讯云 ASR：result.voice_text_str 为累积文本，slice_type 2=最终结果 4=流结束
            if (msg.result && msg.result.voice_text_str) {
              transcripts.push(msg.result.voice_text_str);
            }
            if (msg.slice_type === 2) {
              // 最终结果到达，立即结束（不再等 onclose）
              finish(transcripts.join(''));
            }
          } catch(e) {}
        };

        ws.onerror = function() { finish(''); };

        ws.onclose = function() {
          clearTimeout(timer);
          if (!done) finish(transcripts.join(''));
        };
      })
      .catch(function() {
        callback(null); // 降级
      });
  }

  /* ────────────────────────────────────────────────────────────────────
     3. 通用组件：旁白、爪印轨迹、录音采集
     ──────────────────────────────────────────────────────────────────── */
  function say(el, html, delay) {
    return new Promise(function (res) {
      setTimeout(function () {
        el.style.opacity = 0;
        setTimeout(function () {
          el.innerHTML = html;
          el.style.transition = 'opacity .7s ease';
          el.style.opacity = 1;
          res();
        }, 260);
      }, delay || 0);
    });
  }

  function pawSvg(cls) {
    return '<svg class="pawmark ' + (cls || '') + '" viewBox="0 0 26 26"><use href="#paw"></use></svg>';
  }

  // 脚步不是进度条：它是 TA 走过的痕迹。记忆进来后对应爪印变成温暖的光。
  function buildTrail(host, n) {
    host.innerHTML = '';
    for (var i = 0; i < n; i++) {
      var wrap = document.createElement('div');
      wrap.innerHTML = pawSvg();
      var svg = wrap.firstChild;
      var t = i / (n - 1);
      svg.style.position = 'absolute';
      svg.style.left = (8 + t * 78) + '%';
      svg.style.bottom = (39 + Math.sin(t * 3.1) * 2.2) + '%';
      svg.style.transform = 'rotate(' + (-16 + t * 26) + 'deg) scale(' + (0.8 + (i % 2) * 0.18) + ')';
      host.appendChild(svg);
    }
  }
  function litTrail(host, count) {
    $$('.pawmark', host).forEach(function (p, i) {
      p.classList.toggle('is-lit', i < count);
    });
  }

  /* 录音浮层 */
  var recOverlay = $('#recOverlay');
  var wave = $('#wave');
  for (var w = 0; w < 11; w++) {
    var bar = document.createElement('i');
    bar.style.animationDelay = (w * 0.08).toFixed(2) + 's';
    wave.appendChild(bar);
  }

  /*  采集组件：按住发光爪印说话 → Mock 转写 → 发送前可编辑 → 失败可退化为文字
      对应 PRD「语音支持录音、Mock ASR、发送前编辑；失败退化为文字」 */
  function capture(slot, opt) {
    slot.innerHTML = '';
    var col = document.createElement('div');
    col.className = 'slot';
    slot.appendChild(col);

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'paw-btn';
    btn.setAttribute('aria-label', opt.hold || '按住说话');
    btn.innerHTML = '<svg viewBox="0 0 26 26"><use href="#paw"></use></svg>';

    var label = document.createElement('span');
    label.className = 'paw-label';
    label.textContent = opt.hold || '按住，说给 TA 听';

    var alt = document.createElement('button');
    alt.type = 'button';
    alt.className = 'ghost-btn';
    alt.textContent = '改用文字';

    col.appendChild(btn); col.appendChild(label); col.appendChild(alt);

    if (opt.skip) {
      var sk = document.createElement('button');
      sk.type = 'button';
      sk.className = 'ghost-btn';
      sk.textContent = opt.skip;
      sk.addEventListener('click', function () { slot.innerHTML = ''; opt.onSkip && opt.onSkip(); });
      col.appendChild(sk);
    }

    var t0 = 0;
    var mediaRecorder = null;
    var audioChunks = [];
    var asrWs = null;

    function start(e) {
      e.preventDefault();
      t0 = Date.now();
      btn.classList.add('is-holding');
      recOverlay.hidden = false;
      $('#recTip').textContent = '松开结束';
      audioChunks = [];

      navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        mediaRecorder.ondataavailable = function(ev) {
          if (ev.data.size > 0) audioChunks.push(ev.data);
        };
        mediaRecorder.start(100); // 每100ms一个chunk
      }).catch(function() {
        // 麦克风不可用，静默降级到手动输入
      });
    }

    function end() {
      if (!t0) return;
      var dur = Date.now() - t0; t0 = 0;
      btn.classList.remove('is-holding');
      recOverlay.hidden = true;

      if (mediaRecorder) {
        mediaRecorder.stream.getTracks().forEach(function(t) { t.stop(); });
        if (dur < 550) { mediaRecorder = null; label.textContent = '太短了，再按久一点'; return; }

        $('#recTip').textContent = '正在转写…';

        // 等待所有 chunk 收集完毕
        mediaRecorder.onstop = function() {
          var blob = new Blob(audioChunks, { type: 'audio/webm' });
          audioChunks = [];
          doASR(blob, function(text) {
            mediaRecorder = null;
            if (text) {
              editor(text);
            } else {
              // 转写失败，降级到手动输入
              editor('');
            }
          });
        };
        mediaRecorder.stop();
      } else {
        // 没有麦克风权限，直接手动输入
        if (dur < 550) { label.textContent = '太短了，再按久一点'; return; }
        editor('');
      }
    }
    btn.addEventListener('pointerdown', start);
    btn.addEventListener('pointerup', end);
    btn.addEventListener('pointerleave', end);
    btn.addEventListener('pointercancel', end);
    alt.addEventListener('click', function () { editor(''); });

    // 发送前编辑
    function editor(text) {
      col.innerHTML = '';
      var field = document.createElement('div');
      field.className = 'field';
      var ta = document.createElement('textarea');
      ta.rows = 2;
      ta.placeholder = opt.placeholder || '写下来也可以…';
      ta.value = text;
      var send = document.createElement('button');
      send.type = 'button';
      send.className = 'icon-btn';
      send.setAttribute('aria-label', '发送');
      send.innerHTML = '<svg viewBox="0 0 24 24"><use href="#send"></use></svg>';
      field.appendChild(ta); field.appendChild(send);
      col.appendChild(field);

      var row = document.createElement('div');
      row.className = 'slot-row';
      row.style.justifyContent = 'center';
      var again = document.createElement('button');
      again.type = 'button';
      again.className = 'ghost-btn';
      again.textContent = '重新说';
      again.addEventListener('click', function () { capture(slot, opt); });
      row.appendChild(again);
      if (opt.skip) {
        var sk2 = document.createElement('button');
        sk2.type = 'button';
        sk2.className = 'ghost-btn';
        sk2.textContent = opt.skip;
        sk2.addEventListener('click', function () { slot.innerHTML = ''; opt.onSkip && opt.onSkip(); });
        row.appendChild(sk2);
      }
      col.appendChild(row);

      ta.focus();
      ta.addEventListener('input', function () {
        ta.style.height = 'auto'; ta.style.height = Math.min(96, ta.scrollHeight) + 'px';
      });
      function submit() {
        var v = ta.value.trim();
        if (!v) { ta.focus(); return; }
        slot.innerHTML = '';
        opt.onDone(v);
      }
      send.addEventListener('click', submit);
      ta.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
      });
    }
  }

  function actionButton(slot, text, fn) {
    slot.innerHTML = '';
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'primary-btn';
    b.textContent = text;
    b.addEventListener('click', fn);
    slot.appendChild(b);
  }

  /* ────────────────────────────────────────────────────────────────────
     4. 场景调度
     ──────────────────────────────────────────────────────────────────── */
  var scenes = {};
  $$('.scene').forEach(function (el) { scenes[el.dataset.scene] = el; });

  function goto(name) {
    Object.keys(scenes).forEach(function (k) {
      var isTarget = k === name;
      scenes[k].classList.toggle('is-active', isTarget);
      scenes[k].classList.toggle('is-leaving', !isTarget);
    });
    S.scene = name; save();
    if (SCENE_INIT[name]) SCENE_INIT[name]();
  }

  /* ── 场景 0：开场（6–10 秒，可跳过） ─────────────────────────────── */
  function initIntro() {
    var host = $('#introPaws');
    if (host.childElementCount) return;
    var pts = [[14, 82], [26, 74], [22, 63], [34, 55], [30, 44], [44, 36], [40, 25]];
    pts.forEach(function (p, i) {
      var wrap = document.createElement('div');
      wrap.innerHTML = pawSvg();
      var svg = wrap.firstChild;
      svg.style.position = 'absolute';
      svg.style.left = p[0] + '%';
      svg.style.top = p[1] + '%';
      svg.style.width = svg.style.height = (20 + (i % 2) * 5) + 'px';
      svg.style.transform = 'rotate(' + (-24 + i * 7) + 'deg)';
      svg.style.animationDelay = (0.25 + i * 0.42) + 's';
      host.appendChild(svg);
    });

    var line = $('#introLine');
    say(line, '<span class="dim">有一串脚印，在暗处亮了一下。</span>', 900);
    say(line, '<span class="dim">熟悉的东西从旁边掠过去。</span>', 3400);
    setTimeout(function () { $('.door').classList.add('is-open'); }, 5200);
    say(line, '跟着 TA 走过的地方，再走一次。', 6000);
    setTimeout(function () {
      var b = $('#introEnter');
      b.hidden = false;
      b.addEventListener('click', function () { goto('journey'); }, { once: true });
    }, 7200);
    setTimeout(function () { if (S.scene === 'intro') goto('journey'); }, 11000);
  }
  $('#skipIntro').addEventListener('click', function () { goto('journey'); });

  /* ── 第二阶段：JourneyPage / 连续叙事式记忆旅程 ─────────────────── */
  var JOURNEY_NODES = [
    { id: 'first_meeting', title: '第一次遇见 TA', reveal: '水面浮起一束暖光。第一次靠近你的那个瞬间，慢慢回来了。', priority: 2 },
    { id: 'first_home', title: '第一次回家', reveal: '又一片光落进水里。我想起了第一次有家的感觉。', priority: 2 },
    { id: 'habit', title: '只有你们知道的小习惯', reveal: '有一些细小的动作，只有你一眼就能认出是我。', priority: 2 },
    { id: 'favorite_activity', title: 'TA 喜欢做什么', reveal: '水流推着我向前，也带回了那些最想奔向的地方。', priority: 2 },
    { id: 'happiest_memory', title: '一段特别幸福的时光', reveal: '最后这束光很亮。它把所有幸福的时刻都留了下来。', priority: 3 }
  ];
  var journeyWorld = $('#journeyWorld');
  var journeyCard = $('#journeyCard');
  var journeyCreator = $('#journeyCreator');
  var journeyConfirm = $('#journeyConfirm');
  var journeyTimer = null;

  function journeyPersonalized(node) {
    var voice = S.journey.voiceDescription || '';
    var name = S.petName || 'TA';
    var place = ['宠物店', '楼下的纸箱', '路边', '朋友家', '收容所'].filter(function (p) { return voice.indexOf(p) >= 0; })[0];
    var shy = /胆小|躲|不出来/.test(voice);
    var rainy = /雨|下雨/.test(voice);
    var first = place ? '在' + place : '在那个还记不太清的地方';
    var copy = {
      first_meeting: { title: '我记得，第一次遇见你', reveal: first + '，' + name + (shy ? '躲在角落里，慢慢向你靠近。' : '朝你走了过来。') },
      first_home: { title: '那天，我们一起回家', reveal: (rainy ? '雨声还在身后。' : '回去的路上，') + '你把我带回了一个可以安心待着的地方。' },
      habit: { title: '你记得我的那些小习惯', reveal: '这些只有你认得的小动作，正在水面上一点点变清楚。' },
      favorite_activity: { title: name + '最喜欢的事', reveal: '我记得自己会因为' + (/晒太阳/.test(voice) ? '一束阳光' : /球|玩具/.test(voice) ? '一个玩具' : '熟悉的气息') + '，忍不住往前跑。' },
      happiest_memory: { title: '我想把那段幸福带过去', reveal: '你说过的那段时光，会变成前面彩虹桥上的光。' }
    };
    return copy[node.id] || { title: node.title, reveal: node.reveal };
  }

  function journeyProgress() {
    var host = $('#journeyProgress');
    host.innerHTML = '';
    for (var i = 0; i < 3; i++) {
      var paw = document.createElement('span');
      paw.className = 'journey-paw ' + (i < S.journey.sceneIndex ? 'is-done' : i === S.journey.sceneIndex ? 'is-current' : '');
      paw.textContent = '⌁';
      host.appendChild(paw);
    }
    var bridge = document.createElement('span');
    bridge.className = 'journey-rainbow-mark';
    bridge.textContent = '✦';
    host.appendChild(bridge);
  }

  function journeyWorldLevel() {
    journeyWorld.dataset.level = String(S.journey.worldLevel || 0);
    var creating = S.journey.stage === 'PET_CREATION' || S.journey.stage === 'PET_CONFIRM';
    journeyWorld.dataset.sceneIndex = String(S.journey.sceneIndex || 0);
    journeyWorld.dataset.state = creating ? 'creation' : S.journey.stage === 'RAINBOW_BRIDGE' ? 'rainbow' : 'swimming';
    journeyWorld.classList.toggle('is-swimming', !creating);
    journeyCard.dataset.state = creating ? 'creation' : 'story';
    journeyCard.classList.toggle('is-over-water', !creating);
    journeyCard.classList.toggle('is-creating', creating);
    journeyWorld.classList.toggle('is-rainbow', S.journey.stage === 'RAINBOW_BRIDGE');
    journeyWorld.classList.toggle('is-running', S.journey.stage === 'RUNNING');
  }

  function journeyCardReset() {
    journeyCreator.hidden = true;
    journeyConfirm.hidden = true;
  }

  function journeyShowNode() {
    var node = JOURNEY_NODES[S.journey.currentMemoryIndex];
    if (!node) return journeyRainbow();
    var narrative = journeyPersonalized(node);
    S.journey.stage = 'MEMORY_REVEAL';
    journeyWorld.classList.remove('is-running'); journeyCard.classList.add('is-flowing');
    journeyCardReset();
    $('#journeyKicker').textContent = '记忆开始渐渐清晰';
    $('#journeyTitle').textContent = narrative.title;
    $('#journeyCopy').textContent = narrative.reveal;
    journeyProgress(); journeyWorldLevel(); save();
    journeyWorld.classList.add('is-processing');
    setTimeout(async function () {
      journeyWorld.classList.remove('is-processing');
      var m = addMemory('journey:' + node.id, narrative.title, node.priority);
      m.summary = narrative.title; m.narrative = narrative.reveal; m.memoryType = node.id; m.emotion = node.id === 'happiest_memory' ? 'joy' : 'warm';
      m.petTraits = S.profile.traits.slice(); m.petBehaviors = S.profile.habits.slice(); m.homeAssets = [node.id];
      var remote = await persistJourneyMemory(node, narrative);
      if (remote) {
        var remoteMemory = remote.created_memory || remote;
        if (remoteMemory && remoteMemory.id) m.backendId = remoteMemory.id;
        if (remote.narration && remote.narration.ai_response) m.aiResponse = remote.narration.ai_response;
      }
      S.journey.memories.push(m);
      S.journey.currentMemoryIndex += 1;
      S.journey.petCompletion = [0.25, 0.4, 0.55, 0.7, 0.85, 1][Math.min(S.journey.currentMemoryIndex, 5)];
      S.journey.worldLevel = Math.min(5, S.journey.worldLevel + 1);
      setDetail(S.journey.petCompletion);
      journeyProgress(); journeyWorldLevel(); save();
      journeyTimer = setTimeout(journeyShowNode, 2300);
    }, 1700);
  }

  function journeyRainbow() {
    S.journey.stage = 'RAINBOW_BRIDGE';
    S.journey.sceneIndex = 2;
    S.journey.petCompletion = 1; S.journey.worldLevel = 5; setDetail(1);
    journeyCardReset();
    $('#journeyKicker').textContent = '彩虹桥';
    $('#journeyTitle').textContent = (S.petName || 'TA') + '要走过彩虹桥了。';
    $('#journeyCopy').textContent = '你刚才说起的那些记忆，正在前面汇成一束光。';
    $('.pet', $('#journeyPet')).src = POSE.run;
    journeyWorldLevel(); journeyProgress(); save();
    clearTimeout(journeyTimer);
  }

  function initJourney() {
    if (!journeyWorld.dataset.bound) {
      journeyWorld.dataset.bound = '1';
      journeyWorld.addEventListener('click', function (e) {
        if (S.journey.stage === 'PET_CREATION' || S.journey.stage === 'PET_CONFIRM') return;
        if (S.journey.sceneIndex === 0) {
          S.journey.sceneIndex = 1; S.journey.worldLevel = 2;
          $('#journeyKicker').textContent = '记忆旅程'; $('#journeyTitle').textContent = '一些画面开始浮现。'; $('#journeyCopy').textContent = '再往前一点，彩虹桥就在前面。';
          journeyWorldLevel(); journeyProgress(); save(); return;
        }
        if (S.journey.sceneIndex === 1) {
          S.journey.sceneIndex = 2; S.journey.stage = 'RAINBOW_BRIDGE'; S.journey.worldLevel = 5; setDetail(1);
          journeyRainbow(); return;
        }
        if (S.journey.sceneIndex === 2) { S.journey.stage = 'HOME_GENERATING'; goto('weave'); }
      });
      // journeyVoice：按住爪印录音，松开后转写，进入宠物确认页
      var jv = $('#journeyVoice');
      var jvMediaRecorder = null;
      var jvAudioChunks = [];
      var jvPermitted = false;
      var jvPending = false;
      var jvStartTime = 0;
      var jvReleased = false;
      var jvTimerInterval = null;
      var jvMaxTimer = null;   // 60秒自动停止

      function finishRecording() {
        if (jvTimerInterval) { clearInterval(jvTimerInterval); jvTimerInterval = null; }
        if (jvMaxTimer) { clearTimeout(jvMaxTimer); jvMaxTimer = null; }
        if (!jvMediaRecorder) return;
        jvMediaRecorder.stream.getTracks().forEach(function (t) { t.stop(); });
        $('#recTip').textContent = '正在转写…';
        $('#recGuidance').hidden = true;
        $('#recTimer').hidden = true;
        recOverlay.hidden = true;
        jvMediaRecorder.onstop = function () {
          var blob = new Blob(jvAudioChunks, { type: 'audio/webm' });
          jvAudioChunks = [];
          doASR(blob, function (text) {
            jvMediaRecorder = null;
            onJourneyVoiceResult(text || mockASR('meet'));
          });
        };
        jvMediaRecorder.stop();
      }

      function startRecordingTimer() {
        // 更新计时器显示
        var seconds = 0;
        jvTimerInterval = setInterval(function () {
          seconds++;
          $('#recTimer').textContent = seconds + ' 秒';
          if (seconds >= 60) {
            finishRecording();
          }
        }, 1000);
        // 60秒自动停止
        jvMaxTimer = setTimeout(finishRecording, 60000);
      }

      jv.addEventListener('pointerdown', function (e) {
        e.preventDefault();
        jv.classList.add('is-holding');
        recOverlay.hidden = false;
        $('#recTip').textContent = '请稍候…';
        $('#recGuidance').hidden = false;
        $('#recTimer').hidden = false;
        $('#recTimer').textContent = '0 秒';
        jvAudioChunks = [];
        jvPermitted = false;
        jvPending = true;
        jvReleased = false;

        navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
          jvPermitted = true;
          jvPending = false;
          jvStartTime = Date.now();
          $('#recTip').textContent = '松开结束';
          $('#recGuidance').hidden = true;   // 授权后隐藏引导词，专注录音
          jvMediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
          jvMediaRecorder.ondataavailable = function (ev) {
            if (ev.data.size > 0) jvAudioChunks.push(ev.data);
          };
          jvMediaRecorder.start(100);
          startRecordingTimer();
          if (jvReleased) finishRecording();
        }).catch(function () {
          jvPending = false;
          recOverlay.hidden = true;
          jv.classList.remove('is-holding');
          onJourneyVoiceResult(mockASR('meet'));
        });
      });

      jv.addEventListener('pointerup', function () {
        if (!jv.classList.contains('is-holding')) return;
        jv.classList.remove('is-holding');

        if (jvPending) {
          jvReleased = true;
          $('#recTip').textContent = '正在等待…';
          return;
        }

        if (!jvMediaRecorder) {
          onJourneyVoiceResult(mockASR('meet'));
          return;
        }

        var dur = Date.now() - jvStartTime;
        if (dur < 550) {
          // 太短：停止计时和录音，但不跳场景
          if (jvTimerInterval) { clearInterval(jvTimerInterval); jvTimerInterval = null; }
          if (jvMaxTimer) { clearTimeout(jvMaxTimer); jvMaxTimer = null; }
          jvMediaRecorder.stream.getTracks().forEach(function (t) { t.stop(); });
          jvMediaRecorder = null;
          recOverlay.hidden = true;
          $('#recGuidance').hidden = true;
          $('#recTimer').hidden = true;
          $('#journeyVoiceLabel').textContent = '太短了，再按久一点';
          return;
        }

        finishRecording();
      });

      jv.addEventListener('pointerleave', function () {
        if (!jv.classList.contains('is-holding')) return;
        jv.classList.remove('is-holding');
        recOverlay.hidden = true;
        jvPending = false;
        jvReleased = false;
        if (jvTimerInterval) { clearInterval(jvTimerInterval); jvTimerInterval = null; }
        if (jvMaxTimer) { clearTimeout(jvMaxTimer); jvMaxTimer = null; }
        if (jvMediaRecorder) {
          jvMediaRecorder.stream.getTracks().forEach(function (t) { t.stop(); });
          jvMediaRecorder = null;
        }
        $('#recGuidance').hidden = true;
        $('#recTimer').hidden = true;
      });

      jv.addEventListener('pointercancel', function () {
        jv.classList.remove('is-holding');
        recOverlay.hidden = true;
        jvPending = false;
        jvReleased = false;
        if (jvTimerInterval) { clearInterval(jvTimerInterval); jvTimerInterval = null; }
        if (jvMaxTimer) { clearTimeout(jvMaxTimer); jvMaxTimer = null; }
        if (jvMediaRecorder) {
          jvMediaRecorder.stream.getTracks().forEach(function (t) { t.stop(); });
          jvMediaRecorder = null;
        }
        $('#recGuidance').hidden = true;
        $('#recTimer').hidden = true;
      });

      // 预设名字列表（用于正则快速匹配）
      var PRESET_NAMES = ['豆豆', '年糕', '团子', '煤球', '花卷', '布丁', '小白', '旺财', '来福', '球球', '嘟嘟', '果冻', '奶茶', '饼干', '麻薯'];

      // 正则从文本中提取宠物名字（不限定字符类型，用标点和长度作边界）
      function extractNameByRegex(text) {
        if (!text) return null;
        // 1. "它/他/她叫XXX" 或 "叫XXX"（名字1-20字，以标点/空格/句尾截止）
        var m = text.match(/[它他她]?叫([^\s，,。！？、；:：""''（）()]{1,20})/);
        if (m) return m[1];
        // 2. "名字是XXX" 或 "TA叫XXX"（名字1-20字）
        m = text.match(/(?:名字|它叫|他叫|她叫)([^\s，,。！？、；:：""''（）()]{1,20})/);
        if (m) return m[1];
        // 3. "他叫XX，是YY" → 提取 XX
        m = text.match(/[它他她]叫([^\s，,。！？、；:：""''（）()]{1,20})[，,]?[是为]?/);
        if (m) return m[1];
        // 4. "他叫XX，YY" → 提取 XX（无"是"字）
        m = text.match(/[它他她]叫([^\s，,。！？、；:：""''（）()]{1,20})[,，]/);
        if (m) return m[1];
        // 5. "它的名字是XXXX" → 提取 XXXX
        m = text.match(/(?:它的名字|他名字|她名字)是([^\s，,。！？、；:：""''（）()]{1,20})/);
        if (m) return m[1];
        // 6. 开头"XX叫/是"且紧接着是描述，但"叫/是"后必须是另一个词而非"的"（排除"叫得很欢"）
        m = text.match(/^([^\s，,。！？、；:：""''（）()]{1,6})(?:叫|是)(?!['"]?[的得])[^\s，,]/);
        if (m) return m[1];
        // 精确匹配预设名字（兜底）
        for (var i = 0; i < PRESET_NAMES.length; i++) {
          if (text.indexOf(PRESET_NAMES[i]) >= 0) return PRESET_NAMES[i];
        }
        return null;
      }

      // 从后端 LLM 提取名字
      function extractNameByLLM(text, callback) {
        fetch(API_BASE + '/pets/' + (S.backendPetId || '') + '/extract-name', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: text })
        })
          .then(function (res) { return res.json(); })
          .then(function (data) { callback(data.name || ''); })
          .catch(function () { callback(''); });
      }

      // 显示语音识别结果确认界面
      function showVoiceConfirm(name, description) {
        journeyCreator.hidden = true;
        var confirmBox = $('#journeyVoiceConfirm') || createVoiceConfirmUI();
        confirmBox.hidden = false;
        $('#journeyConfirmName').value = name;
        $('#journeyConfirmDesc').value = description;
        $('#journeyConfirmName').focus();
      }

      function createVoiceConfirmUI() {
        var wrapper = document.createElement('div');
        wrapper.id = 'journeyVoiceConfirm';
        wrapper.className = 'journey-creator';
        wrapper.style.gap = '10px';
        wrapper.style.marginTop = '2px';

        var nameRow = document.createElement('div');
        nameRow.style.display = 'flex';
        nameRow.style.alignItems = 'center';
        nameRow.style.gap = '8px';

        var nameLabel = document.createElement('span');
        nameLabel.style.cssText = 'font-size:12px;color:#8A7869;white-space:nowrap;';
        nameLabel.textContent = 'TA 叫';
        var nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.id = 'journeyConfirmName';
        nameInput.className = 'journey-input';
        nameInput.placeholder = '还没起名字…';
        nameInput.style.flex = '1';
        nameRow.appendChild(nameLabel);
        nameRow.appendChild(nameInput);

        var descInput = document.createElement('textarea');
        descInput.id = 'journeyConfirmDesc';
        descInput.className = 'journey-input';
        descInput.rows = 3;
        descInput.placeholder = '说说你们的故事…';
        descInput.style.resize = 'none';

        var btnRow = document.createElement('div');
        btnRow.style.display = 'flex';
        btnRow.style.gap = '10px';
        btnRow.style.justifyContent = 'center';

        var retryBtn = document.createElement('button');
        retryBtn.type = 'button';
        retryBtn.className = 'ghost-btn';
        retryBtn.textContent = '重新说';
        retryBtn.style.fontSize = '13px';
        retryBtn.addEventListener('click', function () {
          $('#journeyVoiceConfirm').hidden = true;
          journeyCreator.hidden = false;
        });

        var okBtn = document.createElement('button');
        okBtn.type = 'button';
        okBtn.className = 'primary-btn';
        okBtn.textContent = '确认';
        okBtn.addEventListener('click', function () {
          var name = $('#journeyConfirmName').value.trim();
          var desc = $('#journeyConfirmDesc').value.trim();
          $('#journeyVoiceConfirm').hidden = true;
          onVoiceConfirm(name, desc);
        });

        btnRow.appendChild(retryBtn);
        btnRow.appendChild(okBtn);

        wrapper.appendChild(nameRow);
        wrapper.appendChild(descInput);
        wrapper.appendChild(btnRow);

        // 插入到 journeyCreator 之后
        journeyCreator.parentNode.insertBefore(wrapper, journeyCreator.nextSibling);
        return wrapper;
      }

      function onVoiceConfirm(name, description) {
        S.petName = name || mockASR('name');
        S.journey.voiceDescription = description || mockASR('meet');
        S.journey.petImage = 'assets/pet-idle.webp';
        S.hasPhoto = true;
        interpret(S.journey.voiceDescription);
        ensureBackendPet().then(function () {
          S.journey.stage = 'PET_CONFIRM';
          setDetail(0.35);
          journeyWorld.classList.remove('is-running');
          journeyCardReset();
          journeyConfirm.hidden = false;
          $('#journeyKicker').textContent = '';
          $('#journeyTitle').textContent = '我想起来啦';
          $('#journeyCopy').textContent = '我是这样的一只小狗对嘛？';
          journeyProgress();
          journeyWorldLevel();
          save();
        });
      }

      function onJourneyVoiceResult(text) {
        var rawText = text || mockASR('meet');
        // 1. 正则优先提取名字
        var name = extractNameByRegex(rawText);
        if (name) {
          showVoiceConfirm(name, rawText);
          return;
        }
        // 2. 正则匹配不到，且 pet 已创建（backendPetId 存在），调 LLM 二次识别
        if (S.backendPetId) {
          extractNameByLLM(rawText, function (llmName) {
            if (llmName) {
              showVoiceConfirm(llmName, rawText);
            } else {
              showVoiceConfirm('', rawText);
            }
          });
        } else {
          // pet 还未创建，无法调 LLM，直接用空名字显示描述
          showVoiceConfirm('', rawText);
        }
      }
      $('#journeyRegeneratePhoto').addEventListener('change', function () {
        var file = this.files && this.files[0]; if (!file) return;
        var reader = new FileReader();
        reader.onload = async function () {
          S.journey.petReferenceImage = reader.result;
          S.journey.regenerationPrompt = [S.journey.voiceDescription, '根据补充照片校准外形'].filter(Boolean).join('；');
          S.journey.isRegenerating = true;
          var pet = $('#journeyConfirmPet');
          pet.classList.add('is-regenerating');
          $('#journeyCopy').textContent = '正在根据照片和描述重新生成……';
          $('#journeyConfirmBtn').disabled = true;
          await syncPetPhoto(file);
          setTimeout(function () {
            // Mock 生成：真实接入时将 regenerationPrompt 与参考图传给生图服务。
            var voice = S.journey.voiceDescription || '';
            var pose = /跑|奔|活泼/.test(voice) ? POSE.approach : /躲|胆小|雨/.test(voice) ? POSE.down : POSE.idle;
            pet.src = pose; pet.classList.remove('is-regenerating');
            S.journey.petImage = pose; S.journey.isRegenerating = false; S.hasPhoto = true;
            $('#journeyCopy').textContent = '照片和描述都记住了。这个样子更像你记忆里的我了吗？';
            $('#journeyConfirmBtn').disabled = false; save();
          }, 1500);
        };
        reader.readAsDataURL(file);
      });
      $('#journeyConfirmBtn').addEventListener('click', function () {
        $('.pet', $('#journeyPet')).src = S.journey.petImage || POSE.idle;
        S.journey.stage = 'RUNNING'; S.journey.sceneIndex = 0; S.journey.currentMemoryIndex = 0; S.journey.petCompletion = 0.25; S.journey.worldLevel = 1;
        setDetail(0.25); journeyWorld.classList.add('is-running'); journeyCardReset();
        $('#journeyKicker').textContent = '记忆旅程'; $('#journeyTitle').textContent = (S.petName || 'TA') + '，好像想起来一点了。'; $('#journeyCopy').textContent = S.journey.voiceDescription ? '你说起的' + (S.journey.voiceDescription.slice(0, 20)) + '……正在水里慢慢回来。' : '跟着 TA 向前走，世界会一点点回来。';
        journeyProgress(); journeyWorldLevel(); save();
        clearTimeout(journeyTimer);
      });
    }
    var stage = S.journey.stage || 'PET_CREATION';
    if (stage === 'PET_CREATION') {
      journeyCardReset(); journeyCard.classList.remove('is-flowing'); journeyCreator.hidden = false;
      $('#journeyKicker').textContent = ''; $('#journeyTitle').innerHTML = '我好像……<br>记不清自己原来的样子了'; $('#journeyCopy').textContent = '你可以帮我想起来吗？';
    } else if (stage === 'PET_CONFIRM') {
      journeyCardReset(); journeyCard.classList.remove('is-flowing'); journeyConfirm.hidden = false;
      $('#journeyConfirmPet').src = S.journey.petImage || 'assets/pet-idle.webp';
      $('#journeyKicker').textContent = ''; $('#journeyTitle').textContent = '我想起来啦'; $('#journeyCopy').textContent = '我是这样的一只小狗对嘛？';
    } else if (stage === 'MEMORY_INPUT' || stage === 'MEMORY_REVEAL' || stage === 'MEMORY_PROCESSING') journeyShowNode();
    else if (stage === 'RAINBOW_BRIDGE') journeyRainbow();
    else if (stage === 'RUNNING') { journeyCardReset(); journeyWorld.classList.add('is-running'); clearTimeout(journeyTimer); }
    journeyProgress(); journeyWorldLevel();
  }


  /* ── 家园生成 ───────────────────────────────────────────────────── */
  function initWeave() {
    S.journey.stage = 'HOME_GENERATING';
    if (!S.journey.homeConfig) {
      S.journey.homeConfig = {
        theme: 'warm_nature', lighting: 'sunny',
        assets: S.journey.memories.map(function (m) { return m.memoryType; })
      };
    }
    var w = scenes.weave;
    if (w.dataset.ready) return;
    w.dataset.ready = '1';
    w.classList.add('is-drawing');

    var host = $('#weavePaws');
    for (var i = 0; i < 7; i++) {
      var wrap = document.createElement('div');
      wrap.innerHTML = pawSvg('is-lit');
      var svg = wrap.firstChild;
      svg.style.position = 'absolute';
      svg.style.left = (10 + i * 12) + '%';
      svg.style.bottom = (27 + Math.sin(i) * 3) + '%';
      svg.style.opacity = 0;
      svg.style.transition = 'opacity .8s ease';
      host.appendChild(svg);
      (function (s, k) { setTimeout(function () { s.style.opacity = 1; }, 300 + k * 260); })(svg, i);
    }

    var n = $('#nWeave');
    say(n, '<span class="dim">脚印一枚一枚，走回同一个地方。</span>', 500);
    say(n, '<span class="dim">墙立起来了，灯挂上去了。</span>', 3200);
    say(n, '家已经在这里了。', 5400);
    syncHomeConfig();
    setTimeout(function () { if (S.scene === 'weave') goto('home'); }, 7400);
  }

  /* ────────────────────────────────────────────────────────────────────
     5. 第三阶段：首页（房子 / 信箱 / 熄灯休息）
     ──────────────────────────────────────────────────────────────────── */
  var homeHub = $('[data-scene="home"]');
  var homeNoteTimer = null;

  function localDay() {
    try { return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai' }).format(new Date()); }
    catch (e) { return new Date().toISOString().slice(0, 10); }
  }
  function localDayLabel() {
    try { return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long', day: 'numeric' }).format(new Date()); }
    catch (e) { return localDay(); }
  }
  function rememberConversation(text) {
    S.conversations.push({ day: localDay(), text: String(text), at: Date.now() });
    S.conversations = S.conversations.slice(-60);
  }
  function buildDailyLetter() {
    var day = localDay();
    var turns = S.conversations.filter(function (item) { return item.day === day; });
    var old = S.dailyLetters.filter(function (item) { return item.day === day; })[0];
    if (old && old.turnCount === turns.length) return old;

    var pet = S.petName || '我';
    var first = turns[0] && turns[0].text.replace(/\s+/g, ' ').slice(0, 34);
    var last = turns[turns.length - 1] && turns[turns.length - 1].text.replace(/\s+/g, ' ').slice(0, 34);
    var paragraphs;
    if (turns.length) {
      paragraphs = [
        '今天你来和我说话了。你说“' + first + (first.length >= 34 ? '…' : '') + '”，我一直记着。',
        turns.length > 1
          ? '后来你又说“' + last + (last.length >= 34 ? '…' : '') + '”。这些话我都收好，放在我们家最暖的地方。'
          : '我听见以后，把尾巴轻轻扫了两下。你不用急着说完，我会慢慢听。',
        '等你下次回来，信箱还是开着的，我也会在这里。'
      ];
    } else {
      paragraphs = [
        '今天屋子很安静，我在窗边待了一会儿，也看了一会儿门。',
        '还没有听见你的声音没关系。等你想说话的时候，我就在这里。'
      ];
    }
    var letter = { day: day, turnCount: turns.length, paragraphs: paragraphs, sign: pet };
    S.dailyLetters = S.dailyLetters.filter(function (item) { return item.day !== day; }).concat(letter).slice(-21);
    save();
    return letter;
  }
  function showHomeNote(text) {
    var note = $('#homeNote');
    note.textContent = text;
    note.classList.add('is-visible');
    clearTimeout(homeNoteTimer);
    homeNoteTimer = setTimeout(function () { note.classList.remove('is-visible'); }, 2600);
  }
  function setHomeLights(on, announce) {
    S.story.homeLightsOn = on;
    S.story.petState = on ? 'idle' : 'down';
    homeHub.classList.toggle('is-lights-off', !on);
    $('#homeLamp').setAttribute('aria-label', on ? '关灯，让小狗休息' : '开灯，叫醒小狗');
    if (announce) showHomeNote(on ? '灯亮起来了，TA 抬头看了看你。' : '灯熄了，TA 趴下休息。');
    save();
  }
  function openLetter() {
    var letter = buildDailyLetter();
    var body = $('#letterBody');
    body.innerHTML = '';
    letter.paragraphs.forEach(function (paragraph) {
      var p = document.createElement('p'); p.textContent = paragraph; body.appendChild(p);
    });
    $('#letterDate').textContent = localDayLabel();
    $('#letterSign').textContent = '— ' + letter.sign;
    $('#letterSheet').hidden = false;
    goto('letter');
  }
  function initLetter() {
    if ($('#letterSheet').hidden) openLetter();
  }
  function initHome() {
    S.journey.stage = 'COMPLETE';
    setDetail(1);
    setHomeLights(S.story.homeLightsOn !== false, false);
  }

  $('#homeLamp').addEventListener('click', function () { setHomeLights(!S.story.homeLightsOn, true); });
  $('#homeMailbox').addEventListener('click', openLetter);
  $('#homeBowl').addEventListener('click', function () {
    if (!S.story.homeLightsOn) setHomeLights(true, false);
    showHomeNote('TA 走到饭盆旁边，摇了摇尾巴。');
  });
  $('#homePet').addEventListener('click', function () {
    goto('companion');
  });
  $('#letterClose').addEventListener('click', function () { $('#letterSheet').hidden = true; goto('home'); });
  $('#homeBack').addEventListener('click', function () { goto('home'); });

  /* ────────────────────────────────────────────────────────────────────
     6. Companion：想象性陪伴叙事
        每一轮 = 环境描述 → 角色动作 → 角色对白 → 事件推进
        真实 Memory 只约束"TA 是谁"，不规定接下来聊什么；
        新故事绝不写成"我们以前发生过的事"。
     ──────────────────────────────────────────────────────────────────── */
  var thread = $('#thread');
  var petC = $('#petC');

  function N() { return S.petName || 'TA'; }
  function withName(t) { return S.petName ? String(t).replace(/ ?TA ?/g, S.petName) : String(t); }

  var BEATS = [
    { pose: 'approach', mood: '灯还亮着',
      env: '屋里很安静，只有灯在响一点点电流的声音。',
      act: '{n}从沙发那边站起来，甩了甩身上的毛，往门口走了两步又停下。',
      say: '你回来啦。我刚才听见外面有脚步声，还以为是你。',
      push: '要不要坐下来歇一会儿？' },
    { pose: 'happy', mood: '窗边有风', needs: 'window',
      env: '窗户开着一条缝，风把窗帘吹起来一下。',
      act: '{n}跳上窗台，鼻子贴着玻璃，尾巴一直在动。',
      say: '外面味道变了，你闻到了吗？我想出去看看。',
      push: '今天要不要一起下楼走一圈？' },
    { pose: 'run', mood: '有点吵',
      env: '楼道里有人上楼，声音一顿一顿的。',
      act: '{n}一下子冲到门口，脚下打滑，撞到了鞋柜。',
      say: '不是你。……好吧，不是你。我先回来了。',
      push: '你要不要叫它一声？' },
    { pose: 'down', mood: '安静下来了',
      env: '天色慢慢暗下去，房间只剩下一盏灯。',
      act: '{n}绕着你转了半圈，在你脚边趴下，下巴压在你鞋子上。',
      say: '我就在这儿。你先忙你的。',
      push: '你想说点什么，我都听着。' },
    { pose: 'happy', mood: '厨房有声音', needs: 'bowl',
      env: '厨房那边传来袋子被捏响的声音。',
      act: '{n}耳朵先动了一下，犹豫了两秒，还是探头过去看。',
      say: '那个……是给我的吗？我可以只吃一点点。',
      push: '给不给？' },
    { pose: 'approach', mood: '玩具找到了',
      env: '沙发底下有个东西被拨出来，滚了半圈。',
      act: '{n}叼着它跑过来，放在你面前，退后两步，看着你。',
      say: '给你。你扔，我去捡。',
      push: '要不要陪 TA 玩一会儿？' },
    { pose: 'down', mood: '外面在下雨',
      env: '外面开始下雨，玻璃上有水一道一道往下走。',
      act: '{n}靠着你的腿坐下来，把身子往里挤了挤。',
      say: '下雨的时候屋子里最好了。你别走远。',
      push: '你要不要也坐下来？' },
    { pose: 'idle', mood: '灯还亮着',
      env: '灯下有一小块暖的地方，别的地方都是凉的。',
      act: '{n}把自己整个卷成一团，正好卡在那块光里。',
      say: '这里刚刚好。你要不要也过来一点？',
      push: '再待一会儿吧。' },
    { pose: 'happy', mood: '想出门', needs: 'leash',
      env: '门口那根绳子被碰到了，晃了两下。',
      act: '{n}立刻站起来，来回走，一直看着门。',
      say: '走吗？走吗？我已经准备好了。',
      push: '要出门，还是先等等？' },
    { pose: 'approach', mood: '睡不着',
      env: '很晚了，屋子里只剩下钟走的声音。',
      act: '{n}轻轻跳上床边，趴在那块空着的位置。',
      say: '我不吵你。你睡吧，我看着门。',
      push: '要关灯了吗？' }
  ];

  function line(cls, text) {
    var p = document.createElement('p');
    p.className = 'line ' + cls;
    p.textContent = text;
    return p;
  }
  function isThreadNearBottom() {
    return thread.scrollHeight - thread.scrollTop - thread.clientHeight < 42;
  }
  function scrollEnd(force) {
    if (!force && !isThreadNearBottom()) return;
    thread.scrollTo({ top: thread.scrollHeight, behavior: force ? 'smooth' : 'auto' });
  }

  function typing() {
    var t = document.createElement('div');
    t.className = 'typing';
    t.innerHTML = '<i></i><i></i><i></i>';
    var follow = isThreadNearBottom();
    thread.appendChild(t); if (follow) scrollEnd(true);
    return t;
  }

  function setPose(pose) {
    $('.pet', petC).src = POSE[pose] || POSE.idle;
    S.story.petState = pose;
    if (pose === 'run') { petC.classList.add('is-running'); setTimeout(function () { petC.classList.remove('is-running'); }, 1800); }
    if (pose === 'happy') { petC.classList.add('is-bouncing'); setTimeout(function () { petC.classList.remove('is-bouncing'); }, 2000); }
  }

  var busy = false;

  function nextBeat() {
    // 只挑用得上的：needs 指向的安全物件必须真的出现在这个家里
    var pool = BEATS.filter(function (b, i) {
      if (S.story.used.indexOf(i) >= 0) return false;
      if (b.needs && S.profile.objects.indexOf(b.needs) < 0) return false;
      return true;
    });
    if (!pool.length) { S.story.used = []; pool = BEATS.slice(); }
    var beat = pick(pool);
    S.story.used.push(BEATS.indexOf(beat));
    S.story.beat++;
    return beat;
  }

  async function playBeat(beat) {
    if (busy) return;
    busy = true;
    var box = document.createElement('div');
    box.className = 'beat';
    var t = typing();
    await sleep(700);
    t.remove();
    var follow = isThreadNearBottom();
    thread.appendChild(box); if (follow) scrollEnd(true);

    box.appendChild(line('line-env', beat.env)); if (follow) scrollEnd(true);
    await sleep(750);
    setPose(beat.pose);
    box.appendChild(line('line-act', beat.act.replace(/\{n\}/g, N()))); if (follow) scrollEnd(true);
    await sleep(850);
    box.appendChild(line('line-say', beat.say)); if (follow) scrollEnd(true);
    await sleep(650);
    box.appendChild(line('line-push', withName(beat.push))); if (follow) scrollEnd(true);

    S.story.mood = beat.mood || S.story.mood;
    $('#cSub').textContent = S.story.mood;
    save();
    busy = false;
    $('#btnContinue').classList.add('is-nudging');
  }

  async function respond(text) {
    if (busy) return;
    busy = true;
    $('#btnContinue').classList.remove('is-nudging');

    var follow = isThreadNearBottom();
    var me = line('line-me', text);
    thread.appendChild(me); if (follow) scrollEnd(true);
    rememberConversation(text);

    // 情绪保护：强烈痛苦时温和陪伴，并提示联系信任的人或专业支持
    if (DISTRESS.test(text)) {
      var t1 = typing(); await sleep(900); t1.remove();
      var b1 = document.createElement('div'); b1.className = 'beat'; thread.appendChild(b1);
      b1.appendChild(line('line-act', N() + '没有动，只是把头靠过来，靠在你手边。'));
      await sleep(700);
      b1.appendChild(line('line-say', '不用说了。我在这儿，你想坐多久都行。'));
      await sleep(600);
      b1.appendChild(line('line-soft', '如果心里太沉，也可以和你信任的人说说，或者找专业的支持聊一聊。'));
      if (follow) scrollEnd(true); busy = false; save(); return;
    }

    // 自然纠正：进入后台候选修正，不直接覆盖既有 Memory
    if (/^(不是|不对|它不会|TA不会|他不会|她不会|没有)/.test(text)) {
      var t2 = typing(); await sleep(800); t2.remove();
      var b2 = document.createElement('div'); b2.className = 'beat'; thread.appendChild(b2);
      b2.appendChild(line('line-act', N() + '歪了一下头，像是在等你把话说完。'));
      await sleep(600);
      b2.appendChild(line('line-say', '嗯，那我记住这个。'));
      if (follow) scrollEnd(true);
      S.story.threads = (S.story.threads || []).concat([{ type: 'correction', rawText: text, confirmed: false }]);
      save(); busy = false;
      return;
    }

    interpret(text);
    var t3 = typing(); await sleep(850); t3.remove();
    var b3 = document.createElement('div'); b3.className = 'beat'; thread.appendChild(b3);
    var remoteReply = await backendChat(text);
    if (remoteReply) {
      b3.appendChild(line('line-act', N() + '看着你，耳朵轻轻动了一下。'));
      await sleep(500);
      b3.appendChild(line('line-say', remoteReply));
      if (follow) scrollEnd(true);
      busy = false; save();
      return;
    }
    var reacts = [
      { act: N() + '抬头看着你，尾巴在地板上扫了两下。', say: '好呀。你说什么我都听。' },
      { act: N() + '往你这边挪了挪，整个身子贴上来。', say: '我在听，你继续说。' },
      { act: N() + '把爪子搭在你腿上，眼睛一直没离开。', say: '嗯，然后呢？' }
    ];
    var r = pick(reacts);
    b3.appendChild(line('line-act', r.act));
    await sleep(650);
    b3.appendChild(line('line-say', r.say));
    if (follow) scrollEnd(true);
    busy = false; save();
    setTimeout(function () { if (!busy) playBeat(nextBeat()); }, 1400);
  }

  function initCompanion() {
    S.journey.stage = 'COMPLETE';
    setDetail(1);                          // 进入家园后以清晰的 Base 形象陪伴
    $('#cName').textContent = S.petName ? S.petName + '的家' : '家';
    $('#cSub').textContent = S.story.mood;
    $('.pet', petC).src = POSE[S.story.petState] || POSE.idle;

    if (thread.dataset.ready) return;
    thread.dataset.ready = '1';

    if (!thread.childElementCount) {
      var open = document.createElement('p');
      open.className = 'line line-soft';
      open.textContent = S.petName ? '门开着，灯是亮的。' : '门开着，灯是亮的。名字还没有说出口也没关系。';
      thread.appendChild(open);
      setTimeout(function () { playBeat(nextBeat()); }, 900);   // 首次自动开场
    }
    requestAnimationFrame(function () { thread.scrollTop = thread.scrollHeight; });
  }

  $('#composer').addEventListener('submit', function (e) {
    e.preventDefault();
    var v = $('#cInput').value.trim();
    if (!v) return;
    $('#cInput').value = '';
    respond(v);
  });
  // 输入框右侧「继续」：不知道说什么时，直接推进下一轮剧情
  $('#btnContinue').addEventListener('click', function () {
    $('#btnContinue').classList.remove('is-nudging');
    playBeat(nextBeat());
  });

  /* ────────────────────────────────────────────────────────────────────
     6. 启动
     ──────────────────────────────────────────────────────────────────── */
  var SCENE_INIT = {
    intro: initIntro, journey: initJourney,
    weave: initWeave, home: initHome, letter: initLetter, companion: initCompanion
  };

  var jump = { '1': 'intro', '2': 'journey', '3': 'home', '4': 'companion' };
  document.addEventListener('keydown', function (e) {
    if (e.target && e.target.matches && e.target.matches('input, textarea')) return;
    if (jump[e.key]) goto(jump[e.key]);
    if (e.key === 'r' || e.key === 'R') reset();
  });

  window.__mh = { S: S, goto: goto, reset: reset, addMemory: addMemory, addPaw: addPaw };  // 调试用

  var resumed = load();
  setDetail(S.detail);
  goto(resumed && (S.scene === 'home' || S.scene === 'letter' || S.scene === 'companion') ? S.scene : 'intro');
})();
