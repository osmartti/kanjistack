<script>
	import { onMount, tick } from "svelte";
	import { get, set } from "idb-keyval";
	import { fade, fly } from "svelte/transition";
	import Menu from "./lib/Menu.svelte";

	// ─── Constants ────────────────────────────────────────────────────────────
	const WINDOW_SIZE = 30;
	const DB_KEY = "kanjistack_v1";
	const SR_INTERVALS = [
		1 * 60 * 60 * 1000,
		4 * 60 * 60 * 1000,
		12 * 60 * 60 * 1000,
		1 * 24 * 60 * 60 * 1000,
		3 * 24 * 60 * 60 * 1000,
		7 * 24 * 60 * 60 * 1000,
		14 * 24 * 60 * 60 * 1000,
		30 * 24 * 60 * 60 * 1000,
	];
	const LANG_NAMES = {
		en: "English",
		fr: "Français",
		es: "Español",
		pt: "Português",
	};

	// ─── Data ─────────────────────────────────────────────────────────────────
	let kanjiList = [];
	let loading = true;
	let loadError = null;
	let availableLangs = ["en"];

	// ─── Persisted state ──────────────────────────────────────────────────────
	let windowKanji = [];
	let nextKanjiIndex = 0;
	let srQueue = []; // [{kanjiIndex, dueDate}]
	let srStepMap = {}; // kanjiIndex → SR step count
	let droppedCount = 0;
	let currentPos = 0;
	let selectedLang = "en";

	// ─── UI / navigation state ────────────────────────────────────────────────
	let page = "learn"; // 'learn' | 'learn-sr' | 'stack-current' | 'stack-sr'
	let revealed = false;
	let showInfo = false;
	let srLearnPos = 0;
	let srRevealed = false;

	// ─── Weighted learning & seen tracking ────────────────────────────────────
	let weightMap      = {};   // kanjiIndex → weight (starts 1, +1 per Keep)
	let seenSet        = new Set(); // ever-seen kanji indices (for "new entry" badge)
	let lastKanjiIndex = -1;   // index of last-shown kanji (for no-repeat)
	let isNew          = false; // true when current kanji is being seen for first time

	// ─── Fly "+1" animations (drop = green, sr = orange) ─────────────────────
	let dropFly      = null;  // {x, y, dx, dy} — set before showing
	let srFly        = null;
	let showDropFly  = false;
	let showSRFly    = false;
	let dropFlyTimer = null;
	let srFlyTimer   = null;

	/** Get start (kanji center) + end (target element center) for a fly animation. */
	function getFlyParams(targetSel) {
		const kanjiEl  = document.querySelector('.kanji-char');
		const targetEl = document.querySelector(targetSel);
		if (!kanjiEl || !targetEl) return null;
		const kr = kanjiEl.getBoundingClientRect();
		const tr = targetEl.getBoundingClientRect();
		return {
			x:  kr.left + kr.width  / 2,
			y:  kr.top  + kr.height / 2,
			dx: (tr.left + tr.width  / 2) - (kr.left + kr.width  / 2),
			dy: (tr.top  + tr.height / 2) - (kr.top  + kr.height / 2),
		};
	}

	// ─── Learn — derived ──────────────────────────────────────────────────────
	$: safePos = windowKanji.length
		? Math.min(currentPos, windowKanji.length - 1)
		: 0;
	$: current =
		kanjiList.length && windowKanji.length
			? kanjiList[windowKanji[safePos]]
			: null;
	$: onyomi = current?.on ?? [];
	$: kunyomi = current?.kun ?? [];
	$: meanings =
		current?.meanings?.[selectedLang] ?? current?.meanings?.en ?? [];
	$: nanori = current?.nanori ?? [];
	$: dueCount = srQueue.filter((i) => i.dueDate <= Date.now()).length;
	$: complete =
		!loading &&
		kanjiList.length > 0 &&
		windowKanji.length === 0 &&
		nextKanjiIndex >= kanjiList.length;
	$: progressPct = kanjiList.length
		? Math.min(100, (droppedCount / kanjiList.length) * 100)
		: 0;
	$: srLabel = (() => {
		if (!current) return "SR";
		const step = srStepMap[windowKanji[safePos]] ?? 0;
		const ms = SR_INTERVALS[Math.min(step, SR_INTERVALS.length - 1)];
		if (ms < 60 * 60 * 1000) return `SR · ${ms / 60000}m`;
		if (ms < 24 * 60 * 60 * 1000) return `SR · ${ms / 3600000}h`;
		return `SR · ${ms / 86400000}d`;
	})();

	// ─── SR Learn — derived ───────────────────────────────────────────────────
	$: safeSRPos = srQueue.length
		? Math.min(srLearnPos, srQueue.length - 1)
		: 0;
	$: srCurrent = srQueue.length
		? kanjiList[srQueue[safeSRPos].kanjiIndex]
		: null;
	$: srOnyomi = srCurrent?.on ?? [];
	$: srKunyomi = srCurrent?.kun ?? [];
	$: srMeanings =
		srCurrent?.meanings?.[selectedLang] ?? srCurrent?.meanings?.en ?? [];
	$: srNanori = srCurrent?.nanori ?? [];

	// ─── Persistence ──────────────────────────────────────────────────────────
	async function saveState() {
		try {
			await set(DB_KEY, {
				windowKanji,
				nextKanjiIndex,
				srQueue,
				srStepMap,
				droppedCount,
				currentPos,
				selectedLang,
				weightMap,
				seenIndices: [...seenSet],
				lastKanjiIndex,
			});
		} catch (e) {
			console.warn('saveState failed:', e);
		}
	}

	async function loadState() {
		try {
			const s = await get(DB_KEY);
			if (s) {
				windowKanji    = s.windowKanji    ?? [];
				nextKanjiIndex = s.nextKanjiIndex ?? 0;
				srQueue        = s.srQueue        ?? [];
				srStepMap      = s.srStepMap      ?? {};
				droppedCount   = s.droppedCount   ?? 0;
				currentPos     = s.currentPos     ?? 0;
				selectedLang   = s.selectedLang   ?? "en";
				weightMap      = s.weightMap      ?? {};
				seenSet        = new Set(s.seenIndices ?? []);
				lastKanjiIndex = s.lastKanjiIndex ?? -1;
			} else {
				initFresh();
			}
		} catch (e) {
			console.warn('loadState failed, starting fresh:', e);
			initFresh();
		}
	}

	function initFresh() {
		const count    = Math.min(WINDOW_SIZE, kanjiList.length);
		windowKanji    = Array.from({ length: count }, (_, i) => i);
		nextKanjiIndex = count;
		srQueue        = [];
		srStepMap      = {};
		droppedCount   = 0;
		currentPos     = 0;
		weightMap      = {};
		seenSet        = new Set();
		lastKanjiIndex = -1;
	}

	// ─── Window helpers ───────────────────────────────────────────────────────
	function injectDueSR() {
		const now = Date.now();
		const due = srQueue.filter((i) => i.dueDate <= now);
		if (!due.length) return;
		const inWindow = new Set(windowKanji);
		for (const item of due) {
			if (!inWindow.has(item.kanjiIndex)) {
				windowKanji = [item.kanjiIndex, ...windowKanji];
				inWindow.add(item.kanjiIndex);
			}
		}
		srQueue = srQueue.filter((i) => i.dueDate > now);
	}

	function addNext() {
		if (nextKanjiIndex < kanjiList.length) {
			windowKanji = [...windowKanji, nextKanjiIndex];
			nextKanjiIndex++;
		}
	}

	function removeCurrent() {
		windowKanji = windowKanji.filter((_, i) => i !== currentPos);
		if (windowKanji.length === 0) currentPos = 0;
		else if (currentPos >= windowKanji.length) currentPos = 0;
	}

	// ─── Weighted random selection ────────────────────────────────────────────

	/**
	 * Pick the next position in windowKanji using weighted randomness.
	 * The kanji at lastKanjiIndex is excluded so the same kanji is never
	 * shown twice in a row (falls back to full pool if only one item).
	 */
	function pickNextPos() {
		if (windowKanji.length <= 1) return 0;

		const candidates = windowKanji
			.map((kanjiIdx, pos) => ({ pos, weight: weightMap[kanjiIdx] ?? 1 }))
			.filter(({ pos }) => windowKanji[pos] !== lastKanjiIndex);

		// Safety fallback: if exclusion removes everyone, use full pool
		const pool = candidates.length > 0
			? candidates
			: windowKanji.map((kanjiIdx, pos) => ({ pos, weight: weightMap[kanjiIdx] ?? 1 }));

		const total = pool.reduce((s, c) => s + c.weight, 0);
		let r = Math.random() * total;
		for (const c of pool) {
			r -= c.weight;
			if (r <= 0) return c.pos;
		}
		return pool[pool.length - 1].pos;
	}

	/** Check if the kanji at currentPos is new; update isNew and seenSet. */
	function checkIfNew() {
		if (!windowKanji.length) { isNew = false; return; }
		const idx = windowKanji[Math.min(currentPos, windowKanji.length - 1)];
		if (idx !== undefined && !seenSet.has(idx)) {
			seenSet.add(idx);
			isNew = true;
		} else {
			isNew = false;
		}
	}

	// ─── Learn actions ────────────────────────────────────────────────────────
	function handleTap() {
		if (!revealed) revealed = true;
	}

	async function onDrop() {
		// Capture last-shown before removing it
		lastKanjiIndex = windowKanji[Math.min(currentPos, windowKanji.length - 1)] ?? -1;

		// Fly green "+1" from kanji → stat counter
		dropFly = getFlyParams('.stat-wrap');
		showDropFly = false;
		await tick();
		showDropFly = true;
		clearTimeout(dropFlyTimer);
		dropFlyTimer = setTimeout(() => { showDropFly = false; }, 1200);

		removeCurrent();
		droppedCount++;
		addNext();
		injectDueSR();
		currentPos = pickNextPos();
		checkIfNew();
		revealed = false;
		await saveState();
	}

	async function onKeep() {
		const posNow = Math.min(currentPos, windowKanji.length - 1);
		const idxNow = windowKanji[posNow];

		// Increment weight so this kanji appears more often
		weightMap = { ...weightMap, [idxNow]: (weightMap[idxNow] ?? 1) + 1 };
		lastKanjiIndex = idxNow;

		injectDueSR();
		currentPos = pickNextPos();
		checkIfNew();
		revealed = false;
		await saveState();
	}

	async function onSR() {
		const posNow     = Math.min(currentPos, windowKanji.length - 1);
		const kanjiIndex = windowKanji[posNow];
		lastKanjiIndex   = kanjiIndex ?? -1;

		const step     = srStepMap[kanjiIndex] ?? 0;
		const interval = SR_INTERVALS[Math.min(step, SR_INTERVALS.length - 1)];
		srStepMap = { ...srStepMap, [kanjiIndex]: step + 1 };
		srQueue   = [...srQueue, { kanjiIndex, dueDate: Date.now() + interval }];

		// Fly orange "+1" from kanji → ··· menu button
		srFly = getFlyParams('.dots-btn');
		showSRFly = false;
		await tick();
		showSRFly = true;
		clearTimeout(srFlyTimer);
		srFlyTimer = setTimeout(() => { showSRFly = false; }, 1200);

		removeCurrent();
		addNext();
		injectDueSR();
		currentPos = pickNextPos();
		checkIfNew();
		revealed = false;
		await saveState();
	}

	// ─── SR Learn actions ─────────────────────────────────────────────────────
	function handleSRTap() {
		if (!srRevealed) srRevealed = true;
	}

	async function onSRKeep() {
		// Stays in SR queue — cycle to next item
		if (srQueue.length > 1) srLearnPos = (srLearnPos + 1) % srQueue.length;
		srRevealed = false;
	}

	async function onSRDrop() {
		// Mastered — remove from SR queue
		srQueue = srQueue.filter((_, i) => i !== safeSRPos);
		droppedCount++;
		if (srLearnPos >= srQueue.length && srQueue.length > 0) srLearnPos = 0;
		srRevealed = false;
		await saveState();
	}

	// ─── Navigation / menu ────────────────────────────────────────────────────
	function navigate(p) {
		page = p;
		showInfo = false;
		if (p === "learn-sr") {
			srLearnPos = 0;
			srRevealed = false;
		}
	}

	function selectLang(lang) {
		selectedLang = lang;
		saveState();
	}

	async function confirmReset() {
		showInfo = false;
		if (confirm("Reset all progress? This cannot be undone.")) {
			initFresh();
			revealed = false;
			await saveState();
		}
	}

	// ─── Lifecycle ────────────────────────────────────────────────────────────
	onMount(async () => {
		try {
			const res = await fetch(`${import.meta.env.BASE_URL}kanji.json`);
			kanjiList = await res.json();
			// Collect available meaning languages from the data
			const langSet = new Set();
			for (const k of kanjiList) {
				if (k.meanings)
					Object.keys(k.meanings).forEach((l) => langSet.add(l));
			}
			// English first, rest alphabetical
			availableLangs = [...langSet].sort((a, b) =>
				a === "en" ? -1 : b === "en" ? 1 : a.localeCompare(b),
			);
			await loadState();
			injectDueSR();
				checkIfNew(); // mark initial kanji as new if unseen
		} catch (e) {
			console.error('onMount error:', e);
			loadError = `${e.constructor?.name ?? 'Error'}: ${e.message}`;
		} finally {
			loading = false;
		}
	});
</script>

<!-- ═══════════════════════════════════════════════════════════
     LOADING / ERROR
════════════════════════════════════════════════════════════ -->
{#if loading}
	<div class="screen center">
		<div class="spinner"></div>
		<p class="muted">Loading kanji…</p>
	</div>
{:else if loadError}
	<div class="screen center">
		<p class="error">Failed to load data.<br />{loadError}</p>
	</div>

	<!-- ═══════════════════════════════════════════════════════════
     COMPLETION
════════════════════════════════════════════════════════════ -->
{:else if complete && page === "learn"}
	<div class="screen center">
		<div class="complete-icon">🎉</div>
		<h2>All {kanjiList.length} Jōyō kanji mastered!</h2>
		<p class="muted">Incredible work.</p>
		<button class="reset-btn" on:click={confirmReset}>Start over</button>
	</div>

	<!-- ═══════════════════════════════════════════════════════════
     LEARN PAGE
════════════════════════════════════════════════════════════ -->
{:else if page === "learn"}
	<div class="screen column">
		<!-- Progress bar -->
		<div class="progress-track">
			<div class="progress-fill" style="width: {progressPct}%"></div>
		</div>

		<!-- Stats + menu row -->
		<div class="stats-row">
			<div class="stat-wrap">
				<span class="stat-val">{droppedCount}</span>
				<span class="stat-lbl">/ {kanjiList.length} learned</span>
			</div>

			<div class="row-right">
				<!-- Info button -->
				<button
					class="icon-btn"
					on:click={() => {
						showInfo = !showInfo;
					}}
					aria-label="Info"
				>
					<svg
						width="17"
						height="17"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<circle cx="12" cy="12" r="10" />
						<line x1="12" y1="8" x2="12" y2="12" />
						<line x1="12" y1="16" x2="12.01" y2="16" />
					</svg>
				</button>

				<Menu
					{page}
					{srQueue}
					{availableLangs}
					{selectedLang}
					{LANG_NAMES}
					on:navigate={(e) => navigate(e.detail)}
					on:selectlang={(e) => selectLang(e.detail)}
				/>
			</div>
		</div>

		<!-- Info panel -->
		{#if showInfo}
			<div class="info-panel" transition:fly={{ y: -10, duration: 200 }}>
				<p>
					<strong>Drop</strong> — mastered. Leaves window, new kanji enters.
				</p>
				<p>
					<strong>Keep</strong> — not ready. Stays in window, show next.
				</p>
				<p>
					<strong>SR</strong> — spaced repetition. Returns after a delay.
				</p>
				{#if srQueue.length}
					<p class="muted">
						{srQueue.length} in SR queue.{dueCount
							? ` ${dueCount} due now.`
							: ""}
					</p>
				{/if}
				<button class="reset-btn small" on:click={confirmReset}
					>Reset progress</button
				>
			</div>
		{/if}

		<!-- Kanji card -->
		<div
			class="card"
			role="button"
			tabindex="0"
			on:click={handleTap}
			on:keydown={(e) => e.key === "Enter" && handleTap()}
		>
			<div class="card-inner" class:revealed>
					{#if isNew}
						<div class="new-badge">✦ new entry</div>
					{/if}
					{#key current?.l}
					<div class="kanji-char" in:fade={{ duration: 180 }}>
						{current?.l ?? ""}
					</div>
				{/key}

				{#if revealed}
					<div class="details">
						{#if meanings.length}
							<p class="meanings">{meanings.join(", ")}</p>
						{/if}
						{#if onyomi.length}
							<div class="reading-row">
								<span class="r-label">On</span>
								<span class="r-text">{onyomi.join("　")}</span>
							</div>
						{/if}
						{#if kunyomi.length}
							<div class="reading-row">
								<span class="r-label">Kun</span>
								<span class="r-text">{kunyomi.join("　")}</span>
							</div>
						{/if}
						{#if current?.ex}
							<div class="reading-row ex-row">
								<span class="r-label">Ex</span>
								<div class="ex-block">
									<div class="example">
										{#each current.ex.f as part}
											{#if part[1]}<ruby>{part[0]}<rt>{part[1]}</rt></ruby>{:else}{part[0]}{/if}
										{/each}
									</div>
									{#if current.ex.t}
										{#each Object.entries(current.ex.t) as [lang, text]}
											<p class="ex-trans">{text}</p>
										{/each}
									{/if}
								</div>
							</div>
						{/if}
						{#if current?.jlpt}
							<span class="badge">JLPT N{current.jlpt}</span>
						{/if}
					</div>
				{:else}
					<p class="tap-hint">tap to reveal</p>
				{/if}
			</div>
		</div>

		<!-- Action buttons -->
		<div class="btn-row" class:hidden={!revealed}>
			{#if revealed}
				<button
					class="action drop"
					on:click|stopPropagation={onDrop}
					in:fly={{ y: 48, duration: 240 }}>Drop</button
				>
				<button
					class="action keep"
					on:click|stopPropagation={onKeep}
					in:fly={{ y: 48, duration: 240, delay: 40 }}>Keep</button
				>
				<button
					class="action sr"
					on:click|stopPropagation={onSR}
					in:fly={{ y: 48, duration: 240, delay: 80 }}
					>{srLabel}</button
				>
			{/if}
		</div>

		<!-- Fixed fly badges — rendered above everything, position computed from DOM -->
		{#if showDropFly && dropFly}
			<div
				class="fly-badge fly-green"
				style="left:{dropFly.x}px; top:{dropFly.y}px; --dx:{dropFly.dx}px; --dy:{dropFly.dy}px"
			>+1</div>
		{/if}
		{#if showSRFly && srFly}
			<div
				class="fly-badge fly-orange"
				style="left:{srFly.x}px; top:{srFly.y}px; --dx:{srFly.dx}px; --dy:{srFly.dy}px"
			>+1</div>
		{/if}
	</div>

	<!-- ═══════════════════════════════════════════════════════════
     LEARN / SR PAGE
════════════════════════════════════════════════════════════ -->
{:else if page === "learn-sr"}
	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => navigate("learn")}
				>‹ Back</button
			>
			<span class="sub-title">Learn / SR</span>
			<span class="sub-count">{srQueue.length} items</span>
			<Menu
				{page}
				{srQueue}
				{availableLangs}
				{selectedLang}
				{LANG_NAMES}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
			/>
		</div>

		{#if srQueue.length === 0}
			<div class="fill-center">
				<p class="muted" style="text-align:center;line-height:1.7">
					SR queue is empty.<br />
					Use the <strong style="color:#c2410c">SR</strong> button while
					learning to add kanji here.
				</p>
				<button class="reset-btn" on:click={() => navigate("learn")}
					>Back to Learn</button
				>
			</div>
		{:else}
			<div
				class="card"
				role="button"
				tabindex="0"
				on:click={handleSRTap}
				on:keydown={(e) => e.key === "Enter" && handleSRTap()}
			>
				<div class="card-inner" class:revealed={srRevealed}>
					{#key srCurrent?.l}
						<div class="kanji-char" in:fade={{ duration: 180 }}>
							{srCurrent?.l ?? ""}
						</div>
					{/key}

					{#if srRevealed}
						<div class="details">
							{#if srMeanings.length}
								<p class="meanings">{srMeanings.join(", ")}</p>
							{/if}
							{#if srOnyomi.length}
								<div class="reading-row">
									<span class="r-label">On</span>
									<span class="r-text"
										>{srOnyomi.join("　")}</span
									>
								</div>
							{/if}
							{#if srKunyomi.length}
									<div class="reading-row">
										<span class="r-label">Kun</span>
										<span class="r-text"
											>{srKunyomi.join("　")}</span
										>
									</div>
								{/if}
								{#if srCurrent?.ex}
									<div class="reading-row ex-row">
										<span class="r-label">Ex</span>
										<div class="ex-block">
											<div class="example">
												{#each srCurrent.ex.f as part}
													{#if part[1]}<ruby>{part[0]}<rt>{part[1]}</rt></ruby>{:else}{part[0]}{/if}
												{/each}
											</div>
											{#if srCurrent.ex.t}
												{#each Object.entries(srCurrent.ex.t) as [lang, text]}
													<p class="ex-trans">{text}</p>
												{/each}
											{/if}
										</div>
									</div>
								{/if}
								{#if srCurrent?.jlpt}
									<span class="badge">JLPT N{srCurrent.jlpt}</span
									>
								{/if}
						</div>
					{:else}
						<p class="tap-hint">tap to reveal</p>
					{/if}
				</div>
			</div>

			<!-- SR-only: Keep + Drop (no SR button) -->
			<div class="btn-row" class:hidden={!srRevealed}>
				{#if srRevealed}
					<button
						class="action keep sr-keep"
						on:click|stopPropagation={onSRKeep}
						in:fly={{ y: 48, duration: 240 }}>Keep</button
					>
					<button
						class="action drop sr-drop"
						on:click|stopPropagation={onSRDrop}
						in:fly={{ y: 48, duration: 240, delay: 60 }}
						>Drop</button
					>
				{/if}
			</div>
		{/if}
	</div>

	<!-- ═══════════════════════════════════════════════════════════
     STACK VIEWS
════════════════════════════════════════════════════════════ -->
{:else if page === "stack-current" || page === "stack-sr"}
	{@const isSR = page === "stack-sr"}
	{@const title = isSR ? "SR Stack" : "Current Stack"}
	{@const items = isSR
		? srQueue.map((q) => ({
				kanji: kanjiList[q.kanjiIndex],
				dueDate: q.dueDate,
			}))
		: windowKanji.map((idx) => ({ kanji: kanjiList[idx], dueDate: null }))}

	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => navigate("learn")}
				>‹ Back</button
			>
			<span class="sub-title">{title}</span>
			<span class="sub-count">{items.length}</span>
			<Menu
				{page}
				{srQueue}
				{availableLangs}
				{selectedLang}
				{LANG_NAMES}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
			/>
		</div>

		<div class="stack-list">
			{#if items.length === 0}
				<p class="stack-empty">Nothing here yet.</p>
			{:else}
				{#each items as { kanji, dueDate }}
					<div class="stack-item">
						<span class="stack-kanji">{kanji.l}</span>
						<div class="stack-info">
							<span class="stack-meaning">
								{(
									kanji.meanings?.[selectedLang] ??
									kanji.meanings?.en ??
									[]
								)
									.slice(0, 3)
									.join(", ")}
							</span>
							<span class="stack-readings">
								{[...(kanji.on ?? []), ...(kanji.kun ?? [])]
									.slice(0, 4)
									.join("  ·  ")}
							</span>
						</div>
						{#if dueDate !== null}
							<span
								class="stack-due"
								class:due-now={dueDate <= Date.now()}
							>
								{dueDate <= Date.now() ? "due" : "later"}
							</span>
						{/if}
					</div>
				{/each}
			{/if}
		</div>
	</div>
{/if}

<!-- ═══════════════════════════════════════════════════════════
     STYLES
════════════════════════════════════════════════════════════ -->
<style>
	/* ── Base ── */
	:global(html, body) {
		height: 100%;
		background: #111;
		color: #f0f0f0;
		font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
			"Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP",
			sans-serif;
		-webkit-font-smoothing: antialiased;
	}
	:global(#app) {
		height: 100%;
	}

	/* ── Layout shells ── */
	.screen {
		height: 100dvh;
		width: 100%;
		max-width: 480px;
		margin: 0 auto;
	}
	.center {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1rem;
		padding: 2rem;
		text-align: center;
	}
	.column {
		display: flex;
		flex-direction: column;
	}

	/* vertically centered + flexible filler (for empty states) */
	.fill-center {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1.25rem;
		padding: 2rem;
	}

	/* ── Progress bar ── */
	.progress-track {
		width: 100%;
		height: 3px;
		background: #1e1e1e;
		flex-shrink: 0;
	}
	.progress-fill {
		height: 100%;
		background: #22c55e;
		transition: width 0.4s ease;
	}

	/* ── Stats row ── */
	.stats-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 0.75rem 0.4rem;
		flex-shrink: 0;
	}

	/* Anchor for the floating "+1" */
	.stat-wrap {
		position: relative;
		display: flex;
		align-items: baseline;
		gap: 0.3rem;
	}
	.stat-val { color: #888; font-weight: 600; font-size: 0.8rem; }
	.stat-lbl { color: #555; font-size: 0.8rem; }

	/* ── Fly badges (fixed, animate from kanji to target) ── */
	.fly-badge {
		position: fixed;
		font-size: 1.6rem;
		font-weight: 800;
		pointer-events: none;
		z-index: 1000;
		transform: translate(-50%, -50%);
		animation: flyToTarget 1.1s cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards;
	}
	.fly-green  { color: #22c55e; }
	.fly-orange { color: #f97316; }

	@keyframes flyToTarget {
		0% {
			opacity: 1;
			transform: translate(-50%, -50%) scale(1.8);
		}
		100% {
			opacity: 0;
			transform:
				translate(calc(-50% + var(--dx)), calc(-50% + var(--dy)))
				scale(0.55);
		}
	}

	.row-right {
		display: flex;
		align-items: center;
		gap: 2px;
	}

	/* ── Icon button (info) ── */
	.icon-btn {
		background: none;
		border: none;
		color: #444;
		cursor: pointer;
		padding: 6px 8px;
		line-height: 1;
		border-radius: 8px;
		transition:
			color 0.15s,
			background 0.15s;
		font-size: 1.1rem;
		letter-spacing: 0.05em;
	}
	.icon-btn:hover {
		color: #aaa;
		background: #1e1e1e;
	}

	/* ── Dropdown menu — styles now in Menu.svelte ── */

	/* ── Info panel ── */
	.info-panel {
		margin: 0 0.75rem 0.5rem;
		background: #1a1a1a;
		border: 1px solid #2a2a2a;
		border-radius: 12px;
		padding: 0.9rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
		font-size: 0.83rem;
		color: #aaa;
		flex-shrink: 0;
	}
	.info-panel strong {
		color: #ddd;
	}

	/* ── Sub-page header ── */
	.sub-header {
		display: flex;
		align-items: center;
		padding: 0.6rem 0.75rem;
		border-bottom: 1px solid #1e1e1e;
		flex-shrink: 0;
		gap: 0.5rem;
	}
	.back-btn {
		background: none;
		border: none;
		color: #888;
		font-size: 1rem;
		cursor: pointer;
		padding: 4px 8px 4px 0;
		transition: color 0.15s;
	}
	.back-btn:hover {
		color: #fff;
	}
	.sub-title {
		flex: 1;
		font-size: 0.95rem;
		font-weight: 600;
		color: #ddd;
	}
	.sub-count {
		font-size: 0.78rem;
		color: #555;
	}

	/* ── Card ── */
	.card {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		-webkit-overflow-scrolling: touch;
		cursor: pointer;
		user-select: none;
		-webkit-tap-highlight-color: transparent;
		scrollbar-width: none;
	}
	.card::-webkit-scrollbar {
		display: none;
	}

	.card-inner {
		position: relative; /* anchor for .new-badge */
		display: flex;
		flex-direction: column;
		align-items: center;
		min-height: 100%;
		padding: 28vh 1.5rem 2.5rem;
		gap: 1.5rem;
		transition: padding-top 0.6s cubic-bezier(0.4, 0, 0.2, 1);
	}
	.card-inner.revealed {
		padding-top: 8vh;
	}

	/* ── "New entry" badge ── */
	.new-badge {
		position: absolute;
		top: 3.5vh;
		left: 50%;
		transform: translateX(-50%);
		color: #22c55e;
		font-size: 0.68rem;
		letter-spacing: 0.22em;
		text-transform: uppercase;
		pointer-events: none;
		white-space: nowrap;
		animation: newEntryFlash 3s ease-in-out infinite;
	}
	@keyframes newEntryFlash {
		0%   { opacity: 0;    transform: translateX(-50%) translateY(-5px); }
		8%   { opacity: 1;    transform: translateX(-50%) translateY(0);    }
		50%  { opacity: 1;    }
		80%  { opacity: 0.08; }
		100% { opacity: 1;    }
	}

	/* ── Kanji character ── */
	.kanji-char {
		font-size: clamp(5rem, 38vw, 200px);
		line-height: 1;
		font-family: "Hiragino Mincho ProN", "Yu Mincho", "MS Mincho",
			"Noto Serif JP", "BIZ UDMincho", serif;
		color: #ffffff;
		text-shadow: 0 2px 24px rgba(255, 255, 255, 0.06);
	}

	.tap-hint {
		font-size: 0.75rem;
		color: #333;
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}

	/* ── Details — staggered CSS animation ── */
	.details {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.6rem;
		width: 100%;
		max-width: 340px;
	}
	.details > * {
		opacity: 0;
		animation: fadeUp 0.45s ease forwards;
	}
	.details > *:nth-child(1) {
		animation-delay: 0.05s;
	}
	.details > *:nth-child(2) {
		animation-delay: 0.15s;
	}
	.details > *:nth-child(3) {
		animation-delay: 0.25s;
	}
	.details > *:nth-child(4) {
		animation-delay: 0.35s;
	}
	.details > *:nth-child(5) {
		animation-delay: 0.45s;
	}
	.details > *:nth-child(6) {
		animation-delay: 0.55s;
	}

	@keyframes fadeUp {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.meanings {
		font-size: 1.05rem;
		color: #d1d5db;
		text-align: center;
		font-style: italic;
		line-height: 1.4;
	}
	.reading-row {
		display: flex;
		align-items: baseline;
		gap: 0.75rem;
	}
	.r-label {
		font-size: 0.65rem;
		color: #555;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		min-width: 2.2rem;
		text-align: right;
	}
	.r-text {
		font-size: 1.15rem;
		color: #94a3b8;
		font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
	}

	/* ── Example sentence with furigana ── */
	.ex-row {
		align-items: flex-start;
	}
	.ex-block {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		flex: 1;
	}
	.example {
		font-size: 1.05rem;
		color: #7c8fa8;
		line-height: 2.5; /* room for rt above */
		font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN",
			"Noto Sans JP", sans-serif;
	}
	ruby { ruby-align: center; }
	rt {
		font-size: 0.58em;
		color: #4b5a6e;
		letter-spacing: 0.01em;
	}
	.ex-trans {
		font-size: 0.82rem;
		color: #4b5a6e;
		line-height: 1.4;
		margin: 0;
	}

	.badge {
		font-size: 0.7rem;
		background: #1e2a3a;
		color: #60a5fa;
		border: 1px solid #1e3a5f;
		border-radius: 6px;
		padding: 2px 8px;
		letter-spacing: 0.05em;
		margin-top: 0.25rem;
	}

	/* ── Action buttons ── */
	.btn-row {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		height: 72px;
		flex-shrink: 0;
		border-top: 1px solid #1e1e1e;
		overflow: hidden;
	}
	/* SR Learn mode only has 2 buttons — equal halves */
	.sr-keep,
	.sr-drop {
		grid-column: span 1;
	}
	.btn-row:has(.sr-keep) {
		grid-template-columns: 1fr 1fr;
	}

	.btn-row.hidden {
		visibility: hidden;
		pointer-events: none;
	}

	.action {
		border: none;
		font-size: 0.9rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		cursor: pointer;
		text-transform: uppercase;
		transition: filter 0.12s;
		color: #fff;
	}
	.action:active {
		filter: brightness(0.82);
	}
	.drop {
		background: #16a34a;
	}
	.keep {
		background: #dc2626;
	}
	.sr {
		background: #c2410c;
	}

	/* ── Stack list ── */
	.stack-list {
		flex: 1;
		overflow-y: auto;
		scrollbar-width: none;
		padding: 0.25rem 0 1rem;
	}
	.stack-list::-webkit-scrollbar {
		display: none;
	}

	.stack-empty {
		text-align: center;
		padding: 3rem 1rem;
		color: #444;
		font-size: 0.9rem;
	}

	.stack-item {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem 1rem;
		border-bottom: 1px solid #191919;
		transition: background 0.1s;
	}
	.stack-item:hover {
		background: #161616;
	}

	.stack-kanji {
		font-size: 2rem;
		font-family: "Hiragino Mincho ProN", "Yu Mincho", "MS Mincho", serif;
		min-width: 2.4rem;
		text-align: center;
		line-height: 1;
		color: #fff;
	}

	.stack-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		min-width: 0;
	}

	.stack-meaning {
		font-size: 0.85rem;
		color: #bbb;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.stack-readings {
		font-size: 0.8rem;
		color: #555;
		font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.stack-due {
		font-size: 0.7rem;
		color: #555;
		background: #1e1e1e;
		border-radius: 6px;
		padding: 2px 7px;
		white-space: nowrap;
	}
	.due-now {
		color: #fb923c;
		background: #2a1800;
	}

	/* ── Misc ── */
	.muted {
		color: #555;
		font-size: 0.85rem;
	}
	.error {
		color: #f87171;
		text-align: center;
		line-height: 1.5;
	}
	.complete-icon {
		font-size: 4rem;
	}
	h2 {
		font-size: 1.2rem;
		font-weight: 700;
		text-align: center;
	}

	.reset-btn {
		background: #1e1e1e;
		color: #888;
		border: 1px solid #333;
		border-radius: 8px;
		padding: 0.6rem 1.4rem;
		font-size: 0.85rem;
		cursor: pointer;
		transition:
			color 0.15s,
			border-color 0.15s;
	}
	.reset-btn:hover {
		color: #ddd;
		border-color: #555;
	}
	.reset-btn.small {
		padding: 0.4rem 1rem;
	}

	.spinner {
		width: 32px;
		height: 32px;
		border: 3px solid #222;
		border-top-color: #555;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
