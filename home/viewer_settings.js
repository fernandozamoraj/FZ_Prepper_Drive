// Replaces kiwix-serve's built-in /viewer_settings.js (via KIWIX_SERVE_CUSTOMIZED_RESOURCES in serve.sh).
// First part: kiwix-serve 3.8.2's own default settings, unchanged.
const viewerSettings = {
  toolbarEnabled:       true,
  linkBlockingEnabled:  false,
  libraryButtonEnabled: true
}

// Offline prepper kit v1.9.0: add the kit's header bar (Home · Library · Bible · Maps) above the
// library viewer. This script runs while the viewer page is still loading, so a plain script tag works.
document.write('<script src="/nav.js"><\/script>');
