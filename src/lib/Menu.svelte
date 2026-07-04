<script>
  import { createEventDispatcher } from 'svelte';
  import { fade, fly } from 'svelte/transition';

  export let page;
  export let srQueue;
  export let availableLangs;
  export let selectedLang;
  export let LANG_NAMES;

  const dispatch = createEventDispatcher();

  let showMenu      = false;
  let showLearnMenu = false;
  let showViewMenu  = false;
  let showLangMenu  = false;

  function toggleMenu() {
    showMenu = !showMenu;
    if (!showMenu) closeAll();
  }

  function closeAll() {
    showLearnMenu = false;
    showViewMenu  = false;
    showLangMenu  = false;
  }

  function onLearnToggle() {
    showLearnMenu = !showLearnMenu;
    showViewMenu  = false;
    showLangMenu  = false;
  }

  function onViewToggle() {
    showViewMenu  = !showViewMenu;
    showLearnMenu = false;
    showLangMenu  = false;
  }

  function onLangToggle() {
    showLangMenu  = !showLangMenu;
    showLearnMenu = false;
    showViewMenu  = false;
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
    <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
    <div class="dropdown" transition:fly={{ y: -6, duration: 150 }} on:click|stopPropagation>

      <!-- ── Learn ── -->
      <button class="dd-item dd-group" on:click|stopPropagation={onLearnToggle}>
        <span class:group-active={page === 'learn' || page === 'learn-sr'}>Learn</span>
        <span class="chevron">{showLearnMenu ? '▴' : '▾'}</span>
      </button>
      {#if showLearnMenu}
        <div class="sub-panel" transition:fade={{ duration: 100 }}>
          <button
            class="dd-item sub-item"
            class:dd-active={page === 'learn'}
            on:click={() => navigate('learn')}
          >
            Normal
            {#if page === 'learn'}<span class="check">✓</span>{/if}
          </button>
          <button
            class="dd-item sub-item"
            class:dd-active={page === 'learn-sr'}
            on:click={() => navigate('learn-sr')}
          >
            SR Only
            {#if srQueue.length > 0}
              <span class="dd-badge">{srQueue.length}</span>
            {:else if page === 'learn-sr'}
              <span class="check">✓</span>
            {/if}
          </button>
        </div>
      {/if}

      <div class="dd-divider"></div>

      <!-- ── View ── -->
      <button class="dd-item dd-group" on:click|stopPropagation={onViewToggle}>
        <span class:group-active={page === 'stack-current' || page === 'stack-sr'}>View</span>
        <span class="chevron">{showViewMenu ? '▴' : '▾'}</span>
      </button>
      {#if showViewMenu}
        <div class="sub-panel" transition:fade={{ duration: 100 }}>
          <button
            class="dd-item sub-item"
            class:dd-active={page === 'stack-current'}
            on:click={() => navigate('stack-current')}
          >
            Current Stack
            {#if page === 'stack-current'}<span class="check">✓</span>{/if}
          </button>
          <button
            class="dd-item sub-item"
            class:dd-active={page === 'stack-sr'}
            on:click={() => navigate('stack-sr')}
          >
            SR Stack
            {#if page === 'stack-sr'}<span class="check">✓</span>{/if}
          </button>
        </div>
      {/if}

      <div class="dd-divider"></div>

      <!-- ── Language ── -->
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

    </div>
  {/if}
</div>

<style>
  .menu-wrap { position: relative; }

  .dots-btn {
    background: none;
    border: none;
    color: #444;
    cursor: pointer;
    padding: 6px 8px;
    line-height: 1;
    border-radius: 8px;
    font-size: 1.15rem;
    letter-spacing: 0.05em;
    transition: color 0.15s, background 0.15s;
  }
  .dots-btn:hover { color: #aaa; background: #1e1e1e; }

  .dropdown {
    position: absolute;
    right: 0;
    top: calc(100% + 4px);
    width: 220px;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 12px;
    overflow: hidden;
    z-index: 200;
    box-shadow: 0 8px 32px rgba(0,0,0,0.55);
  }

  .dd-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    background: none;
    border: none;
    color: #bbb;
    font-size: 0.88rem;
    padding: 0.65rem 1rem;
    cursor: pointer;
    text-align: left;
    transition: background 0.1s, color 0.1s;
  }
  .dd-item:hover  { background: #242424; color: #fff; }
  .dd-active      { color: #fff !important; font-weight: 600; }

  .dd-group       { color: #ddd; font-weight: 500; }
  .group-active   { color: #fff; }

  .dd-divider { height: 1px; background: #202020; margin: 2px 0; }

  .dd-badge {
    background: #c2410c;
    color: #fff;
    font-size: 0.68rem;
    font-weight: 700;
    border-radius: 10px;
    padding: 1px 7px;
  }

  .chevron { font-size: 0.6rem; color: #555; }

  .sub-panel { background: #141414; border-top: 1px solid #1e1e1e; }

  .sub-item {
    padding-left: 1.6rem;
    color: #888;
    font-size: 0.84rem;
  }
  .sub-item:hover { color: #ddd; }

  .dd-group em { font-style: normal; color: #666; font-weight: 400; }

  .check { color: #22c55e; font-size: 0.78rem; }
</style>
