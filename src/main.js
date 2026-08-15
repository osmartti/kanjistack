import App from './App.svelte';
import { registerSW } from 'virtual:pwa-register';

// Silently keep the cached app + datasets up to date in the background
// whenever the user is online; no prompt shown to the user.
registerSW({ immediate: true });

const app = new App({ target: document.getElementById('app') });

export default app;
