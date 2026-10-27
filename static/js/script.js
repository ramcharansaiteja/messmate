/**
 * MessMate Legacy / Placeholder Script
 * The primary script has moved to main.js.
 */
// Load main.js if not already loaded
if (!window.MessMate) {
  const script = document.createElement('script');
  script.src = '/static/js/main.js';
  script.defer = true;
  document.head.appendChild(script);
}
