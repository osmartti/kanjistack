<script>
	import { onMount, tick } from "svelte";
	import { get, set } from "idb-keyval";
	import { fade, fly } from "svelte/transition";
	import Menu from "./lib/Menu.svelte";
	import CookieBanner from "./lib/CookieBanner.svelte";

	// If user previously accepted, load GA immediately on page load
	if (typeof localStorage !== "undefined" && localStorage.getItem("cookie_consent") === "accepted") {
		const gaScript = document.createElement("script");
		gaScript.async = true;
		gaScript.src = "https://www.googletagmanager.com/gtag/js?id=G-QQNTTVYMBC";
		document.head.appendChild(gaScript);
		window.dataLayer = window.dataLayer || [];
		function gtag() {
			window.dataLayer.push(arguments);
		}
		window.gtag = gtag;
		gtag("js", new Date());
		gtag("config", "G-QQNTTVYMBC");
	}

	const WINDOW_SIZE = 30;
	const DB_KEY = "kanjistack_v2";  // bumped: list now sorted by difficulty
	const LANG_NAMES = {
		en: "English",
		fr: "Français",
		es: "Español",
		pt: "Português",
	};

	let kanjiList = [];
	let loading = true;
	let loadError = null;
	let availableLangs = ["en"];

	let windowKanji = [];
	let queueKanji = [];
	let droppedCount = 0;
	let currentPos = 0;
	let selectedLang = "en";
	let learnedKanji = [];
	let readingLearned = {};
	let starredKanji = [];
	let isDark = true;

	let page = "learn";
	let revealed = false;
	let showInfo = false;
	let showVocabInfo = false;

	let weightMap = {};
	let seenSet = new Set();
	let lastKanjiIndex = -1;
	let isRepeat = false;

	let dropFly = null;
	let showDropFly = false;
	let dropFlyTimer = null;

	let touchStartX = 0;
	let touchStartY = 0;
	let swipeDeltaX = 0;
	let swipeActive = false;

	let showOnboarding = false;
	let onboardingDone = false;
	let reviewPos = 0;
	let reviewRevealed = false;
	let reviewLevels = new Set([4, 3, 2, 1]);
	let reviewStarted = false;
	let reviewQueue = [];
	let reviewSwipeDeltaX = 0;
	let reviewSwipeActive = false;
	let reviewTouchStartX = 0;
	let reviewTouchStartY = 0;
	let listTouchId = null;
	let listTouchStartX = 0;
	let listTouchStartY = 0;
	let listDeltaX = 0;
	let listSwipeActive = false;

	// KANJIDIC2 uses old 4-level JLPT (4=easiest=N5, 1=hardest≈N1/N2)
	const JLPT_MAP = { 4: "N5", 3: "N4", 2: "N2/N3", 1: "N1/N2" };

	// Vocab JLPT: stored as 5=N5…2=N2/N1
	const VOCAB_DB_KEY = "kanjistack_vocab_v2";  // bumped with kanji v2
	const VOCAB_JLPT_MAP = { 5: "N5", 4: "N4", 3: "N3", 2: "N2/N1" };

	let vocabList = [];
	let vocabLoading = true;
	let vocabLoadError = null;
	let vocabMode = false; // false=kanji, true=vocab

	let vWindowVocab = [];
	let queueVocab = [];
	let vDroppedCount = 0;
	let vCurrentPos = 0;
	let vLearnedVocab = [];
	let vWeightMap = {};
	let vSeenSet = new Set();
	let vLastIdx = -1;
	let vIsRepeat = false;
	let starredVocab = [];
	let vOnboardingDone = false;
	let showVocabOnboarding = false;

	let vRevealed = false;
	let vFuriganaRevealed = false;
	let vSwipeDeltaX = 0;
	let vSwipeActive = false;
	let vTouchStartX = 0;
	let vTouchStartY = 0;

	let vReviewPos = 0;
	let vReviewRevealed = false;
	let vReviewFuriganaRevealed = false;
	let vReviewLevels = new Set([5, 4, 3, 2]); // selected JLPT levels for review
	let vReviewStarted = false;
	let vReviewQueue = []; // filtered subset of vLearnedVocab indices
	let vReviewSwipeDeltaX = 0;
	let vReviewSwipeActive = false;
	let vReviewTouchStartX = 0;
	let vReviewTouchStartY = 0;

	function vocabWordStyle(word) {
		const len = [...(word ?? "")].length || 1;
		return `--wlen: ${len};`;
	}

	function getFlyParams(targetSel) {
		const kanjiEl = document.querySelector(".kanji-char");
		const targetEl = document.querySelector(targetSel);
		if (!kanjiEl || !targetEl) return null;
		const kr = kanjiEl.getBoundingClientRect();
		const tr = targetEl.getBoundingClientRect();
		return {
			x: kr.left + kr.width / 2,
			y: kr.top + kr.height / 2,
			dx: tr.left + tr.width / 2 - (kr.left + kr.width / 2),
			dy: tr.top + tr.height / 2 - (kr.top + kr.height / 2),
		};
	}

	$: safePos = windowKanji.length
		? Math.min(currentPos, windowKanji.length - 1)
		: 0;
	$: currentKanjiIdx = windowKanji[safePos] ?? -1;
	$: current = currentKanjiIdx >= 0 ? kanjiList[currentKanjiIdx] : null;
	$: onyomi = current?.on ?? [];
	$: kunyomi = current?.kun ?? [];
	$: meanings =
		current?.meanings?.[selectedLang] ?? current?.meanings?.en ?? [];
	$: complete =
		!loading &&
		kanjiList.length > 0 &&
		windowKanji.length === 0 &&
		queueKanji.length === 0;
	$: learnedCount = Math.max(droppedCount, learnedKanji.length);
	$: progressPct = kanjiList.length
		? Math.min(100, (learnedCount / kanjiList.length) * 100)
		: 0;
	$: if (typeof document !== "undefined") {
		document.body.classList.toggle("light", !isDark);
	}

	// Vocab derived
	$: vSafePos = vWindowVocab.length ? Math.min(vCurrentPos, vWindowVocab.length - 1) : 0;
	$: vCurrentIdx = vWindowVocab[vSafePos] ?? -1;
	$: vCurrent = vCurrentIdx >= 0 ? vocabList[vCurrentIdx] : null;
	$: vLearnedCount = Math.max(vDroppedCount, vLearnedVocab.length);
	$: vProgressPct = vocabList.length ? Math.min(100, (vLearnedCount / vocabList.length) * 100) : 0;
	$: vComplete = !vocabLoading && vocabList.length > 0 && vWindowVocab.length === 0 && queueVocab.length === 0;
	$: vReviewEntry = vReviewQueue.length ? vocabList[vReviewQueue[Math.min(vReviewPos, vReviewQueue.length - 1)]] : null;
	$: vReviewIdx = vReviewQueue.length ? vReviewQueue[Math.min(vReviewPos, vReviewQueue.length - 1)] : -1;

	async function saveState() {
		try {
			await set(DB_KEY, {
				windowKanji,
				queueKanji,
				droppedCount,
				currentPos,
				selectedLang,
				weightMap,
				seenIndices: [...seenSet],
				lastKanjiIndex,
				learnedKanji,
				readingLearned,
				starredKanji,
				isDark,
				onboardingDone,
			});
		} catch (e) {
			console.warn("saveState failed:", e);
		}
	}

	async function loadState() {
		try {
			const s = await get(DB_KEY);
			if (s) {
				windowKanji = s.windowKanji ?? [];
				learnedKanji = s.learnedKanji ?? [];
				if (Array.isArray(s.queueKanji)) {
					queueKanji = s.queueKanji;
				} else {
					// Migrating from the old sequential-pointer format
					// (nextKanjiIndex): rebuild an equivalent queue.
					const legacyNext = s.nextKanjiIndex ?? windowKanji.length;
					const learnedSetTmp = new Set(learnedKanji);
					const windowSetTmp = new Set(windowKanji);
					queueKanji = [];
					for (let i = legacyNext; i < kanjiList.length; i++) {
						if (!learnedSetTmp.has(i) && !windowSetTmp.has(i))
							queueKanji.push(i);
					}
				}
				droppedCount = s.droppedCount ?? 0;
				currentPos = s.currentPos ?? 0;
				selectedLang = s.selectedLang ?? "en";
				weightMap = s.weightMap ?? {};
				seenSet = new Set(s.seenIndices ?? []);
				lastKanjiIndex = s.lastKanjiIndex ?? -1;
				readingLearned = s.readingLearned ?? {};
				// Older saves won't have starredKanji at all — treat as none starred.
				starredKanji = Array.isArray(s.starredKanji) ? s.starredKanji : [];
				isDark = s.isDark ?? true;
				onboardingDone = s.onboardingDone ?? false;
				droppedCount = Math.max(droppedCount, learnedKanji.length);
				if (!onboardingDone && learnedKanji.length === 0)
					showOnboarding = true;
			} else {
				initFresh();
			}
		} catch (e) {
			console.warn("loadState failed, starting fresh:", e);
			initFresh();
		}
	}

	function initFresh() {
		const count = Math.min(WINDOW_SIZE, kanjiList.length);
		windowKanji = Array.from({ length: count }, (_, i) => i);
		queueKanji = Array.from(
			{ length: Math.max(0, kanjiList.length - count) },
			(_, i) => i + count,
		);
		droppedCount = 0;
		currentPos = 0;
		weightMap = {};
		seenSet = new Set();
		lastKanjiIndex = -1;
		learnedKanji = [];
		readingLearned = {};
		starredKanji = [];
		isDark = true;
		isRepeat = false;
		swipeDeltaX = 0;
		swipeActive = false;
		onboardingDone = false;
		showOnboarding = true;
		reviewPos = 0;
		reviewRevealed = false;
	}

	function addNext() {
		if (queueKanji.length > 0) {
			const idx = queueKanji[0];
			queueKanji = queueKanji.slice(1);
			windowKanji = [...windowKanji, idx];
		}
	}

	// Inserts idx back into a queue at a random position within the next
	// "batch" (the upcoming windowSize items), instead of appending at the
	// very end — so a "Still Learning" item resurfaces before too long. Since
	// the window is a FIFO and this only bounds a *relative* position (not an
	// absolute turn), heavy sustained "Still Learning" use can keep pushing
	// an item back further via later insertions — intentional: the ~30-60
	// window only holds under normal use, and naturally grows unbounded if a
	// user is stuck relearning many items at once, rather than forcing a
	// hard cap that would surface it before the user actually knows it.
	function shuffleIntoQueue(queue, idx, windowSize) {
		const maxPos = Math.min(windowSize, queue.length);
		const pos = Math.floor(Math.random() * (maxPos + 1));
		return [...queue.slice(0, pos), idx, ...queue.slice(pos)];
	}

	// ── Vocab save/load/init ─────────────────────────────────────────────────
	async function saveVocabState() {
		try {
			await set(VOCAB_DB_KEY, {
				vWindowVocab, queueVocab, vDroppedCount, vCurrentPos,
				vLearnedVocab, vWeightMap, starredVocab,
				vSeenIndices: [...vSeenSet], vLastIdx, vOnboardingDone,
			});
		} catch (e) { console.warn("saveVocabState failed:", e); }
	}

	async function loadVocabState() {
		try {
			const s = await get(VOCAB_DB_KEY);
			if (s) {
				vWindowVocab = s.vWindowVocab ?? [];
				vLearnedVocab = s.vLearnedVocab ?? [];
				if (Array.isArray(s.queueVocab)) {
					queueVocab = s.queueVocab;
				} else {
					// Migrating from the old sequential-pointer format
					// (vNextIdx): rebuild an equivalent queue.
					const legacyNext = s.vNextIdx ?? vWindowVocab.length;
					const learnedSetTmp = new Set(vLearnedVocab);
					const windowSetTmp = new Set(vWindowVocab);
					queueVocab = [];
					for (let i = legacyNext; i < vocabList.length; i++) {
						if (!learnedSetTmp.has(i) && !windowSetTmp.has(i))
							queueVocab.push(i);
					}
				}
				vDroppedCount = s.vDroppedCount ?? 0;
				vCurrentPos = s.vCurrentPos ?? 0;
				vWeightMap = s.vWeightMap ?? {};
				vSeenSet = new Set(s.vSeenIndices ?? []);
				vLastIdx = s.vLastIdx ?? -1;
				// Older saves won't have starredVocab at all — treat as none starred.
				starredVocab = Array.isArray(s.starredVocab) ? s.starredVocab : [];
				vOnboardingDone = s.vOnboardingDone ?? false;
				vDroppedCount = Math.max(vDroppedCount, vLearnedVocab.length);
				if (!vOnboardingDone && vLearnedVocab.length === 0) showVocabOnboarding = true;
			} else {
				initVocabFresh();
			}
		} catch (e) { initVocabFresh(); }
	}

	function initVocabFresh() {
		const count = Math.min(WINDOW_SIZE, vocabList.length);
		vWindowVocab = Array.from({ length: count }, (_, i) => i);
		queueVocab = Array.from(
			{ length: Math.max(0, vocabList.length - count) },
			(_, i) => i + count,
		);
		vDroppedCount = 0; vCurrentPos = 0;
		vWeightMap = {}; vSeenSet = new Set(); vLastIdx = -1;
		vLearnedVocab = [];
		starredVocab = [];
		vOnboardingDone = false;
		showVocabOnboarding = true;
		vIsRepeat = false; vSwipeDeltaX = 0; vSwipeActive = false;
		vReviewPos = 0; vReviewRevealed = false; vReviewFuriganaRevealed = false;
		vRevealed = false; vFuriganaRevealed = false;
	}

	// ── Vocab window helpers ─────────────────────────────────────────────────
	function vAddNext() {
		if (queueVocab.length > 0) {
			const idx = queueVocab[0];
			queueVocab = queueVocab.slice(1);
			vWindowVocab = [...vWindowVocab, idx];
		}
	}
	function vRemoveCurrent() {
		vWindowVocab = vWindowVocab.filter((_, i) => i !== vCurrentPos);
		if (vWindowVocab.length === 0) vCurrentPos = 0;
		else if (vCurrentPos >= vWindowVocab.length) vCurrentPos = 0;
	}
	function vPickNextPos() {
		return 0;
	}
	function vCheckIfRepeat() {
		if (!vWindowVocab.length) { vIsRepeat = false; return; }
		const idx = vWindowVocab[Math.min(vCurrentPos, vWindowVocab.length - 1)];
		if (idx === undefined) { vIsRepeat = false; return; }
		if (vSeenSet.has(idx)) { vIsRepeat = true; return; }
		vSeenSet.add(idx); vIsRepeat = false;
	}

	// ── Vocab touch handlers ─────────────────────────────────────────────────
	function onVTouchStart(e) {
		vTouchStartX = e.touches[0].clientX; vTouchStartY = e.touches[0].clientY;
		vSwipeDeltaX = 0; vSwipeActive = true;
	}
	function onVTouchMove(e) {
		if (!vSwipeActive) return;
		const dx = e.touches[0].clientX - vTouchStartX;
		const dy = e.touches[0].clientY - vTouchStartY;
		const prev = vSwipeDeltaX;
		if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 8) {
			vSwipeDeltaX = dx;
			if (Math.abs(prev) < 60 && Math.abs(vSwipeDeltaX) >= 60) vibrate(10);
		}
	}
	function onVTouchEnd() {
		if (!vSwipeActive) return; vSwipeActive = false;
		if (vSwipeDeltaX > 60) onVKnowIt();
		else if (vSwipeDeltaX < -60) onVStillLearning();
		else vSwipeDeltaX = 0;
	}
	function onVReviewTouchStart(e) {
		vReviewTouchStartX = e.touches[0].clientX; vReviewTouchStartY = e.touches[0].clientY;
		vReviewSwipeDeltaX = 0; vReviewSwipeActive = true;
	}
	function onVReviewTouchMove(e) {
		if (!vReviewSwipeActive) return;
		const dx = e.touches[0].clientX - vReviewTouchStartX;
		const dy = e.touches[0].clientY - vReviewTouchStartY;
		const prev = vReviewSwipeDeltaX;
		if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 8) {
			vReviewSwipeDeltaX = dx;
			if (Math.abs(prev) < 60 && Math.abs(vReviewSwipeDeltaX) >= 60) vibrate(10);
		}
	}
	function unstarCurrentReviewVocab() {
		toggleStarVocab(vReviewIdx);
		vReviewQueue = vReviewQueue.filter((i) => i !== vReviewIdx);
		vReviewPos = Math.min(vReviewPos, Math.max(0, vReviewQueue.length - 1));
		vReviewRevealed = false;
		vReviewFuriganaRevealed = false;
	}
	function onVReviewTouchEnd() {
		if (!vReviewSwipeActive) return; vReviewSwipeActive = false;
		if (vReviewSwipeDeltaX > 60) vNextReview();
		else if (
			vReviewSwipeDeltaX < -60 &&
			(page !== "review-vocab-starred" || vLearnedVocab.includes(vReviewIdx))
		) {
			onVUnlearn(vReviewIdx); vNextReview();
		}
		else vReviewSwipeDeltaX = 0;
	}

	// ── Vocab game actions ───────────────────────────────────────────────────
	async function onVKnowIt() {
		vibrate([15, 60, 15]); // double pulse = success
		vSwipeDeltaX = 0;
		const idx = vWindowVocab[Math.min(vCurrentPos, vWindowVocab.length - 1)];
		if (!vLearnedVocab.includes(idx)) {
			vLearnedVocab = [...vLearnedVocab, idx];
			vDroppedCount = Math.max(vDroppedCount + 1, vLearnedVocab.length);
		}
		vLastIdx = idx ?? -1;
		vRemoveCurrent(); vAddNext();
		vCurrentPos = vPickNextPos(); vCheckIfRepeat();
		vRevealed = false; vFuriganaRevealed = false;
		await saveVocabState();
	}
	async function onVStillLearning() {
		vibrate(25); // single pulse = keep going
		vSwipeDeltaX = 0;
		const posNow = Math.min(vCurrentPos, vWindowVocab.length - 1);
		const idxNow = vWindowVocab[posNow];
		vWeightMap = { ...vWeightMap, [idxNow]: (vWeightMap[idxNow] ?? 1) + 1 };
		vLastIdx = idxNow;
		vRemoveCurrent(); vAddNext();
		queueVocab = shuffleIntoQueue(queueVocab, idxNow, WINDOW_SIZE);
		vCurrentPos = vPickNextPos(); vCheckIfRepeat();
		vRevealed = false; vFuriganaRevealed = false;
		await saveVocabState();
	}
	async function onVUnlearn(idx) {
		vLearnedVocab = vLearnedVocab.filter((i) => i !== idx);
		vDroppedCount = Math.max(0, vDroppedCount - 1);
		if (!vWindowVocab.includes(idx)) vWindowVocab = [idx, ...vWindowVocab];
		await saveVocabState();
	}

	function toggleStarVocab(vIdx) {
		if (vIdx == null || vIdx < 0) return;
		starredVocab = starredVocab.includes(vIdx)
			? starredVocab.filter((i) => i !== vIdx)
			: [...starredVocab, vIdx];
		saveVocabState();
	}

	async function selectVocabOnboardingLevel(jlptLevels) {
		if (jlptLevels.length > 0) {
			const toLearn = vocabList
				.map((v, idx) => ({ v, idx }))
				.filter(({ v }) => jlptLevels.includes(v.jlpt))
				.map(({ idx }) => idx);
			vLearnedVocab = [...new Set([...vLearnedVocab, ...toLearn])];
			vDroppedCount = vLearnedVocab.length;
			vWindowVocab = vWindowVocab.filter((idx) => !toLearn.includes(idx));
			queueVocab = queueVocab.filter((idx) => !toLearn.includes(idx));
			while (vWindowVocab.length < WINDOW_SIZE && queueVocab.length > 0) {
				vWindowVocab = [...vWindowVocab, queueVocab[0]];
				queueVocab = queueVocab.slice(1);
			}
			vCurrentPos = 0;
		}
		vOnboardingDone = true; showVocabOnboarding = false;
		await saveVocabState();
	}

	function vNextReview() {
		if (!vReviewQueue.length) return;
		vReviewRevealed = false; vReviewFuriganaRevealed = false; vReviewSwipeDeltaX = 0;
		vReviewPos = (vReviewPos + 1) % vReviewQueue.length;
	}

	function startVocabReview() {
		const q = vLearnedVocab.filter((idx) => {
			const v = vocabList[idx];
			return v && vReviewLevels.has(v.jlpt);
		});
		// Fisher-Yates shuffle
		for (let i = q.length - 1; i > 0; i--) {
			const j = Math.floor(Math.random() * (i + 1));
			[q[i], q[j]] = [q[j], q[i]];
		}
		vReviewQueue = q;
		vReviewPos = 0;
		vReviewRevealed = false; vReviewFuriganaRevealed = false;
		vReviewStarted = true;
	}

	function startVocabStarredReview() {
		const q = [...starredVocab];
		for (let i = q.length - 1; i > 0; i--) {
			const j = Math.floor(Math.random() * (i + 1));
			[q[i], q[j]] = [q[j], q[i]];
		}
		vReviewQueue = q;
		vReviewPos = 0;
		vReviewRevealed = false; vReviewFuriganaRevealed = false;
		vReviewStarted = true;
	}

	function toggleVReviewLevel(lvl) {
		vReviewLevels = new Set(vReviewLevels);
		if (vReviewLevels.has(lvl)) vReviewLevels.delete(lvl);
		else vReviewLevels.add(lvl);
	}

	function removeCurrent() {
		windowKanji = windowKanji.filter((_, i) => i !== currentPos);
		if (windowKanji.length === 0) currentPos = 0;
		else if (currentPos >= windowKanji.length) currentPos = 0;
	}

	// The window is treated as a FIFO queue: removeCurrent() pops the shown
	// item and addNext()/shuffleIntoQueue() pushes the next one to the back,
	// so the next card to show is always the one now at the front (index 0).
	function pickNextPos() {
		return 0;
	}

	function checkIfRepeat() {
		if (!windowKanji.length) {
			isRepeat = false;
			return;
		}
		const idx = windowKanji[Math.min(currentPos, windowKanji.length - 1)];
		if (idx === undefined) {
			isRepeat = false;
			return;
		}
		if (seenSet.has(idx)) {
			isRepeat = true;
			return;
		}
		seenSet.add(idx);
		isRepeat = false;
	}

	function handleTap() {
		if (showInfo) { showInfo = false; return; }
		if (!revealed) revealed = true;
	}

	function onTouchStart(e) {
		touchStartX = e.touches[0].clientX;
		touchStartY = e.touches[0].clientY;
		swipeDeltaX = 0;
		swipeActive = true;
	}

	function onTouchMove(e) {
		if (!swipeActive) return;
		const dx = e.touches[0].clientX - touchStartX;
		const dy = e.touches[0].clientY - touchStartY;
		const prevDelta = swipeDeltaX;
		if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 8) {
			swipeDeltaX = dx;
			// Haptic tick when crossing the action threshold
			if (Math.abs(prevDelta) < 60 && Math.abs(swipeDeltaX) >= 60) vibrate(10);
		}
	}

	function onTouchEnd() {
		if (!swipeActive) return;
		swipeActive = false;
		if (swipeDeltaX > 60) onKnowIt();
		else if (swipeDeltaX < -60) onStillLearning();
		else swipeDeltaX = 0;
	}

	// ── List swipe (learned list) ────────────────────────────────────────────
	function onListTouchStart(e, id) {
		listTouchId = id;
		listTouchStartX = e.touches[0].clientX;
		listTouchStartY = e.touches[0].clientY;
		listDeltaX = 0;
		listSwipeActive = true;
	}
	function onListTouchMove(e) {
		if (!listSwipeActive) return;
		const dx = e.touches[0].clientX - listTouchStartX;
		const dy = e.touches[0].clientY - listTouchStartY;
		if (Math.abs(dx) > Math.abs(dy)) listDeltaX = dx;
	}
	function onListTouchEnd() {
		if (!listSwipeActive) return;
		listSwipeActive = false;
		if (listDeltaX > 60 && listTouchId !== null) onUnlearn(listTouchId);
		listTouchId = null;
		listDeltaX = 0;
	}

	// ── Onboarding level selection ───────────────────────────────────────────
	async function selectOnboardingLevel(jlptLevels) {
		if (jlptLevels.length > 0) {
			const toLearn = kanjiList
				.map((k, idx) => ({ k, idx }))
				.filter(({ k }) => jlptLevels.includes(k.jlpt))
				.map(({ idx }) => idx);
			learnedKanji = [...new Set([...learnedKanji, ...toLearn])];
			droppedCount = learnedKanji.length;
			windowKanji = windowKanji.filter((idx) => !toLearn.includes(idx));
			queueKanji = queueKanji.filter((idx) => !toLearn.includes(idx));
			while (windowKanji.length < WINDOW_SIZE && queueKanji.length > 0) {
				windowKanji = [...windowKanji, queueKanji[0]];
				queueKanji = queueKanji.slice(1);
			}
			currentPos = 0;
		}
		onboardingDone = true;
		showOnboarding = false;
		await saveState();
	}

	// ── Review learned navigation ────────────────────────────────────────────
	$: reviewKanji = reviewQueue.length
		? kanjiList[reviewQueue[Math.min(reviewPos, reviewQueue.length - 1)]]
		: null;
	$: reviewKanjiIdx = reviewQueue.length
		? reviewQueue[Math.min(reviewPos, reviewQueue.length - 1)]
		: -1;
	function toggleKanjiReviewLevel(lvl) {
		const s = new Set(reviewLevels);
		if (s.has(lvl)) s.delete(lvl); else s.add(lvl);
		reviewLevels = s;
	}
	function startKanjiReview() {
		const q = learnedKanji.filter(i => reviewLevels.has(kanjiList[i]?.jlpt ?? 0));
		// Fisher-Yates shuffle
		for (let i = q.length - 1; i > 0; i--) {
			const j = Math.floor(Math.random() * (i + 1));
			[q[i], q[j]] = [q[j], q[i]];
		}
		reviewQueue = q;
		reviewPos = 0;
		reviewRevealed = false;
		reviewStarted = true;
	}
	function startKanjiStarredReview() {
		const q = [...starredKanji];
		for (let i = q.length - 1; i > 0; i--) {
			const j = Math.floor(Math.random() * (i + 1));
			[q[i], q[j]] = [q[j], q[i]];
		}
		reviewQueue = q;
		reviewPos = 0;
		reviewRevealed = false;
		reviewStarted = true;
	}
	function nextReview() {
		if (!reviewQueue.length) return;
		reviewRevealed = false;
		reviewSwipeDeltaX = 0;
		reviewPos = (reviewPos + 1) % reviewQueue.length;
	}
	function prevReview() {
		if (!reviewQueue.length) return;
		reviewRevealed = false;
		reviewSwipeDeltaX = 0;
		reviewPos = (reviewPos - 1 + reviewQueue.length) % reviewQueue.length;
	}

	function onReviewTouchStart(e) {
		reviewTouchStartX = e.touches[0].clientX;
		reviewTouchStartY = e.touches[0].clientY;
		reviewSwipeDeltaX = 0;
		reviewSwipeActive = true;
	}
	function onReviewTouchMove(e) {
		if (!reviewSwipeActive) return;
		const dx = e.touches[0].clientX - reviewTouchStartX;
		const dy = e.touches[0].clientY - reviewTouchStartY;
		if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 8)
			reviewSwipeDeltaX = dx;
	}
	function unstarCurrentReviewKanji() {
		toggleStarKanji(reviewKanjiIdx);
		reviewQueue = reviewQueue.filter((i) => i !== reviewKanjiIdx);
		reviewPos = Math.min(reviewPos, Math.max(0, reviewQueue.length - 1));
		reviewRevealed = false;
	}
	function onReviewTouchEnd() {
		if (!reviewSwipeActive) return;
		reviewSwipeActive = false;
		if (reviewSwipeDeltaX > 60) nextReview();
		else if (
			reviewSwipeDeltaX < -60 &&
			(page !== "review-starred" || learnedKanji.includes(reviewKanjiIdx))
		) {
			onUnlearn(reviewKanjiIdx);
			nextReview();
		} else reviewSwipeDeltaX = 0;
	}

	async function onKnowIt() {
		vibrate([15, 60, 15]);
		swipeDeltaX = 0;
		const kanjiIdx =
			windowKanji[Math.min(currentPos, windowKanji.length - 1)];
		const alreadyLearned = learnedKanji.includes(kanjiIdx);
		if (!alreadyLearned) {
			learnedKanji = [...learnedKanji, kanjiIdx];
			droppedCount = Math.max(droppedCount + 1, learnedKanji.length);
		}
		lastKanjiIndex = kanjiIdx ?? -1;

		dropFly = getFlyParams(".stat-wrap");
		showDropFly = false;
		await tick();
		showDropFly = true;
		clearTimeout(dropFlyTimer);
		dropFlyTimer = setTimeout(() => {
			showDropFly = false;
		}, 1200);

		removeCurrent();
		addNext();
		currentPos = pickNextPos();
		checkIfRepeat();
		revealed = false;
		await saveState();
	}

	async function onStillLearning() {
		vibrate(25);
		swipeDeltaX = 0;
		const posNow = Math.min(currentPos, windowKanji.length - 1);
		const idxNow = windowKanji[posNow];

		weightMap = { ...weightMap, [idxNow]: (weightMap[idxNow] ?? 1) + 1 };
		lastKanjiIndex = idxNow;

		removeCurrent();
		addNext();
		queueKanji = shuffleIntoQueue(queueKanji, idxNow, WINDOW_SIZE);

		currentPos = pickNextPos();
		checkIfRepeat();
		revealed = false;
		await saveState();
	}

	async function onUnlearn(kanjiIdx) {
		learnedKanji = learnedKanji.filter((idx) => idx !== kanjiIdx);
		droppedCount = Math.max(0, droppedCount - 1);
		if (!windowKanji.includes(kanjiIdx)) {
			windowKanji = [kanjiIdx, ...windowKanji];
		}
		await saveState();
	}

	function toggleStarKanji(kanjiIdx) {
		if (kanjiIdx == null || kanjiIdx < 0) return;
		starredKanji = starredKanji.includes(kanjiIdx)
			? starredKanji.filter((i) => i !== kanjiIdx)
			: [...starredKanji, kanjiIdx];
		saveState();
	}

	// readingLearned: { [kanjiIdx]: { on: {0: bool, ...}, kun: {0: bool, ...} } }
	function toggleReading(kanjiIdx, type, i) {
		const cur = readingLearned[kanjiIdx] ?? { on: {}, kun: {} };
		const typeMap = { ...cur[type] };
		typeMap[i] = !typeMap[i];
		readingLearned = {
			...readingLearned,
			[kanjiIdx]: { ...cur, [type]: typeMap },
		};
		saveState();
	}

	function vibrate(pattern) {
		try { navigator.vibrate?.(pattern); } catch (_) {}
	}

	function navigate(p) {
		page = p;
		showInfo = false;
		showVocabInfo = false;
		swipeDeltaX = 0;
		swipeActive = false;
		if (p !== "review-vocab" && p !== "review-vocab-starred") vReviewStarted = false;
		if (p !== "review-learned" && p !== "review-starred") reviewStarted = false;
		if (p === "review-starred") startKanjiStarredReview();
		if (p === "review-vocab-starred") startVocabStarredReview();
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
			initVocabFresh();
			vocabMode = false;
			page = "learn";
			await Promise.all([saveState(), saveVocabState()]);
		}
	}

	// ── Progress export / import ─────────────────────────────────────────────
	// Builds a fresh learning window + upcoming queue (skipping already-learned
	// entries) starting from index 0 — used after importing progress, since we
	// intentionally do not preserve the exact window/weights across export/import.
	function buildFreshWindow(totalLength, learnedIdxs, windowSize) {
		const learnedSet = new Set(learnedIdxs);
		const win = [];
		const queue = [];
		for (let i = 0; i < totalLength; i++) {
			if (learnedSet.has(i)) continue;
			if (win.length < windowSize) win.push(i);
			else queue.push(i);
		}
		return { window: win, queue };
	}

	let dataStatus = null; // { type: 'success' | 'error', message: string }
	let dataFileInput;

	function buildProgressExport() {
		return {
			version: 1,
			exportedAt: new Date().toISOString(),
			kanji: {
				learned: learnedKanji,
				readingLearned,
				starred: starredKanji,
			},
			vocab: {
				learned: vLearnedVocab,
				starred: starredVocab,
			},
		};
	}

	function downloadProgress() {
		try {
			const data = buildProgressExport();
			const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			const stamp = new Date().toISOString().slice(0, 10);
			a.href = url;
			a.download = `kanjistack-progress-${stamp}.json`;
			document.body.appendChild(a);
			a.click();
			a.remove();
			URL.revokeObjectURL(url);
			dataStatus = { type: "success", message: "Progress downloaded." };
		} catch (e) {
			console.warn("downloadProgress failed:", e);
			dataStatus = { type: "error", message: "Could not download progress." };
		}
	}

	function triggerImport() {
		dataStatus = null;
		dataFileInput?.click();
	}

	async function handleImportFile(e) {
		const file = e.target.files?.[0];
		e.target.value = ""; // allow re-selecting the same file again later
		if (!file) return;

		if (!confirm("Uploading a file will overwrite your current progress. Continue?")) {
			return;
		}

		try {
			const text = await file.text();
			const parsed = JSON.parse(text);
			const importedLearnedKanji = Array.isArray(parsed?.kanji?.learned) ? parsed.kanji.learned : null;
			const importedLearnedVocab = Array.isArray(parsed?.vocab?.learned) ? parsed.vocab.learned : null;

			if (!importedLearnedKanji || !importedLearnedVocab) {
				throw new Error("File does not look like a KanjiStack progress export.");
			}

			// Apply kanji progress
			learnedKanji = [...new Set(importedLearnedKanji)].filter(
				(i) => Number.isInteger(i) && i >= 0 && i < kanjiList.length,
			);
			readingLearned = (parsed.kanji.readingLearned && typeof parsed.kanji.readingLearned === "object")
				? parsed.kanji.readingLearned
				: {};
			// Older exports won't have a `starred` field — treat as none starred.
			const importedStarredKanji = Array.isArray(parsed?.kanji?.starred) ? parsed.kanji.starred : [];
			starredKanji = [...new Set(importedStarredKanji)].filter(
				(i) => Number.isInteger(i) && i >= 0 && i < kanjiList.length,
			);
			const { window: freshWindow, queue: freshQueue } = buildFreshWindow(kanjiList.length, learnedKanji, WINDOW_SIZE);
			windowKanji = freshWindow;
			queueKanji = freshQueue;
			droppedCount = learnedKanji.length;
			currentPos = 0;
			weightMap = {};
			seenSet = new Set();
			lastKanjiIndex = -1;
			isRepeat = false;
			onboardingDone = true;
			showOnboarding = false;

			// Apply vocab progress
			vLearnedVocab = [...new Set(importedLearnedVocab)].filter(
				(i) => Number.isInteger(i) && i >= 0 && i < vocabList.length,
			);
			// Older exports won't have a `starred` field — treat as none starred.
			const importedStarredVocab = Array.isArray(parsed?.vocab?.starred) ? parsed.vocab.starred : [];
			starredVocab = [...new Set(importedStarredVocab)].filter(
				(i) => Number.isInteger(i) && i >= 0 && i < vocabList.length,
			);
			const { window: freshVWindow, queue: freshVQueue } = buildFreshWindow(vocabList.length, vLearnedVocab, WINDOW_SIZE);
			vWindowVocab = freshVWindow;
			queueVocab = freshVQueue;
			vDroppedCount = vLearnedVocab.length;
			vCurrentPos = 0;
			vWeightMap = {};
			vSeenSet = new Set();
			vLastIdx = -1;
			vIsRepeat = false;
			vOnboardingDone = true;
			showVocabOnboarding = false;

			await Promise.all([saveState(), saveVocabState()]);
			dataStatus = {
				type: "success",
				message: `Imported ${learnedKanji.length} kanji and ${vLearnedVocab.length} words.`,
			};
		} catch (err) {
			console.warn("handleImportFile failed:", err);
			dataStatus = {
				type: "error",
				message: "Could not import file. Make sure it's a valid KanjiStack progress export.",
			};
		}
	}

	onMount(async () => {
		try {
			const [kanjiRes, vocabRes] = await Promise.all([
				fetch(`${import.meta.env.BASE_URL}kanji.json`),
				fetch(`${import.meta.env.BASE_URL}vocab.json`),
			]);
			kanjiList = await kanjiRes.json();
			vocabList = await vocabRes.json();
			// Sort easiest → hardest so the sliding window progresses naturally.
			// Kanji JLPT: 4=N5 (easiest), 3=N4, 2=N3, 1=N1/N2, undefined=last
			kanjiList.sort((a, b) => (b.jlpt ?? 0) - (a.jlpt ?? 0));
			// Vocab JLPT: 5=N5, 4=N4, 3=N3, 2=N2/N1, already pre-sorted but enforce
			vocabList.sort((a, b) => (b.jlpt ?? 0) - (a.jlpt ?? 0));
			vocabLoadError = null;
			const langSet = new Set();
			for (const k of kanjiList) {
				if (k.meanings)
					Object.keys(k.meanings).forEach((lang) =>
						langSet.add(lang),
					);
			}
			availableLangs = [...langSet].sort((a, b) =>
				a === "en" ? -1 : b === "en" ? 1 : a.localeCompare(b),
			);
			await Promise.all([loadState(), loadVocabState()]);
			checkIfRepeat();
			vCheckIfRepeat();
		} catch (e) {
			console.error("onMount error:", e);
			loadError = `${e.constructor?.name ?? "Error"}: ${e.message}`;
		} finally {
			loading = false;
			vocabLoading = false;
		}
	});
</script>

{#if loading}
	<div class="screen center">
		<div class="spinner"></div>
		<p class="muted">Loading kanji…</p>
	</div>
{:else if loadError}
	<div class="screen center">
		<p class="error">Failed to load data.<br />{loadError}</p>
	</div>
{:else if complete && page === "learn"}
	<div class="screen center">
		<div class="complete-icon">🎉</div>
		<h2>All {kanjiList.length} Jōyō kanji mastered!</h2>
		<p class="muted">Incredible work.</p>
		<button class="reset-btn" on:click={confirmReset}>Start over</button>
	</div>
{:else if showOnboarding && page === "learn"}
	<div class="screen center onboarding">
		<h2 class="onboard-title">KanjiStack</h2>
		<p class="onboard-sub">What's your current kanji level?</p>
		<div class="onboard-grid">
			<button
				class="onboard-card"
				on:click={() => selectOnboardingLevel([])}
			>
				<span class="onboard-level">Beginner</span>
				<span class="onboard-desc"
					>Start fresh · No kanji pre-learned</span
				>
			</button>
			<button
				class="onboard-card"
				on:click={() => selectOnboardingLevel([4])}
			>
				<span class="onboard-level">N5</span>
				<span class="onboard-desc"
					>~{kanjiList.filter((k) => k.jlpt === 4).length} kanji pre-learned</span
				>
			</button>
			<button
				class="onboard-card"
				on:click={() => selectOnboardingLevel([4, 3])}
			>
				<span class="onboard-level">N4</span>
				<span class="onboard-desc"
					>~{kanjiList.filter((k) => k.jlpt >= 3).length} kanji pre-learned</span
				>
			</button>
			<button
				class="onboard-card"
				on:click={() => selectOnboardingLevel([4, 3, 2])}
			>
				<span class="onboard-level">N3</span>
				<span class="onboard-desc"
					>~{kanjiList.filter((k) => k.jlpt >= 2).length} kanji pre-learned</span
				>
			</button>
			<button
				class="onboard-card"
				on:click={() => selectOnboardingLevel([4, 3, 2, 1])}
			>
				<span class="onboard-level">N1/N2</span>
				<span class="onboard-desc"
					>~{kanjiList.filter((k) => k.jlpt != null).length} kanji pre-learned</span
				>
			</button>
		</div>
		<p class="onboard-note">
			Pre-learned kanji skip the learning window and go directly to your
			Learned list.
		</p>
		<button class="onboard-restore" on:click={() => navigate("data")}
			>Have a backup? Restore progress</button
		>
	</div>
{:else if page === "learn"}
	<div class="screen column">
		<div class="progress-track">
			<div class="progress-fill" style="width: {progressPct}%"></div>
		</div>

		<div class="stats-row">
			<div class="stat-wrap">
				<span class="stat-val">{learnedCount}</span>
				<span class="stat-lbl">/ {kanjiList.length} learned</span>
			</div>

			<div class="row-right">
				<button
					class="mode-toggle"
					on:click={() => { vocabMode = false; navigate("learn"); }}
					class:mode-active={!vocabMode}
				>Kanji</button>
				<button
					class="mode-toggle"
					on:click={() => { vocabMode = true; navigate("vocab-learn"); }}
					class:mode-active={vocabMode}
				>Vocab</button>
				<button
					class="icon-btn"
					on:click={() => { showInfo = !showInfo; }}
					aria-label="Info"
				>
					<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<circle cx="12" cy="12" r="10" />
						<line x1="12" y1="8" x2="12" y2="12" />
						<line x1="12" y1="16" x2="12.01" y2="16" />
					</svg>
				</button>

				<Menu
					{page}
					{isDark}
					{availableLangs}
					{selectedLang}
					{LANG_NAMES}
					{vocabMode}
					on:navigate={(e) => navigate(e.detail)}
					on:selectlang={(e) => selectLang(e.detail)}
					on:toggletheme={() => { isDark = !isDark; saveState(); }}
					on:reset={confirmReset}
				/>
			</div>

			{#if showInfo}
				<div class="info-panel" transition:fly={{ y: -10, duration: 200 }}>
					<p><strong>Know It!</strong> — Mark this kanji as learned and bring in a new one.</p>
					<p><strong>Still Learning</strong> — Send it back a bit and bring in a new one now.</p>
					<p>Tap to highlight individual on/kun readings.</p>
				</div>
			{/if}
		</div>

		<div
			class="card"
			role="button"
			tabindex="0"
			on:click={handleTap}
			on:keydown={(e) => e.key === "Enter" && handleTap()}
			on:touchstart|passive={onTouchStart}
			on:touchmove={onTouchMove}
			on:touchend={onTouchEnd}
			style="transform: translateX({Math.max(
				-100,
				Math.min(100, swipeDeltaX * 0.35),
			)}px); transition: {swipeActive ? 'none' : 'transform 0.3s ease'}"
		>
			<div class="card-inner">
				<button
					class="star-btn"
					class:starred={starredKanji.includes(currentKanjiIdx)}
					on:click|stopPropagation={() => toggleStarKanji(currentKanjiIdx)}
					aria-label={starredKanji.includes(currentKanjiIdx) ? "Unstar" : "Star"}
					aria-pressed={starredKanji.includes(currentKanjiIdx)}
				>{starredKanji.includes(currentKanjiIdx) ? "★" : "☆"}</button>

				{#if swipeActive && Math.abs(swipeDeltaX) > 20}
					<div
						class="swipe-overlay"
						class:swipe-right={swipeDeltaX > 0}
						class:swipe-left={swipeDeltaX < 0}
						style="opacity: {Math.min(
							0.35,
							Math.abs(swipeDeltaX) / 200,
						)}"
					></div>
				{/if}

				{#key currentKanjiIdx}
					<div class="kanji-char" in:fade={{ duration: 180 }}>
						{current?.l ?? ""}
					</div>
				{/key}

				{#if revealed}
					<div class="details">
						{#if meanings.length}
							<p class="meanings">{meanings.join(", ")}</p>
						{/if}
						{#if kunyomi.length}
							<div class="reading-row">
								<span class="r-label">Kun</span>
								<span class="r-texts">
									{#each kunyomi as r, i}
										{#if i > 0}<span class="r-sep">·</span
											>{/if}
										<button
											class="r-btn"
											class:r-learned={readingLearned?.[
												currentKanjiIdx
											]?.kun?.[i] ?? false}
											on:click|stopPropagation={() =>
												toggleReading(
													currentKanjiIdx,
													"kun",
													i,
												)}>{r}</button
										>
									{/each}
								</span>
							</div>
						{/if}
						{#if onyomi.length}
							<div class="reading-row">
								<span class="r-label">On</span>
								<span class="r-texts">
									{#each onyomi as r, i}
										{#if i > 0}<span class="r-sep">·</span
											>{/if}
										<button
											class="r-btn"
											class:r-learned={readingLearned?.[
												currentKanjiIdx
											]?.on?.[i] ?? false}
											on:click|stopPropagation={() =>
												toggleReading(
													currentKanjiIdx,
													"on",
													i,
												)}>{r}</button
										>
									{/each}
								</span>
							</div>
						{/if}
						{#if current?.ex?.kun || current?.ex?.on}
						<div class="reading-row ex-row">
							<span class="r-label">Ex</span>
							<div class="ex-block">
								{#if current.ex.kun}
									<div class="example">
										{#each current.ex.kun.f as part}
											{#if part[1]}<ruby>{part[0]}<rt>{part[1]}</rt></ruby>{:else}{part[0]}{/if}
										{/each}
									</div>
									{#if current.ex.kun.t?.en}
										<p class="ex-trans">{current.ex.kun.t.en}</p>
									{/if}
								{/if}
								{#if current.ex.on}
									<div class="example">
										{#each current.ex.on.f as part}
											{#if part[1]}<ruby>{part[0]}<rt>{part[1]}</rt></ruby>{:else}{part[0]}{/if}
										{/each}
									</div>
									{#if current.ex.on.t?.en}
										<p class="ex-trans">{current.ex.on.t.en}</p>
									{/if}
								{/if}
							</div>
						</div>
					{/if}
						{#if current?.jlpt}
							<span class="badge"
								>JLPT {JLPT_MAP[current.jlpt] ??
									`N${current.jlpt}`}</span
							>
						{/if}
						{#if current?.l}
							<a
								class="jisho-link"
								href="https://jisho.org/search/{current.l}%23kanji"
								target="_blank"
								rel="noopener noreferrer"
								on:click|stopPropagation
							>
								jisho.org ↗
							</a>
						{/if}
					</div>
				{:else}
					<p class="tap-hint">tap to reveal</p>
				{/if}
			</div>
		</div>

		<div class="btn-row" class:hidden={!revealed}>
			{#if revealed}
				<button
					class="action still-learning"
					on:click|stopPropagation={onStillLearning}
					in:fly={{ y: 48, duration: 240 }}>Still Learning</button
				>
				<button
					class="action know"
					on:click|stopPropagation={onKnowIt}
					in:fly={{ y: 48, duration: 240, delay: 40 }}
					>Know It!</button
				>
			{/if}
		</div>

		{#if showDropFly && dropFly}
			<div
				class="fly-badge fly-green"
				style="left:{dropFly.x}px; top:{dropFly.y}px; --dx:{dropFly.dx}px; --dy:{dropFly.dy}px"
			>
				+1
			</div>
		{/if}
	</div>
{:else if page === "stack-current"}
	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => navigate("learn")}
				>‹ Back</button
			>
			<span class="sub-title">Current Stack</span>
			<span class="sub-count">{windowKanji.length}</span>
			<Menu
				{page}
				{isDark}
				{availableLangs}
				{selectedLang}
				{LANG_NAMES}
				{vocabMode}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
				on:toggletheme={() => {
					isDark = !isDark;
					saveState();
				}}
				on:reset={confirmReset}
			/>
		</div>

		<div class="stack-list">
			{#if windowKanji.length === 0}
				<p class="stack-empty">Nothing here yet.</p>
			{:else}
				{#each windowKanji as kanjiIdx}
					{@const kanji = kanjiList[kanjiIdx]}
					{#if kanji}
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
						</div>
					{/if}
				{/each}
			{/if}
		</div>
	</div>
{:else if page === "vocab-stack-current"}
	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => navigate("vocab-learn")}
				>‹ Back</button
			>
			<span class="sub-title">Current Stack</span>
			<span class="sub-count">{vWindowVocab.length}</span>
			<Menu
				{page}
				{isDark}
				{availableLangs}
				{selectedLang}
				{LANG_NAMES}
				{vocabMode}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
				on:toggletheme={() => {
					isDark = !isDark;
					saveState();
				}}
				on:reset={confirmReset}
			/>
		</div>

		<div class="stack-list">
			{#if vWindowVocab.length === 0}
				<p class="stack-empty">Nothing here yet.</p>
			{:else}
				{#each vWindowVocab as vIdx}
					{@const v = vocabList[vIdx]}
					{#if v}
						<div class="stack-item">
							<span class="stack-kanji">{v.w}</span>
							<div class="stack-info">
								<span class="stack-meaning">{v.m.slice(0, 3).join(", ")}</span>
								<span class="stack-readings">{v.r}</span>
							</div>
						</div>
					{/if}
				{/each}
			{/if}
		</div>
	</div>
{:else if page === "stack-learned"}
	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => navigate("learn")}
				>‹ Back</button
			>
			<span class="sub-title">Learned</span>
			<span class="sub-count">{learnedKanji.length}</span>
			<Menu
				{page}
				{isDark}
				{availableLangs}
				{selectedLang}
				{LANG_NAMES}
				{vocabMode}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
				on:toggletheme={() => {
					isDark = !isDark;
					saveState();
				}}
				on:reset={confirmReset}
			/>
		</div>
		<div class="stack-list">
			{#if learnedKanji.length === 0}
				<p class="stack-empty">
					No kanji learned yet.<br />Press "Know It!" to mark kanji as
					learned.
				</p>
			{:else}
				{#each [...learnedKanji].reverse() as kanjiIdx}
					{@const k = kanjiList[kanjiIdx]}
					{#if k}
						<div
							class="stack-item"
							style={listTouchId === kanjiIdx
								? `transform: translateX(${Math.min(120, Math.max(0, listDeltaX * 0.4))}px); transition: none; background: rgba(220,38,38,${Math.min(0.25, Math.max(0, listDeltaX) / 300)})`
								: ""}
							on:touchstart|passive={(e) =>
								onListTouchStart(e, kanjiIdx)}
							on:touchmove={onListTouchMove}
							on:touchend={onListTouchEnd}
						>
							<span class="stack-kanji">{k.l}</span>
							<div class="stack-info">
								<span class="stack-meaning"
									>{(
										k.meanings?.[selectedLang] ??
										k.meanings?.en ??
										[]
									)
										.slice(0, 3)
										.join(", ")}</span
								>
								<span class="stack-readings"
									>{[...(k.on ?? []), ...(k.kun ?? [])]
										.slice(0, 4)
										.join("  ·  ")}</span
								>
							</div>
							<button
								class="unlearn-btn"
								on:click={() => onUnlearn(kanjiIdx)}
								title="Move back to learning">X</button
							>
						</div>
					{/if}
				{/each}
			{/if}
		</div>
	</div>
{:else if page === "stack-starred"}
	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => navigate("learn")}
				>‹ Back</button
			>
			<span class="sub-title">Starred</span>
			<span class="sub-count">{starredKanji.length}</span>
			<Menu
				{page}
				{isDark}
				{availableLangs}
				{selectedLang}
				{LANG_NAMES}
				{vocabMode}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
				on:toggletheme={() => {
					isDark = !isDark;
					saveState();
				}}
				on:reset={confirmReset}
			/>
		</div>
		<div class="stack-list">
			{#if starredKanji.length === 0}
				<p class="stack-empty">
					No starred kanji yet.<br />Tap the star on a card to add
					it here.
				</p>
			{:else}
				{#each [...starredKanji].reverse() as kanjiIdx}
					{@const k = kanjiList[kanjiIdx]}
					{#if k}
						<div class="stack-item">
							<span class="stack-kanji">{k.l}</span>
							<div class="stack-info">
								<span class="stack-meaning"
									>{(
										k.meanings?.[selectedLang] ??
										k.meanings?.en ??
										[]
									)
										.slice(0, 3)
										.join(", ")}</span
								>
								<span class="stack-readings"
									>{[...(k.on ?? []), ...(k.kun ?? [])]
										.slice(0, 4)
										.join("  ·  ")}</span
								>
							</div>
							<button
								class="unlearn-btn"
								on:click={() => toggleStarKanji(kanjiIdx)}
								title="Remove star">★</button
							>
						</div>
					{/if}
				{/each}
			{/if}
		</div>
	</div>
{:else if page === "review-learned"}
	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => { reviewStarted = false; navigate("learn"); }}
				>‹ Back</button
			>
			<span class="sub-title">Review Learned</span>
			<span class="sub-count"
				>{#if reviewStarted && reviewQueue.length}
					{Math.min(reviewPos + 1, reviewQueue.length)} / {reviewQueue.length}
				{:else}
					{learnedKanji.length} learned
				{/if}</span
			>
			<Menu
				{page}
				{isDark}
				{availableLangs}
				{selectedLang}
				{LANG_NAMES}
				{vocabMode}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
				on:toggletheme={() => {
					isDark = !isDark;
					saveState();
				}}
				on:reset={confirmReset}
			/>
		</div>
		{#if learnedKanji.length === 0}
			<div class="screen center">
				<p class="muted">No learned kanji yet.</p>
			</div>
		{:else if !reviewStarted}
			<div class="screen center">
				<p class="review-pick-title">Select levels to review</p>
				<div class="review-level-grid">
					{#each [[4,"N5"],[3,"N4"],[2,"N2/N3"],[1,"N1/N2"]] as [lvl, label]}
						{@const count = learnedKanji.filter(i => kanjiList[i]?.jlpt === lvl).length}
						<button
							class="review-level-btn"
							class:review-level-active={reviewLevels.has(lvl)}
							disabled={count === 0}
							on:click={() => toggleKanjiReviewLevel(lvl)}
						>
							<span class="rl-label">{label}</span>
							<span class="rl-count">{count} kanji</span>
						</button>
					{/each}
				</div>
				<button
					class="review-start-btn"
					disabled={learnedKanji.filter(i => kanjiList[i] && reviewLevels.has(kanjiList[i].jlpt ?? 0)).length === 0}
					on:click={startKanjiReview}
				>Review {learnedKanji.filter(i => kanjiList[i] && reviewLevels.has(kanjiList[i].jlpt ?? 0)).length} kanji</button>
			</div>
		{:else if reviewQueue.length === 0}
			<div class="screen center"><p class="muted">No kanji match the selected levels.</p></div>
		{:else}
			<div
				class="card"
				role="button"
				tabindex="0"
				on:click={() => {
					reviewRevealed = !reviewRevealed;
				}}
				on:keydown={(e) =>
					e.key === "Enter" && (reviewRevealed = !reviewRevealed)}
				on:touchstart|passive={onReviewTouchStart}
				on:touchmove={onReviewTouchMove}
				on:touchend={onReviewTouchEnd}
				style="transform: translateX({Math.max(
					-100,
					Math.min(100, reviewSwipeDeltaX * 0.35),
				)}px); transition: {reviewSwipeActive
					? 'none'
					: 'transform 0.3s ease'}"
			>
				<div class="card-inner">
					{#if reviewSwipeActive && Math.abs(reviewSwipeDeltaX) > 20}
						<div
							class="swipe-overlay"
							class:swipe-right={reviewSwipeDeltaX > 0}
							class:swipe-left={reviewSwipeDeltaX < 0}
							style="opacity: {Math.min(
								0.35,
								Math.abs(reviewSwipeDeltaX) / 200,
							)}"
						></div>
					{/if}
					{#key reviewKanjiIdx}
						<div class="kanji-char" in:fade={{ duration: 180 }}>
							{reviewKanji?.l ?? ""}
						</div>
					{/key}
					{#if reviewRevealed}
						<div class="details">
							{#if (reviewKanji?.meanings?.[selectedLang] ?? reviewKanji?.meanings?.en ?? []).length}
								<p class="meanings">
									{(
										reviewKanji?.meanings?.[selectedLang] ??
										reviewKanji?.meanings?.en ??
										[]
									).join(", ")}
								</p>
							{/if}
							{#if (reviewKanji?.kun ?? []).length}
								<div class="reading-row">
									<span class="r-label">Kun</span>
									<span class="r-texts">
										{#each reviewKanji?.kun ?? [] as r, i}
											{#if i > 0}<span class="r-sep"
													>·</span
												>{/if}
											<button
												class="r-btn"
												class:r-learned={readingLearned?.[
													reviewKanjiIdx
												]?.kun?.[i] ?? false}
												on:click|stopPropagation={() =>
													toggleReading(
														reviewKanjiIdx,
														"kun",
														i,
													)}>{r}</button
											>
										{/each}
									</span>
								</div>
							{/if}
							{#if (reviewKanji?.on ?? []).length}
								<div class="reading-row">
									<span class="r-label">On</span>
									<span class="r-texts">
										{#each reviewKanji?.on ?? [] as r, i}
											{#if i > 0}<span class="r-sep"
													>·</span
												>{/if}
											<button
												class="r-btn"
												class:r-learned={readingLearned?.[
													reviewKanjiIdx
												]?.on?.[i] ?? false}
												on:click|stopPropagation={() =>
													toggleReading(
														reviewKanjiIdx,
														"on",
														i,
													)}>{r}</button
											>
										{/each}
									</span>
								</div>
							{/if}
							{#if reviewKanji?.ex?.kun || reviewKanji?.ex?.on}
							<div class="reading-row ex-row">
								<span class="r-label">Ex</span>
								<div class="ex-block">
									{#if reviewKanji.ex.kun}
										<div class="example">
											{#each reviewKanji.ex.kun.f as part}
												{#if part[1]}<ruby>{part[0]}<rt>{part[1]}</rt></ruby>{:else}{part[0]}{/if}
											{/each}
										</div>
										{#if reviewKanji.ex.kun.t?.en}
											<p class="ex-trans">{reviewKanji.ex.kun.t.en}</p>
										{/if}
									{/if}
									{#if reviewKanji.ex.on}
										<div class="example">
											{#each reviewKanji.ex.on.f as part}
												{#if part[1]}<ruby>{part[0]}<rt>{part[1]}</rt></ruby>{:else}{part[0]}{/if}
											{/each}
										</div>
										{#if reviewKanji.ex.on.t?.en}
											<p class="ex-trans">{reviewKanji.ex.on.t.en}</p>
										{/if}
									{/if}
								</div>
							</div>
						{/if}
							{#if reviewKanji?.jlpt}
								<span class="badge"
									>JLPT {JLPT_MAP[reviewKanji.jlpt] ??
										`N${reviewKanji.jlpt}`}</span
								>
							{/if}
							{#if reviewKanji?.l}
								<a
									class="jisho-link"
									href="https://jisho.org/search/{reviewKanji.l}%23kanji"
									target="_blank"
									rel="noopener noreferrer"
									on:click|stopPropagation
								>
									jisho.org ↗
								</a>
							{/if}
						</div>
					{:else}
						<p class="tap-hint">tap to reveal</p>
					{/if}
				</div>
			</div>
			<div class="review-nav" class:hidden={!reviewRevealed}>
				{#if reviewRevealed}
					<button
						class="review-btn review-unlearn"
						on:click|stopPropagation={() => {
							onUnlearn(reviewKanjiIdx);
							nextReview();
						}}>Unlearn</button
					>
					<button
						class="review-btn review-know"
						on:click|stopPropagation={nextReview}>Know It!</button
					>
				{/if}
			</div>
		{/if}
	</div>
{:else if page === "review-starred"}
	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => { reviewStarted = false; navigate("learn"); }}
				>‹ Back</button
			>
			<span class="sub-title">Review Starred</span>
			<span class="sub-count"
				>{#if reviewQueue.length}
					{Math.min(reviewPos + 1, reviewQueue.length)} / {reviewQueue.length}
				{:else}
					{starredKanji.length} starred
				{/if}</span
			>
			<Menu
				{page}
				{isDark}
				{availableLangs}
				{selectedLang}
				{LANG_NAMES}
				{vocabMode}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
				on:toggletheme={() => {
					isDark = !isDark;
					saveState();
				}}
				on:reset={confirmReset}
			/>
		</div>
		{#if starredKanji.length === 0}
			<div class="screen center">
				<p class="muted">No starred kanji yet.</p>
			</div>
		{:else if reviewQueue.length === 0}
			<div class="screen center"><p class="muted">Loading…</p></div>
		{:else}
			<div
				class="card"
				role="button"
				tabindex="0"
				on:click={() => {
					reviewRevealed = !reviewRevealed;
				}}
				on:keydown={(e) =>
					e.key === "Enter" && (reviewRevealed = !reviewRevealed)}
				on:touchstart|passive={onReviewTouchStart}
				on:touchmove={onReviewTouchMove}
				on:touchend={onReviewTouchEnd}
				style="transform: translateX({Math.max(
					-100,
					Math.min(100, reviewSwipeDeltaX * 0.35),
				)}px); transition: {reviewSwipeActive
					? 'none'
					: 'transform 0.3s ease'}"
			>
				<div class="card-inner">
					<button
						class="star-btn starred"
						on:click|stopPropagation={unstarCurrentReviewKanji}
						aria-label="Unstar"
						aria-pressed="true"
					>★</button>

					{#if reviewSwipeActive && Math.abs(reviewSwipeDeltaX) > 20}
						<div
							class="swipe-overlay"
							class:swipe-right={reviewSwipeDeltaX > 0}
							class:swipe-left={reviewSwipeDeltaX < 0}
							style="opacity: {Math.min(
								0.35,
								Math.abs(reviewSwipeDeltaX) / 200,
							)}"
						></div>
					{/if}
					{#key reviewKanjiIdx}
						<div class="kanji-char" in:fade={{ duration: 180 }}>
							{reviewKanji?.l ?? ""}
						</div>
					{/key}
					{#if reviewRevealed}
						<div class="details">
							{#if (reviewKanji?.meanings?.[selectedLang] ?? reviewKanji?.meanings?.en ?? []).length}
								<p class="meanings">
									{(
										reviewKanji?.meanings?.[selectedLang] ??
										reviewKanji?.meanings?.en ??
										[]
									).join(", ")}
								</p>
							{/if}
							{#if (reviewKanji?.kun ?? []).length}
								<div class="reading-row">
									<span class="r-label">Kun</span>
									<span class="r-texts">
										{#each reviewKanji?.kun ?? [] as r, i}
											{#if i > 0}<span class="r-sep"
													>·</span
												>{/if}
											<button
												class="r-btn"
												class:r-learned={readingLearned?.[
													reviewKanjiIdx
												]?.kun?.[i] ?? false}
												on:click|stopPropagation={() =>
													toggleReading(
														reviewKanjiIdx,
														"kun",
														i,
													)}>{r}</button
											>
										{/each}
									</span>
								</div>
							{/if}
							{#if (reviewKanji?.on ?? []).length}
								<div class="reading-row">
									<span class="r-label">On</span>
									<span class="r-texts">
										{#each reviewKanji?.on ?? [] as r, i}
											{#if i > 0}<span class="r-sep"
													>·</span
												>{/if}
											<button
												class="r-btn"
												class:r-learned={readingLearned?.[
													reviewKanjiIdx
												]?.on?.[i] ?? false}
												on:click|stopPropagation={() =>
													toggleReading(
														reviewKanjiIdx,
														"on",
														i,
													)}>{r}</button
											>
										{/each}
									</span>
								</div>
							{/if}
							{#if reviewKanji?.ex?.kun || reviewKanji?.ex?.on}
							<div class="reading-row ex-row">
								<span class="r-label">Ex</span>
								<div class="ex-block">
									{#if reviewKanji.ex.kun}
										<div class="example">
											{#each reviewKanji.ex.kun.f as part}
												{#if part[1]}<ruby>{part[0]}<rt>{part[1]}</rt></ruby>{:else}{part[0]}{/if}
											{/each}
										</div>
										{#if reviewKanji.ex.kun.t?.en}
											<p class="ex-trans">{reviewKanji.ex.kun.t.en}</p>
										{/if}
									{/if}
									{#if reviewKanji.ex.on}
										<div class="example">
											{#each reviewKanji.ex.on.f as part}
												{#if part[1]}<ruby>{part[0]}<rt>{part[1]}</rt></ruby>{:else}{part[0]}{/if}
											{/each}
										</div>
										{#if reviewKanji.ex.on.t?.en}
											<p class="ex-trans">{reviewKanji.ex.on.t.en}</p>
										{/if}
									{/if}
								</div>
							</div>
						{/if}
							{#if reviewKanji?.jlpt}
								<span class="badge"
									>JLPT {JLPT_MAP[reviewKanji.jlpt] ??
										`N${reviewKanji.jlpt}`}</span
								>
							{/if}
							{#if reviewKanji?.l}
								<a
									class="jisho-link"
									href="https://jisho.org/search/{reviewKanji.l}%23kanji"
									target="_blank"
									rel="noopener noreferrer"
									on:click|stopPropagation
								>
									jisho.org ↗
								</a>
							{/if}
						</div>
					{:else}
						<p class="tap-hint">tap to reveal</p>
					{/if}
				</div>
			</div>
			<div class="review-nav" class:hidden={!reviewRevealed}>
				{#if reviewRevealed}
					<button
						class="review-btn review-unlearn"
						on:click|stopPropagation={() => {
							onUnlearn(reviewKanjiIdx);
							nextReview();
						}}>Unlearn</button
					>
					<button
						class="review-btn review-know"
						on:click|stopPropagation={nextReview}>Next</button
					>
				{/if}
			</div>
		{/if}
	</div>
{:else if page === "vocab-learn"}
	<div class="screen column">
		<div class="progress-track">
			<div class="progress-fill" style="width: {vProgressPct}%"></div>
		</div>
		<div class="stats-row">
			<div class="stat-wrap">
				<span class="stat-val">{vLearnedCount}</span>
				<span class="stat-lbl">/ {vocabList.length} learned</span>
			</div>
			<div class="row-right">
				<button class="mode-toggle" on:click={() => { vocabMode = false; navigate("learn"); }}>Kanji</button>
				<button class="mode-toggle mode-active" on:click={() => navigate("vocab-learn")}>Vocab</button>
				<button class="icon-btn" on:click={() => { showVocabInfo = !showVocabInfo; }} aria-label="Info">
					<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<circle cx="12" cy="12" r="10" />
						<line x1="12" y1="8" x2="12" y2="12" />
						<line x1="12" y1="16" x2="12.01" y2="16" />
					</svg>
				</button>
				<Menu {page} {isDark} {availableLangs} {selectedLang} {LANG_NAMES} {vocabMode}
					on:navigate={(e) => navigate(e.detail)}
					on:selectlang={(e) => selectLang(e.detail)}
					on:toggletheme={() => { isDark = !isDark; saveState(); }}
					on:reset={confirmReset} />
			</div>

			{#if showVocabInfo}
				<div class="info-panel" transition:fly={{ y: -10, duration: 200 }}>
					<p><strong>Know It!</strong> — Mark this word as learned and bring in a new one.</p>
					<p><strong>Still Learning</strong> — Send it back a bit and bring in a new one now.</p>
					<p>Swipe right to Know It!, swipe left to Still Learning.</p>
				</div>
			{/if}
		</div>

		{#if showVocabOnboarding}
			<div class="screen center onboarding">
				<h2 class="onboard-title">VocabStack</h2>
				<p class="onboard-sub">What's your current vocabulary level?</p>
				<div class="onboard-grid">
					<button class="onboard-card" on:click={() => selectVocabOnboardingLevel([])}>
						<span class="onboard-level">Beginner</span>
						<span class="onboard-desc">Start fresh · No words pre-learned</span>
					</button>
					<button class="onboard-card" on:click={() => selectVocabOnboardingLevel([5])}>
						<span class="onboard-level">N5</span>
						<span class="onboard-desc">~{vocabList.filter((v) => v.jlpt === 5).length} words pre-learned</span>
					</button>
					<button class="onboard-card" on:click={() => selectVocabOnboardingLevel([5, 4])}>
						<span class="onboard-level">N4</span>
						<span class="onboard-desc">~{vocabList.filter((v) => v.jlpt >= 4).length} words pre-learned</span>
					</button>
					<button class="onboard-card" on:click={() => selectVocabOnboardingLevel([5, 4, 3])}>
						<span class="onboard-level">N3</span>
						<span class="onboard-desc">~{vocabList.filter((v) => v.jlpt >= 3).length} words pre-learned</span>
					</button>
					<button class="onboard-card" on:click={() => selectVocabOnboardingLevel([5, 4, 3, 2])}>
						<span class="onboard-level">N2/N1</span>
						<span class="onboard-desc">~{vocabList.filter((v) => v.jlpt != null).length} words pre-learned</span>
					</button>
				</div>
				<p class="onboard-note">Pre-learned words go directly to your Learned list.</p>
				<button class="onboard-restore" on:click={() => navigate("data")}
					>Have a backup? Restore progress</button
				>
			</div>
		{:else if vComplete}
			<div class="screen center">
				<div class="complete-icon">🎉</div>
				<h2>All {vocabList.length} words mastered!</h2>
				<p class="muted">Incredible work.</p>
			</div>
		{:else}
			<div
				class="card"
				role="button"
				tabindex="0"
				on:click={() => { if (showVocabInfo) { showVocabInfo = false; return; } if (!vFuriganaRevealed) { vFuriganaRevealed = true; } else if (!vRevealed) { vRevealed = true; } }}
				on:keydown={(e) => e.key === "Enter" && (vRevealed = true)}
				on:touchstart|passive={onVTouchStart}
				on:touchmove={onVTouchMove}
				on:touchend={onVTouchEnd}
				style="transform: translateX({Math.max(-100, Math.min(100, vSwipeDeltaX * 0.35))}px);
					   transition: {vSwipeActive ? 'none' : 'transform 0.3s ease'}"
			>
				<div class="card-inner">
					<button
						class="star-btn"
						class:starred={starredVocab.includes(vCurrentIdx)}
						on:click|stopPropagation={() => toggleStarVocab(vCurrentIdx)}
						aria-label={starredVocab.includes(vCurrentIdx) ? "Unstar" : "Star"}
						aria-pressed={starredVocab.includes(vCurrentIdx)}
					>{starredVocab.includes(vCurrentIdx) ? "★" : "☆"}</button>

					{#if vSwipeActive && Math.abs(vSwipeDeltaX) > 20}
						<div class="swipe-overlay"
							class:swipe-right={vSwipeDeltaX > 0}
							class:swipe-left={vSwipeDeltaX < 0}
							style="opacity: {Math.min(0.35, Math.abs(vSwipeDeltaX) / 200)}"></div>
					{/if}
					{#key vCurrentIdx}
						<div class="kanji-char vocab-word" style={vocabWordStyle(vCurrent?.w)} in:fade={{ duration: 180 }}>
							<ruby class="vocab-ruby">{vCurrent?.w ?? ""}<rt class:rt-hidden={!vFuriganaRevealed}>{vFuriganaRevealed ? (vCurrent?.r ?? "") : "\u00A0"}</rt></ruby>
						</div>
					{/key}
					{#if vRevealed}
						<div class="details">
							{#if vCurrent?.m?.length}
								<p class="meanings">{vCurrent.m.join(", ")}</p>
							{/if}
							{#if vCurrent?.ex}
								<div class="reading-row ex-row">
									<div class="ex-block">
										<div class="example">
											{#each vCurrent.ex.f as part}
												{#if part[1]}<ruby>{part[0]}<rt>{part[1]}</rt></ruby>{:else}{part[0]}{/if}
											{/each}
										</div>
										{#if vCurrent.ex.t?.en}
											<p class="ex-trans">{vCurrent.ex.t.en}</p>
										{/if}
									</div>
								</div>
							{/if}
							{#if vCurrent?.jlpt}
								<span class="badge">JLPT {VOCAB_JLPT_MAP[vCurrent.jlpt] ?? `N${vCurrent.jlpt}`}</span>
							{/if}
							{#if vCurrent?.w}
								<a class="jisho-link" href="https://jisho.org/search/{encodeURIComponent(vCurrent.w)}%23kanji"
									target="_blank" rel="noopener noreferrer" on:click|stopPropagation>jisho.org ↗</a>
							{/if}
						</div>
					{:else}
						<p class="tap-hint">{vFuriganaRevealed ? "tap for meaning" : "tap to reveal"}</p>
					{/if}
				</div>
			</div>
			<div class="btn-row" class:hidden={!vRevealed}>
				{#if vRevealed}
					<button class="action still-learning" on:click|stopPropagation={onVStillLearning}
						in:fly={{ y: 48, duration: 240 }}>Still Learning</button>
					<button class="action know" on:click|stopPropagation={onVKnowIt}
						in:fly={{ y: 48, duration: 240, delay: 40 }}>Know It!</button>
				{/if}
			</div>
		{/if}
	</div>
{:else if page === "vocab-learned"}
	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => navigate("vocab-learn")}>‹ Back</button>
			<span class="sub-title">Vocab Learned</span>
			<span class="sub-count">{vLearnedVocab.length}</span>
			<Menu {page} {isDark} {availableLangs} {selectedLang} {LANG_NAMES} {vocabMode}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
				on:toggletheme={() => { isDark = !isDark; saveState(); }}
				on:reset={confirmReset} />
		</div>
		<div class="stack-list">
			{#if vLearnedVocab.length === 0}
				<p class="stack-empty">No words learned yet.<br />Press "Know It!" to mark words as learned.</p>
			{:else}
				{#each [...vLearnedVocab].reverse() as vIdx}
					{@const v = vocabList[vIdx]}
					{#if v}
						<div class="stack-item">
							<span class="stack-kanji">{v.w}</span>
							<div class="stack-info">
								<span class="stack-meaning">{v.m.slice(0, 3).join(", ")}</span>
								<span class="stack-readings">{v.r}</span>
							</div>
							<button class="unlearn-btn" on:click={() => onVUnlearn(vIdx)} title="Move back to learning">X</button>
						</div>
					{/if}
				{/each}
			{/if}
		</div>
	</div>
{:else if page === "vocab-starred"}
	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => navigate("vocab-learn")}>‹ Back</button>
			<span class="sub-title">Starred</span>
			<span class="sub-count">{starredVocab.length}</span>
			<Menu {page} {isDark} {availableLangs} {selectedLang} {LANG_NAMES} {vocabMode}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
				on:toggletheme={() => { isDark = !isDark; saveState(); }}
				on:reset={confirmReset} />
		</div>
		<div class="stack-list">
			{#if starredVocab.length === 0}
				<p class="stack-empty">No starred words yet.<br />Tap the star on a card to add it here.</p>
			{:else}
				{#each [...starredVocab].reverse() as vIdx}
					{@const v = vocabList[vIdx]}
					{#if v}
						<div class="stack-item">
							<span class="stack-kanji">{v.w}</span>
							<div class="stack-info">
								<span class="stack-meaning">{v.m.slice(0, 3).join(", ")}</span>
								<span class="stack-readings">{v.r}</span>
							</div>
							<button class="unlearn-btn" on:click={() => toggleStarVocab(vIdx)} title="Remove star">★</button>
						</div>
					{/if}
				{/each}
			{/if}
		</div>
	</div>
{:else if page === "review-vocab"}
	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => { vReviewStarted = false; navigate("vocab-learn"); }}>‹ Back</button>
			<span class="sub-title">Review Vocab</span>
			<span class="sub-count">
				{#if vReviewStarted && vReviewQueue.length}
					{Math.min(vReviewPos + 1, vReviewQueue.length)} / {vReviewQueue.length}
				{:else}
					{vLearnedVocab.length} learned
				{/if}
			</span>
			<Menu {page} {isDark} {availableLangs} {selectedLang} {LANG_NAMES} {vocabMode}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
				on:toggletheme={() => { isDark = !isDark; saveState(); }}
				on:reset={confirmReset} />
		</div>

		{#if !vReviewStarted}
			<!-- Level picker -->
			<div class="screen center">
				{#if vLearnedVocab.length === 0}
					<p class="muted">No learned vocabulary yet.</p>
				{:else}
					<p class="review-pick-title">Select levels to review</p>
					<div class="review-level-grid">
						{#each [[5,"N5"],[4,"N4"],[3,"N3"],[2,"N2/N1"]] as [lvl, label]}
							{@const count = vLearnedVocab.filter((i) => vocabList[i]?.jlpt === lvl).length}
							<button
								class="review-level-btn"
								class:review-level-active={vReviewLevels.has(lvl)}
								disabled={count === 0}
								on:click={() => toggleVReviewLevel(lvl)}
							>
								<span class="rl-label">{label}</span>
								<span class="rl-count">{count} words</span>
							</button>
						{/each}
					</div>
					{@const total = vLearnedVocab.filter((i) => vocabList[i] && vReviewLevels.has(vocabList[i].jlpt)).length}
					<button
						class="review-start-btn"
						disabled={total === 0}
						on:click={startVocabReview}
					>Review {total} {total === 1 ? "word" : "words"}</button>
				{/if}
			</div>
		{:else if vReviewQueue.length === 0}
			<div class="screen center"><p class="muted">No words match the selected levels.</p></div>
		{:else}
			<div
				class="card"
				role="button"
				tabindex="0"
				on:click={() => { if (!vReviewFuriganaRevealed) { vReviewFuriganaRevealed = true; } else { vReviewRevealed = !vReviewRevealed; } }}
				on:keydown={(e) => e.key === "Enter" && (!vReviewFuriganaRevealed ? (vReviewFuriganaRevealed = true) : (vReviewRevealed = !vReviewRevealed))}
				on:touchstart|passive={onVReviewTouchStart}
				on:touchmove={onVReviewTouchMove}
				on:touchend={onVReviewTouchEnd}
				style="transform: translateX({Math.max(-100, Math.min(100, vReviewSwipeDeltaX * 0.35))}px);
					   transition: {vReviewSwipeActive ? 'none' : 'transform 0.3s ease'}"
			>
				<div class="card-inner">
					{#if vReviewSwipeActive && Math.abs(vReviewSwipeDeltaX) > 20}
						<div class="swipe-overlay"
							class:swipe-right={vReviewSwipeDeltaX > 0}
							class:swipe-left={vReviewSwipeDeltaX < 0}
							style="opacity: {Math.min(0.35, Math.abs(vReviewSwipeDeltaX) / 200)}"></div>
					{/if}
					{#key vReviewIdx}
						<div class="kanji-char vocab-word" style={vocabWordStyle(vReviewEntry?.w)} in:fade={{ duration: 180 }}>
							<ruby class="vocab-ruby">{vReviewEntry?.w ?? ""}<rt class:rt-hidden={!vReviewFuriganaRevealed}>{vReviewFuriganaRevealed ? (vReviewEntry?.r ?? "") : "\u00A0"}</rt></ruby>
						</div>
					{/key}
					{#if vReviewRevealed}
						<div class="details">
							{#if vReviewEntry?.m?.length}
								<p class="meanings">{vReviewEntry.m.join(", ")}</p>
							{/if}
							{#if vReviewEntry?.ex}
								<div class="reading-row ex-row">
									<div class="ex-block">
										<div class="example">
											{#each vReviewEntry.ex.f as part}
												{#if part[1]}<ruby>{part[0]}<rt>{part[1]}</rt></ruby>{:else}{part[0]}{/if}
											{/each}
										</div>
										{#if vReviewEntry.ex.t?.en}
											<p class="ex-trans">{vReviewEntry.ex.t.en}</p>
										{/if}
									</div>
								</div>
							{/if}
							{#if vReviewEntry?.jlpt}
								<span class="badge">JLPT {VOCAB_JLPT_MAP[vReviewEntry.jlpt] ?? `N${vReviewEntry.jlpt}`}</span>
							{/if}
							{#if vReviewEntry?.w}
								<a class="jisho-link" href="https://jisho.org/search/{encodeURIComponent(vReviewEntry.w)}%23kanji"
									target="_blank" rel="noopener noreferrer" on:click|stopPropagation>jisho.org ↗</a>
							{/if}
						</div>
					{:else}
						<p class="tap-hint">{vReviewFuriganaRevealed ? "tap for meaning" : "tap to reveal"}</p>
					{/if}
				</div>
			</div>
			<div class="review-nav" class:hidden={!vReviewRevealed}>
				{#if vReviewRevealed}
					<button class="review-btn review-unlearn"
						on:click|stopPropagation={() => { onVUnlearn(vReviewIdx); vNextReview(); }}>Unlearn</button>
					<button class="review-btn review-know"
						on:click|stopPropagation={vNextReview}>Know It!</button>
				{/if}
			</div>
		{/if}
	</div>
{:else if page === "review-vocab-starred"}
	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => { vReviewStarted = false; navigate("vocab-learn"); }}>‹ Back</button>
			<span class="sub-title">Review Starred</span>
			<span class="sub-count">
				{#if vReviewQueue.length}
					{Math.min(vReviewPos + 1, vReviewQueue.length)} / {vReviewQueue.length}
				{:else}
					{starredVocab.length} starred
				{/if}
			</span>
			<Menu {page} {isDark} {availableLangs} {selectedLang} {LANG_NAMES} {vocabMode}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
				on:toggletheme={() => { isDark = !isDark; saveState(); }}
				on:reset={confirmReset} />
		</div>

		{#if starredVocab.length === 0}
			<div class="screen center"><p class="muted">No starred words yet.</p></div>
		{:else if vReviewQueue.length === 0}
			<div class="screen center"><p class="muted">Loading…</p></div>
		{:else}
			<div
				class="card"
				role="button"
				tabindex="0"
				on:click={() => { if (!vReviewFuriganaRevealed) { vReviewFuriganaRevealed = true; } else { vReviewRevealed = !vReviewRevealed; } }}
				on:keydown={(e) => e.key === "Enter" && (!vReviewFuriganaRevealed ? (vReviewFuriganaRevealed = true) : (vReviewRevealed = !vReviewRevealed))}
				on:touchstart|passive={onVReviewTouchStart}
				on:touchmove={onVReviewTouchMove}
				on:touchend={onVReviewTouchEnd}
				style="transform: translateX({Math.max(-100, Math.min(100, vReviewSwipeDeltaX * 0.35))}px);
					   transition: {vReviewSwipeActive ? 'none' : 'transform 0.3s ease'}"
			>
				<div class="card-inner">
					<button
						class="star-btn starred"
						on:click|stopPropagation={unstarCurrentReviewVocab}
						aria-label="Unstar"
						aria-pressed="true"
					>★</button>

					{#if vReviewSwipeActive && Math.abs(vReviewSwipeDeltaX) > 20}
						<div class="swipe-overlay"
							class:swipe-right={vReviewSwipeDeltaX > 0}
							class:swipe-left={vReviewSwipeDeltaX < 0}
							style="opacity: {Math.min(0.35, Math.abs(vReviewSwipeDeltaX) / 200)}"></div>
					{/if}
					{#key vReviewIdx}
						<div class="kanji-char vocab-word" style={vocabWordStyle(vReviewEntry?.w)} in:fade={{ duration: 180 }}>
							<ruby class="vocab-ruby">{vReviewEntry?.w ?? ""}<rt class:rt-hidden={!vReviewFuriganaRevealed}>{vReviewFuriganaRevealed ? (vReviewEntry?.r ?? "") : "\u00A0"}</rt></ruby>
						</div>
					{/key}
					{#if vReviewRevealed}
						<div class="details">
							{#if vReviewEntry?.m?.length}
								<p class="meanings">{vReviewEntry.m.join(", ")}</p>
							{/if}
							{#if vReviewEntry?.ex}
								<div class="reading-row ex-row">
									<div class="ex-block">
										<div class="example">
											{#each vReviewEntry.ex.f as part}
												{#if part[1]}<ruby>{part[0]}<rt>{part[1]}</rt></ruby>{:else}{part[0]}{/if}
											{/each}
										</div>
										{#if vReviewEntry.ex.t?.en}
											<p class="ex-trans">{vReviewEntry.ex.t.en}</p>
										{/if}
									</div>
								</div>
							{/if}
							{#if vReviewEntry?.jlpt}
								<span class="badge">JLPT {VOCAB_JLPT_MAP[vReviewEntry.jlpt] ?? `N${vReviewEntry.jlpt}`}</span>
							{/if}
							{#if vReviewEntry?.w}
								<a class="jisho-link" href="https://jisho.org/search/{encodeURIComponent(vReviewEntry.w)}%23kanji"
									target="_blank" rel="noopener noreferrer" on:click|stopPropagation>jisho.org ↗</a>
							{/if}
						</div>
					{:else}
						<p class="tap-hint">{vReviewFuriganaRevealed ? "tap for meaning" : "tap to reveal"}</p>
					{/if}
				</div>
			</div>
			<div class="review-nav" class:hidden={!vReviewRevealed}>
				{#if vReviewRevealed}
					<button class="review-btn review-unlearn"
						on:click|stopPropagation={() => { onVUnlearn(vReviewIdx); vNextReview(); }}>Unlearn</button>
					<button class="review-btn review-know"
						on:click|stopPropagation={vNextReview}>Next</button>
				{/if}
			</div>
		{/if}
	</div>
{:else if page === "data"}
	<div class="screen column">
		<div class="sub-header">
			<button class="back-btn" on:click={() => navigate(vocabMode ? "vocab-learn" : "learn")}
				>‹ Back</button
			>
			<span class="sub-title">Data</span>
			<Menu
				{page}
				{isDark}
				{availableLangs}
				{selectedLang}
				{LANG_NAMES}
				{vocabMode}
				on:navigate={(e) => navigate(e.detail)}
				on:selectlang={(e) => selectLang(e.detail)}
				on:toggletheme={() => {
					isDark = !isDark;
					saveState();
				}}
				on:reset={confirmReset}
			/>
		</div>

		<div class="screen center data-page">
			<p class="data-desc">
				Back up what you've learned, or restore progress from a
				previous backup.
			</p>

			<button class="data-btn data-download" on:click={downloadProgress}>
				Download Progress
			</button>
			<button class="data-btn data-upload" on:click={triggerImport}>
				Upload Progress
			</button>
			<input
				type="file"
				accept="application/json"
				bind:this={dataFileInput}
				on:change={handleImportFile}
				style="display: none;"
			/>

			{#if dataStatus}
				<p class="data-status" class:data-status-error={dataStatus.type === "error"}>
					{dataStatus.message}
				</p>
			{/if}
		</div>
	</div>
{/if}

<CookieBanner />

<style>
	:global(:root) {
		--c-bg: #111;
		--c-bg2: #1a1a1a;
		--c-bg3: #222;
		--c-border: #1e1e1e;
		--c-text: #f0f0f0;
		--c-text2: #e2e8f0;
		--c-muted: #6b7280;
		--c-muted2: #9ca3af;
		--c-kanji: #ffffff;
		--c-on: #a8b8cc;
		--c-ex: #8fa5bc;
		--c-hint: #3a3a3a;
		--c-tap-hint: #555;
		--c-reading-learned: #f59e0b;
		--c-repeat: #f59e0b;
		--c-progress-bg: #1e1e1e;
		--c-item-hover: #161616;
		--c-stack-border: #191919;
	}

	:global(body.light) {
		--c-bg: #f5f5f5;
		--c-bg2: #ffffff;
		--c-bg3: #ebebeb;
		--c-border: #e0e0e0;
		--c-text: #111111;
		--c-text2: #1f2937;
		--c-muted: #6b7280;
		--c-muted2: #374151;
		--c-kanji: #111111;
		--c-on: #1e3a5f;
		--c-ex: #1a3a50;
		--c-hint: #ccc;
		--c-tap-hint: #888;
		--c-reading-learned: #1d4ed8;
		--c-repeat: #1d4ed8;
		--c-progress-bg: #e0e0e0;
		--c-item-hover: #f0f0f0;
		--c-stack-border: #e8e8e8;
	}

	:global(html, body) {
		height: 100%;
		background: var(--c-bg);
		color: var(--c-text);
		font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
			"Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP",
			sans-serif;
		-webkit-font-smoothing: antialiased;
	}

	:global(#app) {
		height: 100%;
	}

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

	.progress-track {
		width: 100%;
		height: 3px;
		background: var(--c-progress-bg);
		flex-shrink: 0;
	}

	.progress-fill {
		height: 100%;
		background: #22c55e;
		transition: width 0.4s ease;
	}

	.stats-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.5rem 0.75rem 0.4rem;
		flex-shrink: 0;
		position: relative;
	}

	.stat-wrap {
		position: relative;
		display: flex;
		align-items: baseline;
		gap: 0.3rem;
	}

	.stat-val {
		color: var(--c-muted2);
		font-weight: 600;
		font-size: 0.8rem;
	}

	.stat-lbl {
		color: var(--c-muted);
		font-size: 0.8rem;
	}

	.fly-badge {
		position: fixed;
		font-size: 1.6rem;
		font-weight: 800;
		pointer-events: none;
		z-index: 1000;
		transform: translate(-50%, -50%);
		animation: flyToTarget 1.1s cubic-bezier(0.25, 0.46, 0.45, 0.94)
			forwards;
	}

	.fly-green {
		color: #22c55e;
	}

	@keyframes flyToTarget {
		0% {
			opacity: 1;
			transform: translate(-50%, -50%) scale(1.8);
		}
		100% {
			opacity: 0;
			transform: translate(calc(-50% + var(--dx)), calc(-50% + var(--dy)))
				scale(0.55);
		}
	}

	.row-right {
		display: flex;
		align-items: center;
		gap: 2px;
	}

	.mode-toggle {
		background: none;
		border: 1px solid var(--c-border);
		color: var(--c-muted);
		cursor: pointer;
		padding: 3px 9px;
		font-size: 0.72rem;
		font-weight: 600;
		border-radius: 20px;
		letter-spacing: 0.04em;
		transition: background 0.15s, color 0.15s;
	}
	.mode-toggle.mode-active {
		background: var(--c-text);
		color: var(--c-bg);
		border-color: var(--c-text);
	}

	.vocab-word {
		--wlen: 1;
		/* Shrink as the word gets longer so it keeps fitting the screen width;
		   falls back to wrapping onto extra rows if it still can't fit. */
		font-size: clamp(1.5rem, min(18vw, calc(78vw / var(--wlen))), 5.5rem) !important;
		letter-spacing: 0.05em;
		max-width: 100%;
		min-width: 0;
		text-align: center;
		overflow-wrap: break-word;
		word-break: break-word;
	}

	.vocab-ruby rt {
		font-size: 0.28em;
		letter-spacing: 0.05em;
		color: var(--c-muted2);
		transition: opacity 0.2s ease;
	}

	.vocab-ruby rt.rt-hidden {
		opacity: 0;
	}

	.vocab-reading {
		font-size: 1.5rem;
		color: var(--c-on);
		margin: 0.1rem 0 0.5rem;
		text-align: center;
		letter-spacing: 0.08em;
	}

	.review-pick-title {
		font-size: 1rem;
		color: var(--c-muted2);
		margin-bottom: 1.5rem;
		font-weight: 500;
	}

	.review-level-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
		width: 100%;
		max-width: 320px;
		margin-bottom: 2rem;
	}

	.review-level-btn {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.25rem;
		padding: 1rem 0.5rem;
		background: var(--c-bg2);
		border: 2px solid var(--c-border);
		border-radius: 14px;
		cursor: pointer;
		color: var(--c-muted2);
		transition: border-color 0.15s, background 0.15s, color 0.15s;
	}

	.review-level-btn:disabled {
		opacity: 0.35;
		cursor: not-allowed;
		border-color: #ef4444 !important;
		background: rgba(239, 68, 68, 0.07) !important;
	}

	.review-level-btn.review-level-active {
		border-color: #22c55e;
		background: rgba(34, 197, 94, 0.1);
		color: var(--c-text);
	}

	.rl-label {
		font-size: 1.3rem;
		font-weight: 700;
	}

	.rl-count {
		font-size: 0.72rem;
		color: var(--c-muted);
	}

	.review-level-btn.review-level-active .rl-count {
		color: var(--c-muted2);
	}

	.review-start-btn {
		padding: 0.85rem 2.5rem;
		background: #22c55e;
		color: #fff;
		border: none;
		border-radius: 50px;
		font-size: 1rem;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.15s, opacity 0.15s;
	}

	.review-start-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.review-start-btn:not(:disabled):hover {
		background: #16a34a;
	}

	.data-page {
		gap: 1rem;
		padding: 0 1.5rem;
		text-align: center;
	}

	.data-desc {
		color: var(--c-muted2);
		font-size: 0.9rem;
		line-height: 1.5;
		max-width: 360px;
		margin: 0 0 0.5rem;
	}

	.data-btn {
		width: 100%;
		max-width: 280px;
		padding: 0.85rem 1.5rem;
		border-radius: 50px;
		font-size: 1rem;
		font-weight: 600;
		cursor: pointer;
		border: none;
		transition: background 0.15s, opacity 0.15s;
	}

	.data-download {
		background: #22c55e;
		color: #fff;
	}

	.data-download:hover {
		background: #16a34a;
	}

	.data-upload {
		background: var(--c-bg3);
		color: var(--c-text);
		border: 1px solid var(--c-border);
	}

	.data-upload:hover {
		background: var(--c-item-hover);
	}

	.data-status {
		font-size: 0.88rem;
		color: #22c55e;
		max-width: 320px;
	}

	.data-status-error {
		color: #f87171;
	}

	.icon-btn {
		background: none;
		border: none;
		color: var(--c-muted);
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
		color: var(--c-muted2);
		background: var(--c-border);
	}

	.info-panel {
		position: absolute;
		top: calc(100% - 4px);
		left: 0.75rem;
		right: 0.75rem;
		z-index: 100;
		background: var(--c-bg2);
		border: 1px solid var(--c-border);
		border-radius: 12px;
		padding: 0.9rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
		font-size: 0.83rem;
		color: var(--c-muted2);
		box-shadow: 0 8px 24px rgba(0,0,0,0.25);
	}

	.info-panel strong {
		color: var(--c-text2);
	}

	.sub-header {
		display: flex;
		align-items: center;
		padding: 0.6rem 0.75rem;
		border-bottom: 1px solid var(--c-border);
		flex-shrink: 0;
		gap: 0.5rem;
	}

	.back-btn {
		background: none;
		border: none;
		color: var(--c-muted2);
		font-size: 1rem;
		cursor: pointer;
		padding: 4px 8px 4px 0;
		transition: color 0.15s;
	}

	.back-btn:hover {
		color: var(--c-text);
	}

	.sub-title {
		flex: 1;
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--c-text2);
	}

	.sub-count {
		font-size: 0.78rem;
		color: var(--c-muted);
	}

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
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		min-height: 100%;
		padding: 10vh 1.5rem 2.5rem;
		gap: 1.5rem;
		overflow: hidden;
	}

	.star-btn {
		position: absolute;
		top: 0;
		right: 0;
		background: none;
		border: none;
		color: var(--c-muted);
		font-size: 1.5rem;
		line-height: 1;
		padding: 0.3rem 0.4rem;
		cursor: pointer;
		z-index: 5;
		-webkit-tap-highlight-color: transparent;
		transition: color 0.15s, transform 0.15s;
	}

	.star-btn:active {
		transform: scale(0.85);
	}

	.star-btn.starred {
		color: #eab308;
	}

	.swipe-overlay {
		position: absolute;
		inset: 0;
		pointer-events: none;
		border-radius: inherit;
		transition: none;
	}

	.swipe-right {
		background: #16a34a;
	}

	.swipe-left {
		background: #dc2626;
	}

	.kanji-char {
		font-size: clamp(5rem, 38vw, 200px);
		line-height: 1;
		font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN",
			"Noto Sans JP", sans-serif;
		color: var(--c-kanji);
		text-shadow: 0 2px 24px rgba(255, 255, 255, 0.06);
	}

	.tap-hint {
		font-size: 0.75rem;
		color: var(--c-tap-hint);
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}

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
		font-size: 1.2rem;
		color: var(--c-text2);
		text-align: center;
		font-style: italic;
		line-height: 1.4;
	}

	.reading-row {
		display: flex;
		align-items: baseline;
		width: 100%;
		position: relative;
		min-height: 2rem;
	}

	.r-label {
		position: absolute;
		left: 0;
		top: 0.35rem;
		font-size: 0.65rem;
		color: var(--c-muted);
		text-transform: uppercase;
		letter-spacing: 0.1em;
		width: 2.6rem;
		text-align: right;
	}

	.r-texts {
		width: 100%;
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		align-items: baseline;
		gap: 0 0.5rem;
		padding: 0 2.8rem;
		box-sizing: border-box;
	}

	.r-sep {
		color: var(--c-muted);
		font-size: 0.75em;
		user-select: none;
	}

	.r-row-tap {
		cursor: pointer;
		border-radius: 8px;
		padding: 2px 4px;
		transition: background 0.15s;
		-webkit-tap-highlight-color: transparent;
	}

	.r-row-tap:active {
		background: rgba(255, 255, 255, 0.04);
	}

	.r-btn {
		display: inline;
		background: none;
		border: none;
		padding: 0 0.2rem;
		font-size: 1.4rem;
		font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
		color: var(--c-on);
		cursor: pointer;
		transition: color 0.2s;
		-webkit-tap-highlight-color: transparent;
		line-height: 1.6;
	}

	.r-btn.r-learned {
		color: var(--c-reading-learned);
	}

	.r-btn:active {
		opacity: 0.7;
	}

	.ex-row {
		align-items: flex-start;
	}

	.ex-type-label {
	  font-size: 0.6rem;
	  letter-spacing: 0.12em;
	  text-transform: uppercase;
	  color: #22c55e;
	  margin-top: 0.55rem;
	  font-weight: 600;
	}

	.ex-type-label:first-child { margin-top: 0; }

	.ex-type-on { color: var(--c-on); }

	.ex-block {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.3rem;
		flex: 1;
	}

	.example {
		font-size: 1.15rem;
		color: var(--c-ex);
		line-height: 2.5;
		font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN",
			"Noto Sans JP", sans-serif;
	}

	ruby {
		ruby-align: center;
	}

	rt {
		font-size: 0.58em;
		color: var(--c-muted2);
		letter-spacing: 0.01em;
	}

	.ex-trans {
		font-size: 0.95rem;
		color: var(--c-muted2);
		line-height: 1.4;
		margin: 0 0 1rem;
	}

	.ex-block > .example:first-of-type ~ .example {
		margin-top: 0;
	}

	.badge {
		font-size: 0.7rem;
		background: var(--c-bg3);
		color: #60a5fa;
		border: 1px solid var(--c-border);
		border-radius: 6px;
		padding: 2px 8px;
		letter-spacing: 0.05em;
		margin-top: 0.25rem;
	}

	.btn-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		height: 72px;
		flex-shrink: 0;
		border-top: 1px solid var(--c-border);
		overflow: hidden;
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

	.know {
		background: #16a34a;
	}

	.still-learning {
		background: #dc2626;
	}

	.stack-list {
		flex: 1;
		overflow-x: hidden;
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
		color: var(--c-muted);
		font-size: 0.9rem;
	}

	.stack-item {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem 1rem;
		border-bottom: 1px solid var(--c-stack-border);
		transition: background 0.1s;
	}

	.stack-item:hover {
		background: var(--c-item-hover);
	}

	.stack-kanji {
		font-size: 2rem;
		font-family: "Hiragino Mincho ProN", "Yu Mincho", "MS Mincho", serif;
		min-width: 2.4rem;
		text-align: center;
		line-height: 1;
		color: var(--c-kanji);
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
		color: var(--c-text2);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.stack-readings {
		font-size: 0.8rem;
		color: var(--c-muted);
		font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.unlearn-btn {
		background: none;
		border: 1px solid rgba(220, 38, 38, 0.3);
		color: #dc2626;
		font-size: 0.85rem;
		font-weight: 700;
		border-radius: 6px;
		padding: 4px 10px;
		cursor: pointer;
		transition:
			background 0.15s,
			border-color 0.15s;
		flex-shrink: 0;
		letter-spacing: 0.05em;
	}

	.unlearn-btn:hover {
		background: rgba(220, 38, 38, 0.12);
		border-color: #dc2626;
	}

	.jisho-link {
		font-size: 0.72rem;
		color: var(--c-muted2);
		text-decoration: none;
		border: 1px solid var(--c-border);
		border-radius: 6px;
		padding: 2px 8px;
		letter-spacing: 0.04em;
		transition:
			color 0.15s,
			border-color 0.15s;
		margin-top: 0.1rem;
	}

	.jisho-link:hover {
		color: var(--c-text2);
		border-color: var(--c-muted);
	}

	.muted {
		color: var(--c-muted);
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
		background: var(--c-border);
		color: var(--c-muted2);
		border: 1px solid var(--c-hint);
		border-radius: 8px;
		padding: 0.6rem 1.4rem;
		font-size: 0.85rem;
		cursor: pointer;
		transition:
			color 0.15s,
			border-color 0.15s;
	}

	.reset-btn:hover {
		color: var(--c-text2);
		border-color: var(--c-muted);
	}

	.reset-btn.small {
		padding: 0.4rem 1rem;
	}

	.spinner {
		width: 32px;
		height: 32px;
		border: 3px solid var(--c-bg3);
		border-top-color: var(--c-muted);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	/* ── Onboarding ── */
	.onboarding {
		gap: 1.2rem;
		padding: 2rem 1.5rem;
	}
	.onboard-title {
		font-size: 1.8rem;
		font-weight: 800;
		letter-spacing: -0.02em;
		margin: 0;
	}
	.onboard-sub {
		color: var(--c-muted2);
		font-size: 0.9rem;
		margin: 0;
	}
	.onboard-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
		width: 100%;
		max-width: 380px;
	}
	.onboard-card {
		background: var(--c-bg2);
		border: 1px solid var(--c-border);
		border-radius: 14px;
		padding: 1rem 0.75rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.35rem;
		cursor: pointer;
		transition:
			border-color 0.15s,
			background 0.15s;
	}
	.onboard-card:hover {
		border-color: var(--c-muted);
		background: var(--c-item-hover);
	}
	.onboard-card:first-child {
		grid-column: 1 / -1;
	}
	.onboard-level {
		font-size: 1.3rem;
		font-weight: 700;
		color: var(--c-text);
	}
	.onboard-desc {
		font-size: 0.72rem;
		color: var(--c-muted2);
		text-align: center;
		line-height: 1.4;
	}
	.onboard-note {
		font-size: 0.72rem;
		color: var(--c-muted);
		text-align: center;
		max-width: 300px;
		line-height: 1.5;
	}

	.onboard-restore {
		background: none;
		border: none;
		color: var(--c-muted2);
		font-size: 0.8rem;
		text-decoration: underline;
		cursor: pointer;
		margin-top: 0.75rem;
		padding: 0.25rem;
	}

	.onboard-restore:hover {
		color: var(--c-text2);
	}

	/* ── Review navigation ── */
	.review-nav {
		display: grid;
		grid-template-columns: 1fr 1fr;
		height: 64px;
		flex-shrink: 0;
		border-top: 1px solid var(--c-border);
	}
	.review-btn {
		background: none;
		border: none;
		font-size: 0.9rem;
		font-weight: 700;
		cursor: pointer;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: #fff;
		transition: filter 0.12s;
	}
	.review-btn:active {
		filter: brightness(0.82);
	}
	.review-unlearn {
		background: #dc2626;
	}
	.review-know {
		background: #16a34a;
	}
</style>
