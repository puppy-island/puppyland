# Memory River Phase Two Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing second-stage room tapping scene with a full-screen `swimming.png` memory river where five user-provided memories progressively restore a transparent dog before a rainbow-bridge transition into stage three.

**Architecture:** Keep the existing single-page scene/state architecture and Mock ASR. Replace only the `room2` visual/content subtree and `initS2()` behavior with a data-driven five-step river state machine. Render background, dog, river effects, memory cards, and bridge as independent DOM layers controlled by CSS variables and explicit state flags; keep `addMemory()`, `addPaw()`, `save()`, and `goto()` as the existing persistence/navigation boundaries.

**Tech Stack:** Vanilla HTML, CSS, JavaScript IIFE, existing WebP dog poses, localStorage Guest Session, Python static server; no framework, bundler, Canvas, WebGL, or new runtime dependency.

## Global Constraints

- Use `swimming.png` as the second-stage full-screen background with `background-size: cover`; do not stretch its aspect ratio.
- Collect five sequential memories: first meeting, bringing TA home, feeding/care, private habit, and a particularly happy time.
- Support text entry and press-and-hold recording; Mock ASR output must be editable before submission.
- After each submission, play the memory/dog animation and wait for an explicit “继续前进” click; never auto-advance.
- Preserve existing `addMemory()` sensitive filtering, Guest Session persistence, first/third/Weave/Companion scenes, and keyboard shortcuts.
- Keep the project zero-dependency and use CSS transform/opacity for motion.
- Respect `prefers-reduced-motion`, keyboard operation, safe-area insets, and no horizontal scrolling on narrow screens.

## File Map

- Modify `prototype/index.html`: replace the current stage-two room objects with river background, dog, memory, composer, and bridge layer markup; keep shared SVG symbols and all other scenes intact.
- Modify `prototype/style.css`: add stage-two river tokens, full-screen background treatment, dog completeness states, memory cards/points, input states, and rainbow bridge transition; leave unrelated existing rules unchanged.
- Modify `prototype/app.js`: add river data/state helpers, replace `initS2()` touch logic with the five-step text/voice/submit/continue flow, restore persisted progress, and trigger the existing `goto('s3')` exit.
- Add `prototype/assets/swimming.png`: copy the user-provided `D:/zzy/zzy/puppy island/swimming.png` without editing it.
- Add `docs/superpowers/specs/2026-08-28-memory-river-design.md`: approved behavior and acceptance specification (already committed; use as source of truth).

### Task 1: Add the river asset and semantic HTML layers

**Files:**
- Create: `prototype/assets/swimming.png` (copy the supplied image bytes)
- Modify: `prototype/index.html` in the section with `data-scene="s2"`

**Interfaces:**
- Produces element IDs consumed by later tasks: `#riverScene`, `#riverBackground`, `#riverFlow`, `#riverMemoryLayer`, `#riverDog`, `#riverDogImage`, `#riverBridge`, `#riverPrompt`, `#riverComposer`, `#riverText`, `#riverRecord`, `#riverSubmit`, `#riverContinue`, `#riverStatus`.
- Keeps existing `#room2`, `#n2`, `#a2`, `#trail2` selectors only if other shared code still needs them; remove obsolete touch-object markup and listeners.

- [ ] **Step 1: Verify the source asset before copying**

Run:

```powershell
Get-Item 'D:\zzy\zzy\puppy island\swimming.png' | Select-Object FullName,Length
```

Expected: the supplied PNG exists and has a non-zero length.

- [ ] **Step 2: Copy the asset into the prototype**

Run:

```powershell
Copy-Item -LiteralPath 'D:\zzy\zzy\puppy island\swimming.png' -Destination '.\prototype\assets\swimming.png'
```

Expected: `prototype/assets/swimming.png` exists; do not remove or alter the original file.

- [ ] **Step 3: Replace only the stage-two HTML subtree**

Use this structure inside `data-scene="s2"`:

```html
<div class="world river-world" id="riverScene">
  <div class="river-background" id="riverBackground" aria-hidden="true"></div>
  <div class="river-flow" id="riverFlow" aria-hidden="true"></div>
  <div class="river-memory-layer" id="riverMemoryLayer" aria-live="polite"></div>
  <div class="river-dog" id="riverDog">
    <img id="riverDogImage" class="pet" src="assets/pet-idle.webp" alt="一只正在逐渐变完整的小狗">
  </div>
  <div class="river-bridge" id="riverBridge" aria-hidden="true"><span>彩虹桥</span></div>
  <div class="river-status" id="riverStatus" role="status" aria-live="polite"></div>
</div>
<div class="dock river-dock">
  <p class="narration serif" id="riverPrompt"></p>
  <form class="river-composer" id="riverComposer" autocomplete="off">
    <textarea id="riverText" rows="1" maxlength="600" placeholder="写下这一段…" aria-label="这一段记忆"></textarea>
    <button type="button" class="voice-btn" id="riverRecord" aria-label="按住录音">录音</button>
    <button type="submit" class="primary-btn" id="riverSubmit">记下这段</button>
  </form>
  <div class="river-actions" id="riverActions"><button type="button" class="primary-btn" id="riverContinue" hidden>继续前进</button></div>
</div>
```

Expected: the stage has one semantic live status region, one editable text control, one recording control, one submit control, and a hidden continue control; no old `data-touch` elements remain in stage two.

- [ ] **Step 4: Run an HTML smoke check**

Run:

```powershell
rg -n "riverScene|riverDog|riverPrompt|riverRecord|riverContinue|data-touch" .\prototype\index.html
```

Expected: all river IDs are present and `data-touch` appears only zero times in the stage-two subtree.

- [ ] **Step 5: Commit the semantic layer**

```powershell
git add prototype/index.html prototype/assets/swimming.png
git commit -m "feat: add memory river stage markup and asset"
```

### Task 2: Implement the data-driven river state machine

**Files:**
- Modify: `prototype/app.js` in the `S.story` defaults and the current `initS2()` block

**Interfaces:**
- Consumes: Task 1 IDs and existing `addMemory(sceneId, text, priority)`, `addPaw(sceneId, label, memoryId)`, `save()`, `goto(name)`, `capture(slot, options)`, `mockASR(key)`, `POSE`.
- Produces: `RIVER_STEPS`, `ensureRiverState()`, `renderRiverStep()`, `submitRiverMemory(text)`, `continueRiver()`, `finishRiver()`; later CSS and verification tasks depend on these state names and `data-river-state` attributes.

- [ ] **Step 1: Write a deterministic state contract in comments and defaults**

Extend the initial `S.story` object with:

```js
riverStep: 0,
riverSubmitted: false,
riverAwaitingContinue: false,
riverComplete: false,
riverMemories: [],
dogCompleteness: 0
```

Add an idempotent `ensureRiverState()` that fills missing fields after loading older Guest Session data and clamps `riverStep` to `0..4` and `dogCompleteness` to `0..1`.

- [ ] **Step 2: Define the five prompt records**

Add a constant with exact fields:

```js
var RIVER_STEPS = [
  { key:'meet',  title:'第一次见面',      prompt:'还记得第一次见到 TA 的地方吗？', priority:2, pose:'approach', completeness:.18 },
  { key:'home',  title:'把 TA 带回家',    prompt:'那天，你是怎样把 TA 带回家的？', priority:2, pose:'approach', completeness:.20 },
  { key:'care',  title:'喂饭和照料',     prompt:'想起一顿饭，或一次照顾 TA 的时刻。', priority:1, pose:'happy', completeness:.20 },
  { key:'habit', title:'只有你们知道的习惯', prompt:'你们之间有没有一个别人不懂的小习惯？', priority:2, pose:'run', completeness:.20 },
  { key:'joy',   title:'特别幸福的时光', prompt:'哪一段时光，让你们都觉得特别幸福？', priority:3, pose:'run', completeness:.22 }
];
```

- [ ] **Step 3: Replace touch handlers with `renderRiverStep()`**

`renderRiverStep()` must set `S.story.riverSubmitted = false`, `S.story.riverAwaitingContinue = false`, reset the composer, update `#riverPrompt` with the current prompt, set `data-river-step`, restore any existing `riverMemories`, and call `renderRiverDog()` plus `renderRiverMemories()`.

- [ ] **Step 4: Implement editable text and press-and-hold recording**

Wire the form submit to `submitRiverMemory(textarea.value)`. Reuse `capture()` with a stage-two slot adapter or add a small `startRiverRecording()` wrapper that shows the existing `#recOverlay`, calls `mockASR('day')` on release, and writes the result to `#riverText` without submitting it. Escape/cancel must close the overlay and set `#riverStatus` to `没有听清，可以再说一次或直接写下来`.

- [ ] **Step 5: Implement `submitRiverMemory(text)` with lock and persistence**

Reject empty trimmed text. On success:

```js
var step = RIVER_STEPS[S.story.riverStep];
var memory = addMemory('s2', text.trim(), step.priority);
addPaw('s2', step.title, memory.id);
S.story.riverMemories.push({ step:S.story.riverStep, memoryId:memory.id, text:text.trim(), createdAt:Date.now() });
S.story.dogCompleteness = Math.min(1, S.story.dogCompleteness + step.completeness);
S.story.riverSubmitted = true;
S.story.riverAwaitingContinue = false;
save();
```

Then disable composer controls, render the new memory card, call `animateRiverBeat(step)`, and reveal `#riverContinue` only after the animation resolves.

- [ ] **Step 6: Implement `continueRiver()` and `finishRiver()`**

`continueRiver()` must no-op unless `riverSubmitted` and `riverAwaitingContinue` are true. For steps `0..3`, increment `riverStep`, save, and call `renderRiverStep()`. For step `4`, call `finishRiver()`.

`finishRiver()` sets `riverComplete = true`, `riverAwaitingContinue = false`, saves, adds `is-bridge-visible` to `#riverScene`, switches the dog image to `POSE.run`, and after the bridge transition duration calls `goto('s3')` only if `S.scene === 's2'`.

- [ ] **Step 7: Restore persisted progress during `initS2()`**

`initS2()` must call `ensureRiverState()`, bind listeners once using `data-ready`, render all persisted memory cards, and resume the current step. If `riverComplete` is already true, show the bridge state and schedule the same guarded `finishRiver()` transition without creating duplicate memories.

- [ ] **Step 8: Run JavaScript syntax verification**

Run:

```powershell
node --check .\prototype\app.js
```

Expected: exit code 0 and no syntax errors.

- [ ] **Step 9: Commit the state machine**

```powershell
git add prototype/app.js
git commit -m "feat: drive stage two with sequential memory inputs"
```

### Task 3: Add the full-screen river visual system and animations

**Files:**
- Modify: `prototype/style.css` near the current stage-two rules and responsive section

**Interfaces:**
- Consumes: Task 1 class/ID structure and Task 2 attributes/classes: `data-river-step`, `data-river-state`, `is-memory-replay`, `is-bridge-visible`, `--dog-completeness`, `--river-progress`.
- Produces: stable visual states for `idle`, `recording`, `replay`, `awaiting-continue`, and `bridge` with reduced-motion fallbacks.

- [ ] **Step 1: Define scoped stage-two tokens and background**

Add rules scoped under `[data-scene="s2"]` so existing scenes are unaffected:

```css
[data-scene="s2"]{ --river-progress:0; --dog-completeness:0; --dock-tint:18,35,68; }
[data-scene="s2"] .river-world{ position:relative; overflow:hidden; background:#719bd6; }
.river-background{ position:absolute; inset:0; background:url('assets/swimming.png') center center / cover no-repeat; }
.river-background::after{ content:""; position:absolute; inset:0; background:linear-gradient(180deg,rgba(29,63,119,.04),rgba(24,57,125,.28) 72%,rgba(20,38,83,.72)); }
```

Keep the dock readable without obscuring the dog by using a transparent-to-dark gradient only on `.river-dock`.

- [ ] **Step 2: Implement dog completeness styling**

Use CSS variables driven by JS:

```css
.river-dog{ left:calc(20% + var(--river-progress) * 58%); bottom:32%; opacity:calc(.24 + var(--dog-completeness) * .76); filter:blur(calc((1 - var(--dog-completeness)) * 4px)) saturate(calc(.45 + var(--dog-completeness) * .55)); transition:left 1.4s ease,opacity 1.2s ease,filter 1.2s ease; }
```

Add pose/flip rules and `is-memory-replay` movement; avoid transform conflicts by keeping horizontal position on the container and vertical bobbing on the image.

- [ ] **Step 3: Implement memory cards and river points**

Cards must cap at 84vw, wrap Chinese text, and expose full text via a `<details>` or button expansion. Points use `box-shadow` glow and staggered opacity; each card gets `style="--memory-index:n"` for deterministic placement.

- [ ] **Step 4: Implement replay and bridge transitions**

Add `@keyframes riverDrift`, `memoryArrive`, `dogSwim`, and `bridgeReveal`. `prefers-reduced-motion: reduce` must set animation durations near zero while leaving card/bridge visibility and button states intact.

- [ ] **Step 5: Add responsive and accessibility states**

Ensure `.river-composer` uses `padding-bottom:calc(16px + env(safe-area-inset-bottom))`, buttons have visible focus rings, textarea does not exceed 4 lines, and the scene has no horizontal overflow at widths `320px`, `375px`, and `520px`.

- [ ] **Step 6: Run CSS and selector smoke checks**

Run:

```powershell
rg -n "river-background|river-dog|dog-completeness|river-memory|river-bridge|prefers-reduced-motion" .\prototype\style.css
```

Expected: all required selectors and reduced-motion rules are present.

- [ ] **Step 7: Commit the visual system**

```powershell
git add prototype/style.css
git commit -m "feat: style memory river progression and bridge transition"
```

### Task 4: Integrate regression-safe behavior and build output

**Files:**
- Modify: `prototype/app.js` and `prototype/index.html` only if integration fixes are required
- Inspect: `prototype/build.py`, `prototype/README.md`

**Interfaces:**
- Consumes: completed river state machine and visual system from Tasks 1–3.
- Produces: working static prototype with stage navigation, persistence, keyboard shortcuts, and distributable single-file build unchanged outside the new asset/data URI.

- [ ] **Step 1: Verify scene navigation and keyboard shortcuts**

Serve the prototype:

```powershell
python -m http.server 4321 --directory prototype
```

Use a browser at `http://localhost:4321` and verify keys `1`–`5` still select scenes, `R` clears Guest Session, and stage three remains reachable after the bridge.

- [ ] **Step 2: Verify the five-step happy path manually**

For each prompt, submit a short unique text, wait for the replay, and assert:

```text
submit -> composer disabled -> memory card appears -> dog moves/clarifies -> continue appears -> next prompt
```

After step four, assert the dog is visibly complete and the rainbow bridge appears before stage three.

- [ ] **Step 3: Verify recording and failure paths**

Press and hold the record button, release, edit the returned Mock ASR text, submit it, then test cancel/empty text. Expected: cancel closes the overlay without adding a Memory; empty text keeps focus and does not advance.

- [ ] **Step 4: Verify persistence and duplicate protection**

Refresh after each of steps 1–4 and confirm the same prompt and cards return. Double-click submit and continue during replay; expected: exactly one Memory per step and no skipped prompt.

- [ ] **Step 5: Verify sensitive-memory behavior**

Submit a phrase containing an existing sensitive trigger such as `最后`. Confirm the card can display the user text, while the Memory has `groundingAllowed:false` and no sensitive content is added to `S.profile`.

- [ ] **Step 6: Verify reduced motion and narrow viewport**

Test `prefers-reduced-motion: reduce` and viewport widths 320px/375px/520px. Expected: no horizontal scrollbar, controls remain reachable, and state changes remain visible even when motion is suppressed.

- [ ] **Step 7: Build the single-file distribution**

Run:

```powershell
python .\prototype\build.py
```

Expected: build completes without errors and embeds `swimming.png` as a data URI alongside existing assets. Open the generated `prototype/dist/index.html` through the static server and repeat the first prompt plus bridge smoke path.

- [ ] **Step 8: Run final diff checks**

Run:

```powershell
git diff --check HEAD~4..HEAD
git status --short
```

Expected: no whitespace errors; only intended river files are changed, and any pre-existing user modification to `prototype/style.css` is preserved rather than overwritten.

- [ ] **Step 9: Commit integration fixes**

```powershell
git add prototype/index.html prototype/app.js prototype/style.css prototype/build.py prototype/README.md
git commit -m "test: verify memory river integration and distribution build"
```

## Self-Review Checklist

- Spec coverage: full-screen asset, five dynamic memory prompts, editable Mock ASR, explicit continue gate, dog completeness, rainbow bridge, persistence, sensitive filtering, reduced motion, accessibility, responsive layout, and regression boundaries are each mapped to a task.
- Placeholder scan: all steps contain concrete files, selectors, state names, commands, expected results, and commit boundaries; no unfinished marker or vague implementation instruction remains.
- Type/name consistency: HTML IDs match JavaScript selectors; `RIVER_STEPS`, `ensureRiverState()`, `renderRiverStep()`, `submitRiverMemory()`, `continueRiver()`, and `finishRiver()` are used consistently; CSS variables/attributes match the state machine contract.
- Scope: no new framework, backend service, real ASR, or third-party asset pipeline is included.
