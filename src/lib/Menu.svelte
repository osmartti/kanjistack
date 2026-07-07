<script>
  import { createEventDispatcher } from 'svelte';
  import { fade, fly } from 'svelte/transition';

  export let page;
  export let isDark;
  export let availableLangs;
  export let selectedLang;
  export let LANG_NAMES;

  const dispatch = createEventDispatcher();

  let showMenu = false;
  let showLearnMenu = false;
  let showViewMenu = false;
  let showLangMenu = false;

  function toggleMenu() {
    showMenu = !showMenu;
    if (!showMenu) closeAll();
  }

  function closeAll() {
    showLearnMenu = false;
    showViewMenu = false;
    showLangMenu = false;
  }

  function onLearnToggle() {
    showLearnMenu = !showLearnMenu;
    showViewMenu = false;
    showLangMenu = false;
  }

  function onViewToggle() {
    showViewMenu = !showViewMenu;
    showLearnMenu = false;
    showLangMenu = false;
  }

  function onLangToggle() {
    showLangMenu = !showLangMenu;
    showLearnMenu = false;
    showViewMenu = false;
  }

  function navigate(p) {
    dispatch('navigate', p);
    showMenu = false;
    closeAll();
  }

  function selectLang(lang) {
    dispatch('selectlang', lang);
    showMenu = false;
    closeAll();
  }

  function toggleTheme() {
    dispatch('toggletheme');
  }

  function resetProgress() {
    showMenu = false;
    closeAll();
    dispatch('reset');
  }

  function onWindowClick(e) {
    if (showMenu && !e.target.closest?.('.menu-wrap')) {
      showMenu = false;
      closeAll();
    }
  }
</script>

<svelte:window on:click={onWindowClick} />

<div class="menu-wrap">
  <button
    class="dots-btn"
    on:click|stopPropagation={toggleMenu}
    aria-label="Menu"
    aria-expanded={showMenu}
  >···</button>

  {#if showMenu}
    <div class="dropdown" transition:fly={{ y: -6, duration: 150 }}>
      <button class="dd-item dd-group" on:click|stopPropagation={onLearnToggle}>
        <span class:group-active={page === 'learn' || page === 'vocab-learn'}>Learn</span>
        <span class="chevron">{showLearnMenu ? '▴' : '▾'}</span>
      </button>
      {#if showLearnMenu}
        <div class="sub-panel" transition:fade={{ duration: 100 }}>
          <button class="dd-item sub-item" class:dd-active={page === 'learn'} on:click={() => navigate('learn')}>
            Kanji
            {#if page === 'learn'}<span class="check">✓</span>{/if}
          </button>
          <button class="dd-item sub-item" class:dd-active={page === 'vocab-learn'} on:click={() => navigate('vocab-learn')}>
            Vocab
            {#if page === 'vocab-learn'}<span class="check">✓</span>{/if}
          </button>
        </div>
      {/if}

      <div class="dd-divider"></div>

      <button class="dd-item dd-group" on:click|stopPropagation={onViewToggle}>
        <span class:group-active={page === 'stack-current' || page === 'stack-learned' || page === 'review-learned' || page === 'vocab-learned' || page === 'review-vocab'}>View</span>
        <span class="chevron">{showViewMenu ? '▴' : '▾'}</span>
      </button>
      {#if showViewMenu}
        <div class="sub-panel" transition:fade={{ duration: 100 }}>
          <button class="dd-item sub-item" class:dd-active={page === 'stack-current'} on:click={() => navigate('stack-current')}>
            Current Stack
            {#if page === 'stack-current'}<span class="check">✓</span>{/if}
          </button>
          <button class="dd-item sub-item" class:dd-active={page === 'stack-learned'} on:click={() => navigate('stack-learned')}>
            Learned
            {#if page === 'stack-learned'}<span class="check">✓</span>{/if}
          </button>
          <button class="dd-item sub-item" class:dd-active={page === 'review-learned'} on:click={() => navigate('review-learned')}>
            Review Learned
            {#if page === 'review-learned'}<span class="check">✓</span>{/if}
          </button>
          <button class="dd-item sub-item" class:dd-active={page === 'vocab-learned'} on:click={() => navigate('vocab-learned')}>
            Vocab Learned
            {#if page === 'vocab-learned'}<span class="check">✓</span>{/if}
          </button>
          <button class="dd-item sub-item" class:dd-active={page === 'review-vocab'} on:click={() => navigate('review-vocab')}>
            Review Vocab
            {#if page === 'review-vocab'}<span class="check">✓</span>{/if}
          </button>
        </div>
      {/if}

      <div class="dd-divider"></div>

      <button class="dd-item dd-group" on:click|stopPropagation={onLangToggle}>
        <span>Language <em>· {LANG_NAMES[selectedLang] ?? selectedLang}</em></span>
        <span class="chevron">{showLangMenu ? '▴' : '▾'}</span>
      </button>
      {#if showLangMenu}
        <div class="sub-panel" transition:fade={{ duration: 100 }}>
          {#each availableLangs as lang}
            <button
              class="dd-item sub-item"
              class:dd-active={lang === selectedLang}
              on:click={() => selectLang(lang)}
            >
              {LANG_NAMES[lang] ?? lang}
              {#if lang === selectedLang}<span class="check">✓</span>{/if}
            </button>
          {/each}
        </div>
      {/if}

      <div class="dd-divider"></div>

      <button class="dd-item" on:click={toggleTheme}>
        <span>{isDark ? 'Light mode ☀' : 'Dark mode 🌙'}</span>
      </button>

      <div class="dd-divider"></div>

      <button class="dd-item dd-danger" on:click={resetProgress}>
        Reset Progress
      </button>
    </div>
  {/if}
</div>

<style>
  .menu-wrap {
    position: relative;
  }

  .dots-btn {
    background: none;
    border: none;
    color: var(--c-muted);
    cursor: pointer;
    padding: 6px 8px;
    line-height: 1;
    border-radius: 8px;
    font-size: 1.15rem;
    letter-spacing: 0.05em;
    transition: color 0.15s, background 0.15s;
  }

  .dots-btn:hover {
    color: var(--c-muted2);
    background: var(--c-border);
  }

  .dropdown {
    position: absolute;
    right: 0;
    top: calc(100% + 4px);
    width: 220px;
    background: var(--c-bg2);
    border: 1px solid var(--c-border);
    border-radius: 12px;
    overflow: hidden;
    z-index: 200;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
  }

  .dd-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    background: none;
    border: none;
    color: var(--c-text2);
    font-size: 0.88rem;
    padding: 0.65rem 1rem;
    cursor: pointer;
    text-align: left;
    transition: background 0.1s, color 0.1s;
  }

  .dd-item:hover {
    background: var(--c-item-hover);
    color: var(--c-text);
  }

  .dd-active {
    color: var(--c-text) !important;
    font-weight: 600;
  }

  .dd-group {
    color: var(--c-text2);
    font-weight: 500;
  }

  .group-active {
    color: var(--c-text);
  }

  .dd-divider {
    height: 1px;
    background: var(--c-border);
    margin: 2px 0;
  }

  .chevron {
    font-size: 0.6rem;
    color: var(--c-muted);
  }

  .sub-panel {
    background: var(--c-bg);
    border-top: 1px solid var(--c-border);
  }

  .sub-item {
    padding-left: 1.6rem;
    color: var(--c-muted2);
    font-size: 0.84rem;
  }

  .sub-item:hover {
    color: var(--c-text2);
  }

  .dd-group em {
    font-style: normal;
    color: var(--c-muted);
    font-weight: 400;
  }

  .check {
    color: #22c55e;
    font-size: 0.78rem;
  }

  .dd-danger {
    color: #f87171;
  }

  .dd-danger:hover {
    color: #ef4444;
    background: rgba(239, 68, 68, 0.08);
  }
</style>
