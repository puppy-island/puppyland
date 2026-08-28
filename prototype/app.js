/* ==========================================================================
   记忆家园 Memory Home — 前端原型逻辑
   对应 PRD v2.1：场景驱动采集 → 后台记忆整理 → 唯一 Companion 叙事陪伴

   后端接入：保留 localStorage 离线优先，异步同步到 FastAPI 后端。
   ========================================================================== */
(function () {
  'use strict';

  /* ────────────────────────────────────────────────────────────────────
     0. 品种图谱 + 颜色滤镜（对应参考项目 breeds.ts / overlays.ts）
     ──────────────────────────────────────────────────────────────────── */
  var BREEDS = {
    '柯基':       { name: '柯基犬',       image: 'assets/breeds/柯基犬.png' },
    '中华田园犬': { name: '中华田园犬',   image: 'assets/breeds/中华田园犬.png' },
    '柴犬':       { name: '柴犬',         image: 'assets/breeds/柴犬.png' },
    '哈士奇':     { name: '哈士奇',       image: 'assets/breeds/哈士奇.png' },
    '金毛':       { name: '金毛寻回犬',   image: 'assets/breeds/金毛.png' },
    '拉布拉多':   { name: '拉布拉多寻回犬', image: 'assets/breeds/拉布拉多.png' },
    '泰迪':       { name: '贵宾犬',       image: 'assets/breeds/泰迪.png' },
    '法斗':       { name: '法国斗牛犬',   image: 'assets/breeds/法斗.png' },
    '小白狗':     { name: '小白狗',       image: 'assets/breeds/小白狗.png' }
  };
  var BREED_ALIASES = [
    ['柯基','威尔士柯基','柯基犬','welsh corgi'],
    ['中华田园犬','土狗','田园犬','小土狗','黄白小土狗','柴狗'],
    ['柴犬','shiba inu','shiba'],
    ['哈士奇','西伯利亚雪橇犬','husky','二哈'],
    ['金毛','金毛寻回犬','golden retriever'],
    ['拉布拉多','拉布拉多寻回犬','labrador'],
    ['泰迪','贵宾犬','贵宾','toy poodle','poodle'],
    ['法斗','法国斗牛犬','french bulldog'],
    ['小白狗','小白','小白犬']
  ];
  var COLOR_FILTERS = {
    'white': 'grayscale(100%) brightness(1.1)',
    'cream': 'sepia(0.3) saturate(0.8) brightness(1.05)',
    'light-brown': 'sepia(0.5) saturate(1.2)',
    'dark-brown': 'sepia(0.7) saturate(1.3) brightness(0.9)',
    'black': 'grayscale(100%) brightness(0.3) contrast(1.2)',
    'gray': 'grayscale(100%) brightness(0.7)'
  };

  function findBreed(text) {
    if (!text) return null;
    var t = text.toLowerCase();
    for (var key in BREEDS) {
      if (t.indexOf(key) >= 0) return { key: key, breed: BREEDS[key] };
    }
    for (var i = 0; i < BREED_ALIASES.length; i++) {
      var aliases = BREED_ALIASES[i];
      for (var j = 0; j < aliases.length; j++) {
        if (t.indexOf(aliases[j]) >= 0) {
          var k = Object.keys(BREEDS)[i] || key;
          return { key: k, breed: BREEDS[k] };
        }
      }
    }
    return null;
  }

  function findColor(text) {
    if (!text) return null;
    var t = text.toLowerCase();
    if (/白|白的/.test(t)) return 'white';
    if (/奶油|奶油色/.test(t)) return 'cream';
    if (/浅棕|淡棕/.test(t)) return 'light-brown';
    if (/深棕|黑棕/.test(t)) return 'dark-brown';
    if (/黑色|黑的/.test(t)) return 'black';
    if (/灰色|灰的/.test(t)) return 'gray';
    return null;
  }

  function applyBreedImage(imgEl, breedKey, colorKey) {
    if (!imgEl) return;
    if (breedKey && BREEDS[breedKey]) {
      imgEl.src = BREEDS[breedKey].image;
    }
    if (colorKey && COLOR_FILTERS[colorKey]) {
      imgEl.style.filter = COLOR_FILTERS[colorKey];
    }
  }

  /* ────────────────────────────────────────────────────────────────────
     0. API 配置与工具
     ──────────────────────────────────────────────────────────────────── */
  var API_BASE = 'http://localhost:8001/api/v1';
  var currentPetId = null;  // 后端 Pet ID

  // 异步 POST，不阻塞 UI，失败静默（离线优先）
  function apiPost(endpoint, data) {
    if (!currentPetId && endpoint.indexOf('pets') === -1) return;
    var url = API_BASE + endpoint.replace('{pet_id}', currentPetId);
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    }).catch(function(){}); // 离线时静默失败
  }

  // 异步 GET
  function apiGet(endpoint) {
    return fetch(API_BASE + endpoint.replace('{pet_id}', currentPetId))
      .then(function(r){ return r.json(); })
      .catch(function(){});
  }

  // 上传图片到后端
  function uploadImage(file) {
    return new Promise(function(resolve) {
      var formData = new FormData();
      formData.append('file', file);
      fetch(API_BASE + '/upload-image', { method: 'POST', body: formData })
        .then(function(r){ return r.json(); })
        .then(function(data){ resolve(data.url || null); })
        .catch(function(){ resolve(null); });
    });
  }

  // 创建后端 Pet 档案
  function createPet(name, avatarUrl, breed, color) {
    var data = { name: name, avatar_url: avatarUrl || null, breed: breed || null, color: color || null };
    return fetch(API_BASE + '/pets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    .then(function(r){ return r.json(); })
    .then(function(pet){
      if (pet && pet.id) {
        currentPetId = pet.id;
        S.backendPetId = pet.id;
        save();
      }
      return pet;
    })
    .catch(function(){ return null; });
  }

  // 同步记忆到后端
  function syncMemory(sceneId, text, priority, mediaUrl) {
    if (!currentPetId) return;
    var memoryTypes = ['first_sight','funny_eating','departure_reaction','protection','protected_by_owner','wonderful_moment'];
    var type = sceneId === 's1' ? 'first_sight' : sceneId === 's2' ? 'funny_eating' : 'wonderful_moment';
    apiPost('/pets/{pet_id}/memories', {
      memory_type: type,
      title: text.slice(0, 20),
      content: text,
      media_url: mediaUrl || null,
      priority: priority || 1
    });
  }

  // 同步相遇故事
  function syncMeetingStory(text) {
    if (!currentPetId) return;
    apiPost('/pets/{pet_id}/meeting-story', { story: text });
  }

  // 初始化后端数据（3条测试记忆）
  function initTestData() {
    if (currentPetId) return;
    // 先创建 Pet
    fetch(API_BASE + '/pets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: '年糕', breed: '柯基', color: '黄白' })
    })
    .then(function(r){ return r.json(); })
    .then(function(pet){
      if (!pet || !pet.id) return;
      currentPetId = pet.id;
      S.backendPetId = pet.id;
      save();

      // 添加3条测试记忆
      var memories = [
        { memory_type: 'first_sight', title: '第一次见面', content: '是在楼下的纸箱里捡到的，那天下着雨，它一直躲着不出来，特别胆小。' },
        { memory_type: 'funny_eating', title: '吃饭的习惯', content: '吃饭之前一定要转两圈，特别贪吃。每次听到狗粮袋子的声音就兴奋得不行。' },
        { memory_type: 'wonderful_moment', title: '等你回家', content: '它每天都会在门口等我，看到我回来就摇尾巴，什么都没有说，就一直摇。' }
      ];
      memories.forEach(function(m) {
        fetch(API_BASE + '/pets/' + pet.id + '/memories', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(m)
        }).catch(function(){});
      });

      // 相遇故事
      fetch(API_BASE + '/pets/' + pet.id + '/meeting-story', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ story: '是在楼下的纸箱里捡到的，那天下着雨，它一直躲着不出来，特别胆小。' })
      }).catch(function(){});
    })
    .catch(function(){});
  }

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var pick = function (a) { return a[Math.floor(Math.random() * a.length)]; };
  var stage = $('#stage');

  /* ────────────────────────────────────────────────────────────────────
     1. 状态（对应 PRD §7 数据与状态）
     ──────────────────────────────────────────────────────────────────── */
  var KEY = 'memoryhome.guest.v1';   // Guest Session：当前设备永久保存

  var S = {
    scene: 'intro',
    petName: '',
    hasPhoto: false,
    detail: 0,                      // 形象清晰度 0–1，信息不足即保持低细节 Base 形象
    memories: [],                   // MemoryItem
    pawMarks: [],                   // PawMark
    profile: {                      // CharacterProfile（安全、可 grounding 的部分）
      place: '', traits: [], objects: [], habits: [], precious: '', breed: '', color: ''
    },
    story: {                        // StoryState：唯一活跃的想象性剧情
      scene: 'home', beat: 0, petState: 'idle', used: [], mood: '灯还亮着'
    },
    backendPetId: null              // 后端 Pet ID
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
      currentPetId = S.backendPetId || null;
      return true;
    } catch (e) { return false; }
  }
  function reset() {
    try { localStorage.removeItem(KEY); } catch (e) {}
    location.reload();
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
    // 异步同步到后端
    syncMemory(sceneId, text, priority, null);
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
    function start(e) {
      e.preventDefault();
      t0 = Date.now();
      btn.classList.add('is-holding');
      recOverlay.hidden = false;
      $('#recTip').textContent = '松开结束';
    }
    function end() {
      if (!t0) return;
      var dur = Date.now() - t0; t0 = 0;
      btn.classList.remove('is-holding');
      recOverlay.hidden = true;
      if (dur < 550) { label.textContent = '太短了，再按久一点'; return; }
      $('#recTip').textContent = '正在转写…';
      editor(mockASR(opt.asr));
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
    Object.keys(scenes).forEach(function (k) { scenes[k].classList.toggle('is-active', k === name); });
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
      b.addEventListener('click', function () { goto('s1'); }, { once: true });
    }, 7200);
    setTimeout(function () { if (S.scene === 'intro') goto('s1'); }, 11000);
  }
  $('#skipIntro').addEventListener('click', function () { goto('s1'); });

  /* ── 场景 1：门口第一次相遇 ─────────────────────────────────────── */
  var room1 = $('#room1');
  function initS1() {
    if (room1.dataset.ready) return;
    room1.dataset.ready = '1';
    buildTrail($('#trail1'), 6);
    setDetail(0.02);
    var slot1 = $('#pet1');
    slot1.style.left = '25%'; slot1.style.bottom = '43%';   // 先躲在桌子底下

    var n = $('#n1'), a = $('#a1');
    say(n, '<span class="dim">桌子底下有谁，还没有走出来。</span>', 700).then(function () {
      return say(n, '如果愿意，告诉我该怎样叫 TA。', 2600);
    }).then(function () {
      capture(a, {
        asr: 'name', hold: '按住，说出 TA 的名字',
        placeholder: '写下 TA 的名字',
        skip: '还不想说',
        onSkip: function () { a.innerHTML = ''; askPhoto(); },
        onDone: async function (v) {
          S.petName = v.slice(0, 12);
          addMemory('s1', '名字：' + S.petName, 3);
          litTrail($('#trail1'), 1);
          bumpDetail(0.12);
          var detectedBreed = findBreed(v);
          var detectedColor = findColor(v);
          if (detectedBreed) S.profile.breed = detectedBreed.key;
          if (detectedColor) S.profile.color = detectedColor;
          save();
          await createPet(S.petName, null, detectedBreed ? detectedBreed.key : null, detectedColor);
          syncMeetingStory('用户名为：' + S.petName + '的宠物的相遇故事');
          // 应用品种图到所有宠物形象
          var breedKey = detectedBreed ? detectedBreed.key : null;
          $$('.pet').forEach(function(img){ applyBreedImage(img, breedKey, detectedColor); });
          say(n, '「<em>' + S.petName + '</em>」。这个名字在屋子里亮了一下。').then(askPhoto);
        }
      });
    });

    function askPhoto() {
      say(n, '<span class="dim">要不要放一张 TA 的照片？轮廓会更像一点。</span>', 600).then(function () {
        a.innerHTML = '';
        var col = document.createElement('div');
        col.className = 'slot';
        var lab = document.createElement('label');
        lab.className = 'primary-btn';
        lab.style.display = 'inline-flex';
        lab.style.alignItems = 'center';
        lab.style.gap = '8px';
        lab.innerHTML = '<svg viewBox="0 0 24 24" width="17" height="17" style="stroke:currentColor;fill:none"><use href="#camera"></use></svg><span>放一张 TA 的照片</span>';
        var inp = document.createElement('input');
        inp.type = 'file'; inp.accept = 'image/*'; inp.hidden = true;
        lab.appendChild(inp);
        var skip = document.createElement('button');
        skip.type = 'button'; skip.className = 'ghost-btn'; skip.textContent = '以后再说';
        col.appendChild(lab); col.appendChild(skip);
        a.appendChild(col);

        inp.addEventListener('change', function () {
          if (!inp.files || !inp.files[0]) return;
          S.hasPhoto = true; bumpDetail(0.2); save();
          // 上传到后端
          uploadImage(inp.files[0]);
          a.innerHTML = '';
          askMeet('<span class="dim">照片收下了。毛色和耳朵慢慢对上了。</span>');
        });
        skip.addEventListener('click', function () {
          a.innerHTML = '';
          askMeet('<span class="dim">没关系，先这样。</span>');
        });
      });
    }

    function askMeet(pre) {
      say(n, pre).then(function () {
        return say(n, '第一次见到 TA，是在什么地方？', 1800);
      }).then(function () {
        capture(a, {
          asr: 'meet', hold: '按住，讲第一次见面',
          placeholder: '第一次见到 TA 的时候…',
          onDone: function (v) {
            var m = addMemory('s1', v, 2);
            addPaw('s1', '第一次见面', m.id);
            syncMeetingStory(v);
            worldPatch1();
          }
        });
      });
    }

    // 世界变化代替确认文案：说完之后，物件和路径立刻长出来
    function worldPatch1() {
      say(n, '<span class="dim">房间跟着你说的话，一点点长出来。</span>');
      var objs = $$('.obj', room1);
      objs.forEach(function (o, i) {
        setTimeout(function () { o.classList.remove('is-off'); }, 500 + i * 700);
      });
      setTimeout(function () { litTrail($('#trail1'), 3); }, 1600);
      setTimeout(function () {
        var slot = $('#pet1');
        slot.style.left = '52%';
        slot.style.bottom = '44%';
        $('.pet', slot).src = POSE.approach;
        bumpDetail(0.22);
      }, 2400);
      setTimeout(function () {
        var extra = S.profile.place ? '在<em>' + S.profile.place + '</em>' : '在那里';
        say($('#n1'), '轮廓比刚才清楚了一些。' + (S.petName ? S.petName : 'TA') + '从桌子底下探出头。');
        actionButton($('#a1'), '跟上去', function () { goto('s2'); });
      }, 4200);
    }
  }

  /* ── 场景 2：普通的一天 ─────────────────────────────────────────── */
  var room2 = $('#room2');
  var TOUCH = {
    window: { pos: [15, 45], pose: 'idle',     line: '阳光正好落在窗边那块地板上，TA 走过去趴下，尾巴慢慢摆了两下。', mem: '喜欢在窗边晒太阳', tag: '窗边的太阳' },
    bowl:   { pos: [31, 42], pose: 'happy',    line: '饭盆一响，TA 立刻转了两圈，急得原地打转。', mem: '吃饭前会转圈，很贪吃', tag: '饭盆响了', anim: 'bounce' },
    keys:   { pos: [60, 43], pose: 'run',      line: '钥匙响了。TA 冲过去，脚下打滑，还是先到了门口。', mem: '听到钥匙声会冲到门口', tag: '钥匙的声音', anim: 'run' },
    sofa:   { pos: [73, 51], pose: 'down',     line: '沙发那头有一个凹下去的位置，刚好是 TA 的形状。', mem: '常待在沙发一角', tag: '沙发的角落' },
    leash:  { pos: [46, 45], pose: 'happy',    line: '牵引绳晃了一下，TA 抬起头，一直看着它。', mem: '看到牵引绳就想出门', tag: '牵引绳', anim: 'bounce' },
    bed:    { pos: [42, 41], pose: 'down',     line: '床边留着一小块空位。夜里安静下来的时候，那里最软。', mem: '夜里睡在床边', tag: '床边的位置' }
  };
  var touched = 0;

  function initS2() {
    if (room2.dataset.ready) return;
    room2.dataset.ready = '1';
    buildTrail($('#trail2'), 8);
    litTrail($('#trail2'), 3);
    $('.pet', $('#pet2')).src = POSE.idle;

    var order = ['window', 'bowl', 'keys', 'sofa', 'leash', 'bed'];
    order.forEach(function (k, i) {
      var el = $('[data-touch="' + k + '"]', room2);
      el.classList.add('is-off');
      setTimeout(function () { el.classList.remove('is-off'); }, 400 + i * 900);
    });

    var n = $('#n2'), a = $('#a2');
    say(n, '<span class="dim">早晨的光从窗户进来。今天和从前的每一天一样。</span>', 600);

    $$('[data-touch]', room2).forEach(function (el) {
      var k = el.dataset.touch;
      var fire = function () { onTouch(k, el); };
      el.addEventListener('click', fire);
      el.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fire(); }
      });
    });

    function onTouch(key, el) {
      if (el.classList.contains('is-done')) return;
      var t = TOUCH[key];
      el.classList.add('is-done', 'is-active');
      setTimeout(function () { el.classList.remove('is-active'); }, 1600);
      $('#touchHint').classList.add('is-hidden');

      var slot = $('#pet2');
      slot.classList.toggle('face-left', t.pos[0] < parseFloat(slot.style.left || '50'));
      slot.style.left = t.pos[0] + '%';
      slot.style.bottom = t.pos[1] + '%';
      $('.pet', slot).src = POSE[t.pose];
      if (t.anim) {
        slot.classList.add(t.anim === 'run' ? 'is-running' : 'is-bouncing');
        setTimeout(function () { slot.classList.remove('is-running', 'is-bouncing'); }, 2000);
      }

      var m = addMemory('s2', t.mem, 1);
      addPaw('s2', t.tag, m.id);
      if (S.profile.objects.indexOf(key) < 0) S.profile.objects.push(key);
      if (S.profile.habits.indexOf(t.mem) < 0) S.profile.habits.push(t.mem);
      save();

      touched++;
      litTrail($('#trail2'), 3 + touched);
      room2.dataset.time = touched >= 5 ? 'night' : touched >= 3 ? 'dusk' : '';
      tintDock();
      say(n, withName(t.line));

      if (touched === 3) setTimeout(askDay, 2600);
      if (touched >= 4) setTimeout(offerNext, 2600);
    }

    function tintDock() {
      var t = room2.dataset.time;
      scenes.s2.style.setProperty('--dock-tint',
        t === 'night' ? '188,168,142' : t === 'dusk' ? '226,207,176' : '241,226,199');
    }

    function askDay() {
      say(n, withName('<span class="dim">TA 普通的一天，还会做什么？</span>'), 400)
        .then(function () {
          capture(a, {
            asr: 'day', hold: '按住，说说这一天',
            placeholder: '早上、白天、晚上…',
            skip: '再碰碰别的',
            onSkip: function () { a.innerHTML = ''; },
            onDone: function (v) {
              var m = addMemory('s2', v, 2);
              addPaw('s2', '普通的一天', m.id);
              litTrail($('#trail2'), 8);
              say(n, '<span class="dim">屋子记下了这些。天色晚了一点。</span>');
              room2.dataset.time = 'dusk'; tintDock();
              setTimeout(offerNext, 2000);
            }
          });
        });
    }

    function offerNext() {
      if ($('.paw-btn', a) || $('.field', a)) return;
      say(n, '<span class="dim">灯一盏一盏灭了。有几枚脚印还亮着。</span>');
      room2.dataset.time = 'night'; tintDock();
      actionButton(a, '往前走', function () { goto('s3'); });
    }
  }

  /* ── 场景 3：留下最不想失去的记忆 ───────────────────────────────── */
  function initS3() {
    var field = $('#pawField');
    if (field.dataset.ready) return;
    field.dataset.ready = '1';

    var n = $('#n3'), a = $('#a3');
    var p3 = $('#pet3');
    p3.style.left = '76%'; p3.style.bottom = '36%'; p3.classList.add('face-left');
    var marks = S.pawMarks.slice(-6);
    if (!marks.length) marks = [{ id: 'p0', label: '还没有名字的一天' }];
    var spots = [[13, 11], [48, 7], [25, 27], [58, 24], [16, 43], [45, 41]];

    marks.forEach(function (mk, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'paw-choice';
      b.style.left = spots[i % spots.length][0] + '%';
      b.style.top = spots[i % spots.length][1] + '%';
      b.innerHTML = '<svg viewBox="0 0 26 26"><use href="#paw"></use></svg><span class="tag">' + mk.label + '</span>';
      b.style.animationDelay = (i * 0.2) + 's';
      b.addEventListener('click', function () { choose(b, mk); });
      field.appendChild(b);
    });

    say(n, '<span class="dim">今天走过的地方，都还留着。</span>', 600).then(function () {
      return say(n, '选一枚，把最不想弄丢的那一段留在这里。', 2400);
    });

    var chosen = false;
    function choose(btn, mk) {
      if (chosen) return;
      chosen = true;
      $$('.paw-choice', field).forEach(function (o) { if (o !== btn) o.classList.add('is-dimmed'); });
      btn.classList.add('is-chosen');
      say(n, '就是这一枚。<span class="dim">' + mk.label + '。</span>').then(function () {
        capture(a, {
          asr: 'keep', hold: '按住，把它说完整',
          placeholder: '那一次…',
          onDone: function (v) {
            var m = addMemory('s3', v, 3);           // 高优先级，聊天优先使用
            S.profile.precious = SENSITIVE.test(v) ? '' : v;
            btn.classList.add('is-kept');
            bumpDetail(0.3);
            save();
            say(n, '这一枚会一直亮着。<span class="dim">往后每次回来，先经过它。</span>');
            setTimeout(function () { actionButton(a, '回家', function () { goto('weave'); }); }, 1600);
          }
        });
      });
    }
  }

  /* ── 家园生成 ───────────────────────────────────────────────────── */
  function initWeave() {
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
    setTimeout(function () { if (S.scene === 'weave') goto('companion'); }, 7400);
  }

  /* ────────────────────────────────────────────────────────────────────
     5. Companion：想象性陪伴叙事
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
  function scrollEnd() { thread.scrollTop = thread.scrollHeight; }

  function typing() {
    var t = document.createElement('div');
    t.className = 'typing';
    t.innerHTML = '<i></i><i></i><i></i>';
    thread.appendChild(t); scrollEnd();
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
    thread.appendChild(box); scrollEnd();

    box.appendChild(line('line-env', beat.env)); scrollEnd();
    await sleep(750);
    setPose(beat.pose);
    box.appendChild(line('line-act', beat.act.replace(/\{n\}/g, N()))); scrollEnd();
    await sleep(850);
    box.appendChild(line('line-say', beat.say)); scrollEnd();
    await sleep(650);
    box.appendChild(line('line-push', withName(beat.push))); scrollEnd();

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

    var me = line('line-me', text);
    thread.appendChild(me); scrollEnd();

    // 情绪保护：强烈痛苦时温和陪伴，并提示联系信任的人或专业支持
    if (DISTRESS.test(text)) {
      var t1 = typing(); await sleep(900); t1.remove();
      var b1 = document.createElement('div'); b1.className = 'beat'; thread.appendChild(b1);
      b1.appendChild(line('line-act', N() + '没有动，只是把头靠过来，靠在你手边。'));
      await sleep(700);
      b1.appendChild(line('line-say', '不用说了。我在这儿，你想坐多久都行。'));
      await sleep(600);
      b1.appendChild(line('line-soft', '如果心里太沉，也可以和你信任的人说说，或者找专业的支持聊一聊。'));
      scrollEnd(); busy = false; save(); return;
    }

    // 自然纠正：进入后台候选修正，不直接覆盖既有 Memory
    if (/^(不是|不对|它不会|TA不会|他不会|她不会|没有)/.test(text)) {
      var t2 = typing(); await sleep(800); t2.remove();
      var b2 = document.createElement('div'); b2.className = 'beat'; thread.appendChild(b2);
      b2.appendChild(line('line-act', N() + '歪了一下头，像是在等你把话说完。'));
      await sleep(600);
      b2.appendChild(line('line-say', '嗯，那我记住这个。'));
      scrollEnd();
      S.story.threads = (S.story.threads || []).concat([{ type: 'correction', rawText: text, confirmed: false }]);
      save(); busy = false;
      return;
    }

    interpret(text);

    // 调用后端 LLM 生成回复
    var t3 = typing();
    var llmReply = null;
    if (currentPetId) {
      try {
        var res = await fetch(API_BASE + '/pets/' + currentPetId + '/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text })
        });
        if (res.ok) {
          var data = await res.json();
          llmReply = data.content;
        }
      } catch(e) {}
    }
    t3.remove();

    var b3 = document.createElement('div'); b3.className = 'beat'; thread.appendChild(b3);
    if (llmReply) {
      // LLM 返回的回复（已包含动作/对白混合，需要解析）
      // 尝试解析：如果是纯对白，加上默认动作描述
      var isPetAction = /^[汪呜摇尾舔趴躺跑跳]|^[它TA]/.test(llmReply);
      b3.appendChild(line('line-act', N() + '看着你，耳朵轻轻动了一下。'));
      await sleep(600);
      b3.appendChild(line('line-say', llmReply));
    } else {
      // 回退到 Mock
      var reacts = [
        { act: N() + '抬头看着你，尾巴在地板上扫了两下。', say: '好呀。你说什么我都听。' },
        { act: N() + '往你这边挪了挪，整个身子贴上来。', say: '我在听，你继续说。' },
        { act: N() + '把爪子搭在你腿上，眼睛一直没离开。', say: '嗯，然后呢？' }
      ];
      var r = pick(reacts);
      b3.appendChild(line('line-act', r.act));
      await sleep(650);
      b3.appendChild(line('line-say', r.say));
    }
    scrollEnd();
    busy = false; save();
    setTimeout(function () { if (!busy) playBeat(nextBeat()); }, 1400);
  }

  function initCompanion() {
    setDetail(Math.max(S.detail, 0.72));   // Memory 不足也不阻塞，使用低细节 Base 形象
    $('#cName').textContent = S.petName ? S.petName + '的家' : '家';
    $('#cSub').textContent = S.story.mood;
    $('.pet', petC).src = POSE[S.story.petState] || POSE.idle;

    // 固定 Base 家园背景，只替换少量安全元素
    ['window', 'mailbox'].forEach(function (k) { $('[data-safe="' + k + '"]').classList.add('is-on'); });
    if (S.profile.objects.indexOf('bowl') >= 0) $('[data-safe="bowl"]').classList.add('is-on');
    if (S.profile.objects.indexOf('球') >= 0 || S.profile.objects.indexOf('玩具') >= 0)
      $('[data-safe="ball"]').classList.add('is-on');

    if (thread.dataset.ready) return;
    thread.dataset.ready = '1';

    if (!thread.childElementCount) {
      var open = document.createElement('p');
      open.className = 'line line-soft';
      open.textContent = S.petName ? '门开着，灯是亮的。' : '门开着，灯是亮的。名字还没有说出口也没关系。';
      thread.appendChild(open);
      setTimeout(function () { playBeat(nextBeat()); }, 900);   // 首次自动开场
    }
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
    intro: initIntro, s1: initS1, s2: initS2, s3: initS3,
    weave: initWeave, companion: initCompanion
  };

  var jump = { '1': 'intro', '2': 's1', '3': 's2', '4': 's3', '5': 'companion' };
  document.addEventListener('keydown', function (e) {
    if (e.target && e.target.matches && e.target.matches('input, textarea')) return;
    if (jump[e.key]) goto(jump[e.key]);
    if (e.key === 'r' || e.key === 'R') reset();
  });

  window.__mh = { S: S, goto: goto, reset: reset, addMemory: addMemory, addPaw: addPaw, createPet: createPet, initTestData: initTestData };  // 调试用

  var resumed = load();
  setDetail(S.detail);

  goto(resumed && S.scene === 'companion' ? 'companion' : 'intro');
})();
