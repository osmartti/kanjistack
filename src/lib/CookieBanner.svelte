<script>
	const STORAGE_KEY = "cookie_consent";
	const GA_ID = "G-QQNTTVYMBC";

	let visible = localStorage.getItem(STORAGE_KEY) === null;

	function loadGA() {
		const script = document.createElement("script");
		script.async = true;
		script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
		document.head.appendChild(script);

		window.dataLayer = window.dataLayer || [];
		function gtag() {
			window.dataLayer.push(arguments);
		}
		window.gtag = gtag;
		gtag("js", new Date());
		gtag("config", GA_ID);
	}

	function accept() {
		localStorage.setItem(STORAGE_KEY, "accepted");
		loadGA();
		visible = false;
	}

	function decline() {
		localStorage.setItem(STORAGE_KEY, "declined");
		visible = false;
	}
</script>

{#if visible}
	<div class="cookie-banner">
		<p>
			This site uses Google Analytics to understand visitor traffic. No personal data is sold or
			shared with third parties.
			<a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer"
				>Learn more</a
			>
		</p>
		<div class="cookie-banner-actions">
			<button class="btn-accept" on:click={accept}>Accept</button>
			<button class="btn-decline" on:click={decline}>Decline</button>
		</div>
	</div>
{/if}

<style>
	.cookie-banner {
		position: fixed;
		bottom: 0;
		left: 0;
		width: 100%;
		background-color: var(--c-bg2);
		color: var(--c-text);
		border-top: 1px solid var(--c-border);
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.85rem 1.25rem;
		z-index: 1000;
		font-size: 0.85rem;
		flex-wrap: wrap;
		box-sizing: border-box;
	}

	.cookie-banner p {
		margin: 0;
		flex: 1;
		color: var(--c-muted2);
	}

	.cookie-banner a {
		color: var(--c-on);
	}

	.cookie-banner-actions {
		display: flex;
		gap: 0.75rem;
		flex-shrink: 0;
	}

	.btn-accept,
	.btn-decline {
		padding: 0.4rem 1.2rem;
		border-radius: 6px;
		cursor: pointer;
		font-size: 0.85rem;
	}

	.btn-accept {
		border: 1px solid var(--c-on);
		background-color: var(--c-on);
		color: var(--c-bg);
	}

	.btn-decline {
		background-color: transparent;
		color: var(--c-text);
		border: 1px solid var(--c-muted);
	}

	@media (max-width: 500px) {
		.cookie-banner {
			flex-direction: column;
			align-items: flex-start;
			padding: 0.85rem 1rem;
			gap: 0.75rem;
		}

		.cookie-banner-actions {
			width: 100%;
		}

		.btn-accept,
		.btn-decline {
			flex: 1;
		}
	}
</style>
