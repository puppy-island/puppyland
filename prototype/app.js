/* ==========================================================================
   记忆家园 Memory Home — 前端原型逻辑
   对应 PRD v2.1：场景驱动采集 → 后台记忆整理 → 唯一 Companion 叙事陪伴

   ASR：腾讯云 asr/v2 WebSocket（后端签名，前端直连）
   AI：FastAPI 后端 LLM（DeepSeek / Qwen）
   ========================================================================== */
(function () {
  'use strict';

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var pick = function (a) { return a[Math.floor(Math.random() * a.length)]; };
  var stage = $('#stage');
  var REVIEW_MODE = new URLSearchParams(location.search).has('reviewScene');

  /* ────────────────────────────────────────────────────────────────────
     1. 状态（对应 PRD §7 数据与状态）
     ──────────────────────────────────────────────────────────────────── */
  var KEY = 'memoryhome.guest.v1';   // Guest Session：当前设备永久保存
  // 后端地址可通过 window.MEMORY_HOME_API 覆盖；本地开发默认 FastAPI 端口 8000。
  var API_BASE = (window.MEMORY_HOME_API || 'http://localhost:8000/api/v1').replace(/\/$/, '');
  var API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '');

  var S = {
    scene: 'journey',
    petName: '',
    hasPhoto: false,
    generatedDogImage: null,   // AI生成的狗狗形象（base64，无data URI前缀）
    generatingDogImage: false, // 是否有生成请求正在进行中
    dogGenController: null,    // 当前AI生成请求的AbortController，用于取消旧请求
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
    if (REVIEW_MODE) return;
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
      if (typeof S.generatedDogImage === 'undefined') S.generatedDogImage = null;
      if (typeof S.generatingDogImage === 'undefined') S.generatingDogImage = false;
      S.dogGenController = null;
      S._retryTimer = null;
      return true;
    } catch (e) { return false; }
  }
  function reset() {
    try { localStorage.removeItem(KEY); } catch (e) {}
    location.reload();
  }

  function apiRequest(path, options) {
    options = options || {};
    var externalSignal = options.signal || null;
    var controller = null;
    var timer = null;
    if (!externalSignal && window.AbortController) {
      controller = new AbortController();
      timer = setTimeout(function () { controller.abort(); }, options.timeout || 8000);
    }
    var headers = options.headers || {};
    if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    var req = Object.assign({}, options, { headers: headers });
    if (externalSignal) req.signal = externalSignal;
    else if (controller) req.signal = controller.signal;
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

  async function syncPetPhoto(file, base64DataUrl) {
    if (!file) return null;
    try {
      var form = new FormData(); form.append('file', file);
      var uploaded = await apiRequest('/upload-image', { method: 'POST', body: form, timeout: 12000 });
      var url = publicAssetUrl(uploaded.url);
      if (S.backendPetId) {
        await apiRequest('/pets/' + S.backendPetId, { method: 'PUT', body: JSON.stringify({ avatar_url: url }) });
      }
      S.journey.petReferenceImage = url;
      S.journey.petReferenceImageBase64 = base64DataUrl || null;
      save();
      return url;
    } catch (e) { return null; }
  }

  // 触发AI生成狗狗形象图片
  async function triggerDogImageGeneration() {
    // 清除上一次abort后设置的retry timer，避免与新请求竞争
    if (S._retryTimer) { clearTimeout(S._retryTimer); S._retryTimer = null; }
    // 如果已有旧请求在进行中，abort掉（建立新宠物时会触发）
    if (S.dogGenController) {
      S.dogGenController.abort();
      S.dogGenController = null;
      S.generatingDogImage = false;
      console.log('[triggerDogImageGeneration] 终止了旧请求，开始新请求');
    }
    // 防止重复并发请求
    if (S.generatingDogImage) {
      console.log('[triggerDogImageGeneration] 已有生成请求在进行中，跳过此次调用');
      return;
    }
    S.generatingDogImage = true;
    // 创建新的AbortController供apiRequest使用
    var controller = new AbortController();
    S.dogGenController = controller;
    save();
    try {
      var payload = {
        voice_description: S.journey.voiceDescription || '',
        has_uploaded_photo: !!S.journey.petReferenceImage,
        uploaded_photo_base64: null
      };
      // 如果有上传照片，直接使用已存储的base64（无需再走HTTP fetch）
      if (payload.has_uploaded_photo && S.journey.petReferenceImageBase64) {
        try {
          payload.uploaded_photo_base64 = S.journey.petReferenceImageBase64.replace(/^data:image\/\w+;base64,/, '');
        } catch (imgErr) {
          payload.has_uploaded_photo = false;
          payload.uploaded_photo_base64 = null;
        }
      } else if (payload.has_uploaded_photo && S.journey.petReferenceImage) {
        // 兜底：走HTTP fetch（可能因跨域失败）
        try {
          var refImg = new Image();
          refImg.crossOrigin = 'anonymous';
          await new Promise(function (res, rej) {
            refImg.onload = res; refImg.onerror = rej;
            refImg.src = S.journey.petReferenceImage;
          });
          var canvas = document.createElement('canvas');
          canvas.width = refImg.naturalWidth || refImg.width;
          canvas.height = refImg.naturalHeight || refImg.height;
          var ctx = canvas.getContext('2d');
          ctx.drawImage(refImg, 0, 0);
          var dataUrl = canvas.toDataURL('image/png');
          payload.uploaded_photo_base64 = dataUrl.replace(/^data:image\/\w+;base64,/, '');
        } catch (imgErr) {
          payload.has_uploaded_photo = false;
          payload.uploaded_photo_base64 = null;
        }
      }
      var result = await apiRequest('/generate-dog-image', {
        method: 'POST',
        body: JSON.stringify(payload),
        signal: controller.signal
      });
      console.log('[triggerDogImageGeneration] result:', JSON.stringify(result).substring(0, 200));
      S.dogGenController = null;
      if (result && result.success && result.image_base64) {
        S.generatedDogImage = result.image_base64;
        S.generatingDogImage = false;
        save();
        console.log('[triggerDogImageGeneration] 狗狗图片已生成并保存，长度:', result.image_base64.length);
        // 图片生成后如果当前在home场景，立即显示
        if (S.scene === 'home') {
          var homePetEl = $('#homePet');
          if (homePetEl) {
            var existingImg = homePetEl.querySelector('.generated-dog-img');
            if (existingImg) existingImg.remove();
            var img = document.createElement('img');
            img.className = 'generated-dog-img';
            img.src = 'data:image/png;base64,' + S.generatedDogImage;
            img.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;pointer-events:none;';
            homePetEl.style.position = 'relative';
            homePetEl.appendChild(img);
          }
        }
      } else if (result) {
        S.generatingDogImage = false;
        save();
        console.warn('[triggerDogImageGeneration] 生成失败:', result.message, 'breeds:', result.breed_names);
        // 如果服务端返回可重试标志，等待后重试
        if (result.retryable) {
          console.log('[triggerDogImageGeneration] 服务端提示可重试，5秒后重试...');
          var retryTimer = setTimeout(function () { triggerDogImageGeneration(); }, 5000);
          S._retryTimer = retryTimer;
        }
      }
    } catch (e) {
      console.error('[triggerDogImageGeneration] 请求异常:', e.message);
      S.dogGenController = null;
      S.generatingDogImage = false;
      save();
      // 网络中断或页面跳转导致，重试一次
      if (e.message && e.message.includes('aborted')) {
        console.log('[triggerDogImageGeneration] 请求被中断，2秒后重试...');
        var retryTimer = setTimeout(function () { triggerDogImageGeneration(); }, 2000);
        S._retryTimer = retryTimer;
      }
    }
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

  // LLM 剧情生成：根据宠物档案 + 记忆动态生成下一幕（环境/动作/对白/推进语/姿态）
  var ALLOWED_POSE = { idle: 1, approach: 1, happy: 1, run: 1, down: 1, sleep: 1 };
  async function backendGenerateBeat() {
    if (!S.backendPetId) return null;
    try {
      var beat = await apiRequest('/pets/' + S.backendPetId + '/generate-beat', {
        method: 'POST',
        body: JSON.stringify({ previous_beat: S.story.lastEnv || null }),
        timeout: 12000
      });
      if (!beat || !beat.env || !beat.act || !beat.say) return null;
      if (!ALLOWED_POSE[beat.pose]) beat.pose = 'idle';
      if (!beat.push) beat.push = '要不要陪陪TA？';
      return beat;
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

  /* ── 引导文案（语音输入时的提示语）────────────────────────────── */
  var GUIDE_TEXT = {
    name: '按住爪子，说说你记忆里的 TA 吧',
    meet: '说说你们第一次见面的情景',
    day: '说一件你和它之间的小事',
    keep: '说说它留给你的最深印象'
  };
  /* ── 腾讯云实时 ASR ──────────────────────────────────────────── */
  function blobToPcm16k(blob) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () {
        var arrayBuffer = reader.result;
        var ctx = new (window.AudioContext || window.webkitAudioContext)();
        ctx.decodeAudioData(arrayBuffer).then(function (audioBuffer) {
          var offlineCtx = new OfflineAudioContext(1, audioBuffer.duration * 16000, 16000);
          var source = offlineCtx.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(offlineCtx.destination);
          source.start(0);
          offlineCtx.startRendering().then(function (renderedBuffer) {
            var f32 = renderedBuffer.getChannelData(0);
            var pcm = new DataView(new ArrayBuffer(f32.length * 2));
            for (var i = 0; i < f32.length; i++) {
              pcm.setInt16(i * 2, f32[i] * 0x7fff, true);
            }
            resolve(pcm.buffer);
            ctx.close();
          }).catch(reject);
        }).catch(reject);
      };
      reader.onerror = reject;
      reader.readAsArrayBuffer(blob);
    });
  }

  function recognizeByTencentASR(audioBlob, onResult, onError) {
    var CHUNK = 6400; // 200ms @ 16kHz/16bit

    Promise.all([
      apiRequest('/asr?' + Date.now(), { timeout: 10000 }),
      blobToPcm16k(audioBlob)
    ]).then(function (res) {
      var data = res[0], pcm = res[1];
      if (!data.url) { onError('获取ASR连接失败，请检查网络'); return; }
      var ws = new WebSocket(data.url);
      var off = 0;
      var uploaded = false;
      var settled = false;
      var latestText = '';
      function fail(msg) {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        try { ws.close(); } catch (e) {}
        onError(msg);
      }
      var uploadMs = (pcm.byteLength / 6400) * 200;
      var timeout = setTimeout(function () { fail('ASR识别超时'); }, Math.max(uploadMs + 8000, 15000));

      ws.onopen = function () {
        function push() {
          if (!ws || ws.readyState !== WebSocket.OPEN) return;
          if (off >= pcm.byteLength) {
            if (!uploaded) { uploaded = true; ws.send(JSON.stringify({ type: 'end' })); }
            return;
          }
          ws.send(pcm.slice(off, Math.min(off + CHUNK, pcm.byteLength)));
          off += CHUNK;
          setTimeout(push, 200);
        }
        push();
      };

      ws.onmessage = function (e) {
        if (typeof e.data !== 'string') return;
        try {
          var msg = JSON.parse(e.data);
          if (msg.code !== 0 && msg.code !== undefined) {
            fail(msg.message || 'ASR识别失败'); return;
          }
          var r = msg.result;
          // 腾讯云 asr/v2 每条 result.voice_text_str 是该切片序号之前的完整累积文本
          // 直接使用最新一条即可，无需数组合并
          if (r && typeof r.voice_text_str === 'string' && r.voice_text_str) {
            latestText = r.voice_text_str;
            var isFinal = !!(msg.final === 1 || r.slice_type === 2);
            onResult(r.voice_text_str, isFinal);
          }
          if (msg.final === 1 || r && r.slice_type === 2) {
            if (!latestText) { fail('没有识别到内容'); return; }
            if (!(r && r.voice_text_str)) onResult(latestText, true);
            settled = true;
            clearTimeout(timeout); try { ws.close(); } catch(e) {}
          }
        } catch(err) {}
      };

      ws.onerror = function () { fail('ASR连接失败'); };
      ws.onclose = function () {
        if (!settled) fail('没有识别到内容');
        else clearTimeout(timeout);
      };
    }).catch(function (err) { onError('音频处理失败: ' + err.message); });
  }

  /* 从文本提取宠物信息（正则 + LLM） */
  function extractPetInfo(text) {
    return apiRequest('/extract-pet-info?text=' + encodeURIComponent(text), { timeout: 15000 })
      .catch(function () { return { extracted_name: null, breed: null, color: null, personality_traits: [], key_objects: [], habits: [] }; });
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
      $('#recTip').textContent = '';
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
    Object.keys(scenes).forEach(function (k) {
      var isTarget = k === name;
      scenes[k].classList.toggle('is-active', isTarget);
      scenes[k].classList.toggle('is-leaving', !isTarget);
    });
    S.scene = name;
    stage.classList.toggle('is-splash', name === 'splash');
    if (name !== 'splash') save();
    if (SCENE_INIT[name]) SCENE_INIT[name]();
  }

  var startupDestination = 'journey';
  function initSplash() {
    var splash = scenes.splash;
    if (splash.dataset.ready) return;
    splash.dataset.ready = '1';
    setTimeout(function () {
      if (S.scene === 'splash') goto(startupDestination);
    }, 2400);
  }

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
  var journeyTitle = $('#journeyTitle');
  var journeyCopy = $('#journeyCopy');
  var journeyVoiceExample = $('#journeyVoiceExample');
  var journeyVoiceHint = $('#journeyVoiceHint');
  var journeyVoiceQuote = $('#journeyVoiceQuote');
  var journeyCreator = $('#journeyCreator');
  var journeyConfirm = $('#journeyConfirm');
  var journeyTimer = null;
  var voiceTypeTimer = null;
  var voiceTypeToken = 0;
  var rainbowGroupTimer = null;
  var rainbowExitTimer = null;
  var quoteTimer = null;
  var quoteIndex = 0;
  var VOICE_QUOTES = ['可乐是一只灰色泰迪', '它平时特别横，楼下有狗经过就要站在窗户那儿叫', '但其实胆子巨小，最怕打雷', '一响就往我两条腿中间钻，屁股朝外', '我笑它：刚刚不是还很厉害吗'];

  function startVoiceQuoteCarousel() {
    clearInterval(quoteTimer);
    quoteIndex = 0;
    journeyVoiceQuote.textContent = VOICE_QUOTES[quoteIndex] + '\n' + VOICE_QUOTES[(quoteIndex + 1) % VOICE_QUOTES.length];
    quoteTimer = setInterval(function () {
      journeyVoiceQuote.classList.add('is-fading');
      setTimeout(function () {
        quoteIndex = (quoteIndex + 2) % VOICE_QUOTES.length;
        journeyVoiceQuote.textContent = VOICE_QUOTES[quoteIndex] + '\n' + VOICE_QUOTES[(quoteIndex + 1) % VOICE_QUOTES.length];
        journeyVoiceQuote.classList.remove('is-fading');
      }, 350);
    }, 2500);
  }

  function stopVoiceQuoteCarousel() {
    clearInterval(quoteTimer); quoteTimer = null;
    journeyVoiceQuote.textContent = ''; journeyVoiceQuote.classList.remove('is-fading');
  }

  function typeInitialJourneyCopy() {
    clearTimeout(voiceTypeTimer);
    var token = ++voiceTypeToken;
    var title = '我好像……\n记不清自己原来的样子了';
    var copy = '你可以帮我想起来吗？';
    var titleEl = $('#journeyTitle');
    var copyEl = $('#journeyCopy');
    titleEl.classList.add('is-typewriter');
    titleEl.textContent = '';
    copyEl.textContent = '';
    var i = 0;
    function typeTitle() {
      if (token !== voiceTypeToken) return;
      if (i < title.length) {
        titleEl.textContent += title[i++];
        voiceTypeTimer = setTimeout(typeTitle, 95);
        return;
      }
      i = 0;
      voiceTypeTimer = setTimeout(typeCopy, 260);
    }
    function typeCopy() {
      if (token !== voiceTypeToken) return;
      if (i < copy.length) {
        copyEl.textContent += copy[i++];
        voiceTypeTimer = setTimeout(typeCopy, 78);
      } else {
        journeyCreator.hidden = false;
        journeyVoiceHint.hidden = false;
        startVoiceQuoteCarousel();
      }
    }
    typeTitle();
  }

  function renderPhotoPromptTitle() {
    journeyTitle.textContent = '';
    var name = document.createElement('span');
    name.className = 'journey-pet-name';
    name.contentEditable = 'true';
    name.spellcheck = false;
    name.setAttribute('role', 'textbox');
    name.setAttribute('aria-label', '狗狗名字，可编辑');
    name.textContent = S.petName || 'puppy';
    name.addEventListener('input', function () {
      var value = name.textContent.replace(/[\r\n]/g, '').trim();
      if (value) { S.petName = value; save(); }
    });
    name.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') event.preventDefault();
    });
    name.addEventListener('blur', function () {
      if (!name.textContent.trim()) name.textContent = S.petName || 'puppy';
    });
    journeyTitle.appendChild(name);
    journeyTitle.appendChild(document.createElement('br'));
    journeyTitle.appendChild(document.createTextNode('再给我一张照片，也许我会想得更快一点。'));
  }

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
    var creating = S.journey.stage === 'PET_CREATION' || S.journey.stage === 'PHOTO_INPUT';
    host.hidden = false;
    var count = creating ? 7 : 3;
    for (var i = 0; i < count; i++) {
      var paw = document.createElement('span');
      paw.className = 'journey-paw ' + (creating ? 'is-ambient' : (i < S.journey.sceneIndex ? 'is-done' : i === S.journey.sceneIndex ? 'is-current' : ''));
      paw.style.animationDelay = (i * .18).toFixed(2) + 's';
      paw.innerHTML = '<svg viewBox="0 0 26 26" aria-hidden="true"><use href="#paw"></use></svg>';
      host.appendChild(paw);
    }
    var bridge = document.createElement('span');
    bridge.className = 'journey-rainbow-mark';
    bridge.textContent = '✦';
    host.appendChild(bridge);
  }

  function journeyWorldLevel() {
    journeyWorld.dataset.level = String(S.journey.worldLevel || 0);
    var creating = S.journey.stage === 'PET_CREATION' || S.journey.stage === 'PHOTO_INPUT';
    var crossing = S.journey.stage === 'RAINBOW_BRIDGE' || S.journey.stage === 'GROUP_BRIDGE';
    journeyWorld.dataset.sceneIndex = String(S.journey.sceneIndex || 0);
    journeyWorld.dataset.state = creating ? 'creation' : crossing ? 'rainbow' : 'swimming';
    journeyWorld.classList.toggle('is-swimming', !creating);
    journeyCard.dataset.state = creating ? 'creation' : 'story';
    journeyCard.classList.toggle('is-over-water', !creating);
    journeyCard.classList.toggle('is-creating', creating);
    journeyCard.classList.toggle('is-confirming', S.journey.stage === 'PHOTO_INPUT');
    journeyWorld.classList.toggle('is-rainbow', crossing);
    journeyWorld.classList.toggle('is-running', S.journey.stage === 'RUNNING');
  }

  function journeyCardReset() {
    journeyCreator.hidden = true;
    journeyConfirm.hidden = true;
    $('#journeyTitle').classList.remove('is-typewriter');
    journeyVoiceExample.hidden = true;
    journeyVoiceExample.textContent = '';
    journeyVoiceHint.hidden = true;
    stopVoiceQuoteCarousel();
    clearTimeout(voiceTypeTimer);
    voiceTypeToken++;
    // 清除旧版动态编辑控件（兼容已有页面状态）
    var field = journeyCard.querySelector('.field');
    if (field) field.remove();
    var hint = journeyCard.querySelector('p[style*="font-size:13px"]');
    if (hint) hint.remove();
    var slotRow = journeyCard.querySelector('.slot-row');
    if (slotRow) slotRow.remove();
    journeyCard.classList.remove('is-creating');
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
    // 游泳场景后进入静态彩虹桥画面，不直接播放过桥视频。
    S.journey.stage = 'RAINBOW_BRIDGE';
    S.journey.sceneIndex = 2;
    S.journey.petCompletion = 0.72; S.journey.worldLevel = 5; setDetail(0.4);
    journeyCardReset();
    $('#journeyKicker').textContent = '彩虹桥';
    $('#journeyTitle').textContent = (S.petName || 'TA') + '要走过彩虹桥了。';
    $('#journeyCopy').textContent = '你刚才说起的那些记忆，正在前面汇成一束光。';
    var groupVideo = $('#journeyGroupVideo');
    journeyWorld.classList.remove('is-group-crossing');
    try { groupVideo.pause(); groupVideo.currentTime = 0; } catch (e) {}
    journeyWorldLevel(); journeyProgress(); save();
    clearTimeout(journeyTimer); clearTimeout(rainbowGroupTimer); clearTimeout(rainbowExitTimer);
  }

  function beginGeneratingJourney() {
    S.journey.stage = 'RUNNING';
    S.journey.sceneIndex = 0;
    S.journey.currentMemoryIndex = 0;
    S.journey.petCompletion = 0.2;
    S.journey.worldLevel = 1;
    S.journey.generationStartedAt = S.journey.generationStartedAt || Date.now();
    setDetail(0.18);
    journeyWorld.classList.add('is-running');
    journeyCardReset();
    $('#journeyKicker').textContent = '记忆旅程';
    $('#journeyTitle').textContent = (S.petName || 'TA') + '，好像想起来一点了。';
    $('#journeyCopy').textContent = '一个模糊的轮廓正在出现，真正的样子还在慢慢生成。';
    journeyProgress(); journeyWorldLevel(); save();
    clearTimeout(journeyTimer);
    // 触发AI生成狗狗形象（异步，不阻塞主流程），已有请求在进行中则跳过
    if (!S.generatingDogImage) {
      triggerDogImageGeneration();
    }
  }

  function initJourney() {
    if (!journeyWorld.dataset.bound) {
      journeyWorld.dataset.bound = '1';
      journeyWorld.addEventListener('click', function (e) {
        if (S.journey.stage === 'PET_CREATION' || S.journey.stage === 'PHOTO_INPUT') return;
        if (S.journey.stage === 'RAINBOW_BRIDGE') {
          S.journey.stage = 'GROUP_BRIDGE';
          $('#journeyKicker').textContent = '彩虹桥';
          $('#journeyTitle').textContent = '别怕，大家都来陪你了。';
          $('#journeyCopy').textContent = '一起走过这座桥，前面就是新的家。';
          journeyWorld.classList.add('is-group-crossing');
          var groupVideo = $('#journeyGroupVideo');
          try { groupVideo.currentTime = 0; groupVideo.play(); } catch (ignored) {}
          journeyWorldLevel(); journeyProgress(); save();
          clearTimeout(rainbowExitTimer);
          rainbowExitTimer = setTimeout(function () {
            if (S.scene !== 'journey' || S.journey.stage !== 'GROUP_BRIDGE') return;
            S.journey.stage = 'HOME_GENERATING';
            journeyWorld.classList.remove('is-group-crossing');
            goto('weave');
          }, 5000);
          return;
        }
        if (S.journey.stage === 'GROUP_BRIDGE') {
          // 彩虹动画播放期间不响应点击，结束后自动进入家园。
          return;
        }
        if (S.journey.sceneIndex === 0) {
          // 跳过「游泳」画面，直接进入下一个场景（彩虹桥）
          journeyRainbow(); return;
        }
        if (S.journey.sceneIndex === 1) {
          S.journey.sceneIndex = 2; S.journey.stage = 'RAINBOW_BRIDGE'; S.journey.worldLevel = 5; setDetail(1);
          journeyRainbow(); return;
        }
        if (S.journey.sceneIndex === 2) return;
      });
      var editUIShown = false;
      (function () {
        var voiceBtn = $('#journeyVoice');
        var mediaRecorder = null;
        var stream = null;
        var chunks = [];
        var ended = false;
        var starting = false;
        var audioContext = null;
        var analyser = null;
        var monitorTimer = null;
        var quietSince = 0;
        var pauseIndex = 0;

        function stopPauseMonitor() {
          if (monitorTimer) { clearInterval(monitorTimer); monitorTimer = null; }
          if (audioContext) { try { audioContext.close(); } catch (e) {} audioContext = null; }
          analyser = null; quietSince = 0;
          var pause = $('#recPause'); pause.classList.remove('is-visible'); pause.textContent = '';
        }

        function monitorPauses(s) {
          try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioContext.createAnalyser(); analyser.fftSize = 512;
            audioContext.createMediaStreamSource(s).connect(analyser);
            var data = new Uint8Array(analyser.fftSize);
            monitorTimer = setInterval(function () {
              if (!analyser || ended) return;
              analyser.getByteTimeDomainData(data);
              var sum = 0;
              for (var j = 0; j < data.length; j++) { var n = (data[j] - 128) / 128; sum += n * n; }
              var rms = Math.sqrt(sum / data.length);
              if (rms < 0.035) {
                if (!quietSince) quietSince = Date.now();
                if (Date.now() - quietSince >= 3500) {
                  var pause = $('#recPause');
                  pause.textContent = pauseIndex++ % 2 ? '然后呢？' : '嗯……';
                  pause.classList.add('is-visible');
                  quietSince = Date.now();
                }
              } else {
                quietSince = 0;
                $('#recPause').classList.remove('is-visible');
              }
            }, 200);
          } catch (e) {}
        }

        function releaseMic() {
          if (stream) {
            try { stream.getTracks().forEach(function (t) { t.stop(); }); } catch (e) {}
            stream = null;
          }
          stopPauseMonitor();
          if (mediaRecorder) { mediaRecorder = null; }
          voiceBtn.disabled = false;
          starting = false;
        }

        function start(e) {
          e.preventDefault();
          if (starting || mediaRecorder && mediaRecorder.state === 'recording') return;
          if (e.pointerId !== undefined && voiceBtn.setPointerCapture) {
            try { voiceBtn.setPointerCapture(e.pointerId); } catch (ignored) {}
          }
          starting = true;
          chunks = [];
          ended = false;
          editUIShown = false;
          journeyVoiceExample.hidden = true;
          journeyVoiceExample.textContent = '';
          journeyVoiceHint.hidden = true;
          stopVoiceQuoteCarousel();
          voiceBtn.classList.add('is-holding');
          // 记忆旅程录音不显示整屏浮层，仅保留爪子按钮的录音状态。
          recOverlay.hidden = true;
          $('#journeyVoiceLabel').textContent = '正在听…松开结束';

          if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
            ended = true;
            starting = false;
            voiceBtn.classList.remove('is-holding');
            journeyVoiceExample.hidden = true;
            journeyVoiceExample.textContent = '';
            journeyVoiceHint.hidden = false;
            startVoiceQuoteCarousel();
            recOverlay.hidden = true;
            $('#journeyVoiceLabel').textContent = '当前设备不支持录音，请再试一次';
            return;
          }
          navigator.mediaDevices.getUserMedia({ audio: true })
            .then(function (s) {
              starting = false;
              if (ended) { s.getTracks().forEach(function (t) { t.stop(); }); return; }
              stream = s;
              monitorPauses(s);
              var mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm'
                : (MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : 'audio/ogg');
              mediaRecorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
              mediaRecorder.ondataavailable = function (ev) { if (ev.data && ev.data.size > 0) chunks.push(ev.data); };
              mediaRecorder.start();
              voiceBtn.disabled = false;
            })
            .catch(function () {
              ended = true;
              releaseMic();
              voiceBtn.classList.remove('is-holding');
              journeyVoiceExample.hidden = true;
              journeyVoiceExample.textContent = '';
              journeyVoiceHint.hidden = false;
              startVoiceQuoteCarousel();
              $('#journeyVoiceLabel').textContent = '请允许麦克风权限';
              setTimeout(function () { $('#journeyVoiceLabel').textContent = GUIDE_TEXT.name; }, 3000);
            });
        }

        function stop(event) {
          if (ended) { releaseMic(); return; }
          ended = true;
          stopPauseMonitor();

          voiceBtn.classList.remove('is-holding');
          if (event && event.pointerId !== undefined && voiceBtn.releasePointerCapture) {
            try { voiceBtn.releasePointerCapture(event.pointerId); } catch (ignored) {}
          }
          journeyVoiceExample.hidden = true;
          journeyVoiceExample.textContent = '';
          journeyVoiceHint.hidden = true;
          stopVoiceQuoteCarousel();
          recOverlay.hidden = true;

          if (!mediaRecorder || mediaRecorder.state === 'inactive') {
            releaseMic();
            $('#journeyVoiceLabel').textContent = '太短了，再按久一点';
            setTimeout(function () { $('#journeyVoiceLabel').textContent = GUIDE_TEXT.name; }, 2000);
            return;
          }

          var dur = 0; // 不再依赖时长判断，统一处理
          var mimeType = mediaRecorder.mimeType || 'audio/webm';
          mediaRecorder.onstop = function () {
            releaseMic();
            $('#journeyVoiceLabel').textContent = '正在转写…';
            var blob = new Blob(chunks, { type: mimeType });
            if (!blob.size) {
              $('#journeyVoiceLabel').textContent = '没录到声音，再试一次';
              setTimeout(function () { $('#journeyVoiceLabel').textContent = GUIDE_TEXT.name; }, 2000);
              return;
            }
            recognizeByTencentASR(blob, function (text, isFinal) {
              if (!text || !text.trim()) return;
              if (!isFinal) {
                // 中间识别结果不显示，避免在爪子下方出现额外提示。
                return;
              }
              if (editUIShown) return;
              editUIShown = true;
              journeyVoiceExample.hidden = false;
              journeyVoiceExample.textContent = text;
              $('#journeyVoiceLabel').textContent = isFinal ? '想起来一点了…' : '正在听…';
              typeVoiceText(text, function () { processVoiceInput(text); });
            }, function (errMsg) {
              editUIShown = false;
              voiceBtn.disabled = false;
              $('#journeyVoiceLabel').textContent = errMsg + '，请再试一次';
              setTimeout(function () { $('#journeyVoiceLabel').textContent = GUIDE_TEXT.name; }, 3000);
            });
          };

          try { mediaRecorder.stop(); } catch (e) {}
        }

        // 引导提示：告诉用户该说什么
        $('#journeyVoiceLabel').textContent = GUIDE_TEXT.name;
        voiceBtn.addEventListener('pointerdown', start);
        voiceBtn.addEventListener('pointerup', stop);
        voiceBtn.addEventListener('pointercancel', stop);
      })();

      function typeVoiceText(text, done) {
        clearTimeout(voiceTypeTimer);
        var token = ++voiceTypeToken;
        var chars = Array.from(String(text || ''));
        var i = 0;
        journeyVoiceExample.hidden = false;
        journeyVoiceExample.textContent = '';
        function next() {
          if (token !== voiceTypeToken) return;
          if (i >= chars.length) { if (done) done(); return; }
          journeyVoiceExample.textContent += chars[i++];
          voiceTypeTimer = setTimeout(next, 42);
        }
        next();
      }

      function processVoiceInput(text) {
        $('#journeyVoiceLabel').textContent = '正在识别…';
        extractPetInfo(text).then(function (info) {
          if (info.extracted_name) S.petName = info.extracted_name;
          if (info.breed) S.profile.breed = info.breed;
          if (info.color) S.profile.color = info.color;
          if (info.personality_traits && info.personality_traits.length) {
            info.personality_traits.forEach(function (t) {
              if (S.profile.traits.indexOf(t) < 0) S.profile.traits.push(t);
            });
          }
          S.journey.voiceDescription = text;
          S.journey.petImage = 'assets/pet-idle.webp';
          S.journey.generationStartedAt = Date.now();
          interpret(text);
          ensureBackendPet();
          S.journey.stage = 'PHOTO_INPUT'; setDetail(0);
          journeyWorld.classList.remove('is-running');
          journeyCardReset(); journeyConfirm.hidden = false;
          $('#journeyKicker').textContent = '';
          renderPhotoPromptTitle();
          $('#journeyCopy').textContent = '也可以跳过，我们先往前走。';
          journeyProgress(); journeyWorldLevel(); save();
          $('#journeyVoiceLabel').textContent = GUIDE_TEXT.name;
        }).catch(function () {
          // 网络失败时仍使用原始文本
          S.journey.voiceDescription = text;
          S.journey.petImage = 'assets/pet-idle.webp';
          S.journey.generationStartedAt = Date.now();
          interpret(text);
          ensureBackendPet();
          S.journey.stage = 'PHOTO_INPUT'; setDetail(0);
          journeyWorld.classList.remove('is-running');
          journeyCardReset(); journeyConfirm.hidden = false;
          $('#journeyKicker').textContent = '';
          renderPhotoPromptTitle();
          $('#journeyCopy').textContent = '也可以跳过，我们先往前走。';
          journeyProgress(); journeyWorldLevel(); save();
          $('#journeyVoiceLabel').textContent = GUIDE_TEXT.name;
        });
      }
      $('#journeyRegeneratePhoto').addEventListener('change', function () {
        var file = this.files && this.files[0]; if (!file) return;
        var reader = new FileReader();
        reader.onload = async function () {
          S.journey.petReferenceImage = reader.result;
          S.journey.regenerationPrompt = [S.journey.voiceDescription, '根据补充照片校准外形'].filter(Boolean).join('；');
          S.journey.isRegenerating = true;
          $('#journeyCopy').textContent = '照片收好啦。我们继续往前走。';
          $('#journeyConfirmBtn').disabled = true;
          syncPetPhoto(file, reader.result);
          setTimeout(function () {
            S.journey.isRegenerating = false; S.hasPhoto = true;
            $('#journeyConfirmBtn').disabled = false;
            beginGeneratingJourney();
          }, 2000);
        };
        reader.readAsDataURL(file);
      });
      $('#journeyConfirmBtn').addEventListener('click', function () {
        beginGeneratingJourney();
      });
    }
    var stage = S.journey.stage || 'PET_CREATION';
    if (stage === 'PET_CREATION') {
      journeyCardReset(); journeyCard.classList.remove('is-flowing');
      $('#journeyKicker').textContent = ''; typeInitialJourneyCopy();
    } else if (stage === 'PHOTO_INPUT') {
      journeyCardReset(); journeyCard.classList.remove('is-flowing'); journeyConfirm.hidden = false;
      $('#journeyKicker').textContent = ''; renderPhotoPromptTitle(); $('#journeyCopy').textContent = '也可以跳过，我们先往前走。';
    } else if (stage === 'MEMORY_INPUT' || stage === 'MEMORY_REVEAL' || stage === 'MEMORY_PROCESSING') journeyShowNode();
    else if (stage === 'RAINBOW_BRIDGE' || stage === 'GROUP_BRIDGE') journeyRainbow();
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

    var n = $('#nWeave');
    setTimeout(function () { if (S.scene === 'weave') w.classList.add('is-settled'); }, 80);
    say(n, '<span class="dim">原来，这里住着好多小狗。</span>', 650);
    setTimeout(function () {
      if (S.scene !== 'weave') return;
      w.classList.add('is-chosen');
      n.innerHTML = '这一间，会是 ' + (S.petName || 'TA') + ' 的家。';
    }, 3100);
    setTimeout(function () {
      if (S.scene !== 'weave') return;
      w.classList.add('is-entering');
    }, 4850);
    // 推镜还在走时就叠上特写，交叉淡入；特写和主页是同一张图，之后切场无缝
    setTimeout(function () {
      if (S.scene !== 'weave') return;
      w.classList.add('is-closeup');
    }, 6100);
    syncHomeConfig();
    setTimeout(function () { if (S.scene === 'weave') goto('home'); }, 7600);
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
  var homeReactionTarget = null;
  function showHomeReaction(target, text) {
    var note = $('#homeNote');
    if (homeReactionTarget) homeReactionTarget.classList.remove('is-reacting');
    homeReactionTarget = target || null;
    if (homeReactionTarget) {
      homeReactionTarget.classList.remove('is-reacting');
      void homeReactionTarget.offsetWidth;
      homeReactionTarget.classList.add('is-reacting');
    }
    note.textContent = text;
    note.classList.add('is-visible');
    clearTimeout(homeNoteTimer);
    homeNoteTimer = setTimeout(function () {
      note.classList.remove('is-visible');
      if (homeReactionTarget) homeReactionTarget.classList.remove('is-reacting');
      homeReactionTarget = null;
    }, 2600);
  }
  function setHomeLights(on, announce) {
    S.story.homeLightsOn = on;
    S.story.petState = on ? 'idle' : 'down';
    homeHub.classList.toggle('is-lights-off', !on);
    $('#homeLamp').setAttribute('aria-label', on ? '关灯，让小狗休息' : '开灯，叫醒小狗');
    if (announce) showHomeReaction($('#homeLamp'), on ? '亮起来啦，我还想再陪你一会儿。' : '晚安，我就在这里。');
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
    if (!S.journey.customRevealShown) {
      S.journey.customRevealShown = true;
      setTimeout(function () {
        if (S.scene === 'home') showHomeReaction($('#homePet'), '我想起来啦。原来，这就是我。');
      }, 650);
    }
    // 如果有AI生成的狗狗图片，显示在homePet位置（每次进入home都检查，不依赖customRevealShown）
    if (S.generatedDogImage) {
      var homePetEl = $('#homePet');
      if (homePetEl) {
        var existingImg = homePetEl.querySelector('.generated-dog-img');
        if (existingImg) existingImg.remove();
        var img = document.createElement('img');
        img.className = 'generated-dog-img';
        img.src = 'data:image/png;base64,' + S.generatedDogImage;
        img.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;pointer-events:none;';
        homePetEl.style.position = 'relative';
        homePetEl.appendChild(img);
      }
    }
  }

  $('#homeLamp').addEventListener('click', function () { setHomeLights(!S.story.homeLightsOn, true); });
  $('#homeMailbox').addEventListener('click', openLetter);
  $('#homeBowl').addEventListener('click', function () {
    if (!S.story.homeLightsOn) setHomeLights(true, false);
    showHomeReaction(this, '你是不是又怕我饿着呀？');
  });
  $('#homePet').addEventListener('click', function () {
    goto('companion');
  });
  // 每次进入home场景时尝试显示AI生成的狗狗图片
  (function () {
    var origGoto = goto;
    window.goto = function (name) {
      origGoto(name);
      if (name === 'home' && S.generatedDogImage) {
        setTimeout(function () {
          var homePetEl = $('#homePet');
          if (homePetEl) {
            var existingImg = homePetEl.querySelector('.generated-dog-img');
            if (existingImg) existingImg.remove();
            var img = document.createElement('img');
            img.className = 'generated-dog-img';
            img.src = 'data:image/png;base64,' + S.generatedDogImage;
            img.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;pointer-events:none;';
            homePetEl.style.position = 'relative';
            homePetEl.appendChild(img);
          }
        }, 100);
      }
    };
  })();
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

  function localBeat() {
    // 只挑用得上的：needs 指向的安全物件必须真的出现在这个家里
    var pool = BEATS.filter(function (b, i) {
      if (S.story.used.indexOf(i) >= 0) return false;
      if (b.needs && S.profile.objects.indexOf(b.needs) < 0) return false;
      return true;
    });
    if (!pool.length) { S.story.used = []; pool = BEATS.slice(); }
    var beat = pick(pool);
    S.story.used.push(BEATS.indexOf(beat));
    return beat;
  }

  // 下一幕：优先用 LLM 按宠物档案+记忆动态生成，失败时退化为本地固定剧情池
  async function nextBeat() {
    S.story.beat++;
    var remote = await backendGenerateBeat();
    if (remote) return remote;
    return localBeat();
  }

  async function playBeat(beatOrPromise) {
    if (busy) return;
    busy = true;
    var beat = await beatOrPromise;   // nextBeat() 可能是异步（LLM 生成），await 一个非 Promise 值等价于原值
    if (!beat) { busy = false; return; }
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
    S.story.lastEnv = beat.env || S.story.lastEnv;
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
    splash: initSplash, journey: initJourney,
    weave: initWeave, home: initHome, letter: initLetter, companion: initCompanion
  };

  var jump = { '1': 'journey', '2': 'journey', '3': 'home', '4': 'companion' };
  document.addEventListener('keydown', function (e) {
    if (e.target && e.target.matches && e.target.matches('input, textarea')) return;
    if (jump[e.key]) goto(jump[e.key]);
    if (e.key === 'r' || e.key === 'R') reset();
  });

  window.__mh = { S: S, goto: goto, reset: reset, addMemory: addMemory, addPaw: addPaw };  // 调试用

  // 页面卸载时清除生成图片的重试timer，避免刷新后与新请求冲突
  window.addEventListener('beforeunload', function () {
    if (S._retryTimer) { clearTimeout(S._retryTimer); S._retryTimer = null; }
  });

  var resumed = REVIEW_MODE ? false : load();
  // 页面恢复时：如果generatingDogImage=true但generatedDogImage=null，说明刷新前请求中断了，重试
  if (!REVIEW_MODE && S.generatingDogImage && !S.generatedDogImage) {
    S.generatingDogImage = false;
    save();
    console.log('[triggerDogImageGeneration] 页面恢复检测到中断的生成请求，2秒后重试...');
    setTimeout(function () { triggerDogImageGeneration(); }, 2000);
  }
  if (window.PUPPYLAND_FULL_DEMO) {
    S.scene = 'journey';
    S.journey.stage = 'PET_CREATION';
    S.journey.sceneIndex = 0;
    S.journey.currentMemoryIndex = 0;
    S.journey.worldLevel = 0;
    S.journey.petCompletion = .25;
    S.journey.customRevealShown = false;
    S.detail = 0;
  }
  setDetail(S.detail);
  var reviewParams = new URLSearchParams(location.search);
  var reviewScene = reviewParams.get('reviewScene');
  var reviewState = reviewParams.get('reviewState');
  if (reviewScene && scenes[reviewScene]) {
    document.documentElement.classList.add('review-frame');
    S.petName = S.petName || '煤球';
    if (reviewScene === 'splash') scenes.splash.dataset.ready = '1';
    if (reviewScene === 'journey') {
      S.journey.stage = reviewState === 'confirm' ? 'PHOTO_INPUT' : 'PET_CREATION';
      S.journey.sceneIndex = 0;
      S.journey.currentMemoryIndex = 0;
      S.journey.worldLevel = 0;
      S.journey.petCompletion = reviewState === 'confirm' ? .35 : .25;
      S.journey.petImage = S.journey.petImage || POSE.idle;
      setDetail(reviewState === 'confirm' ? .35 : .25);
    }
    if (reviewScene === 'weave') {
      scenes.weave.dataset.ready = '1';
      scenes.weave.classList.add('is-settled', 'is-chosen');
      $('#nWeave').textContent = '这一间，会是 ' + S.petName + ' 的家。';
    }
    goto(reviewScene);
    return;
  }
  startupDestination = !window.PUPPYLAND_FULL_DEMO && resumed && (S.scene === 'home' || S.scene === 'letter' || S.scene === 'companion') ? S.scene : 'journey';
  goto('splash');
})();
