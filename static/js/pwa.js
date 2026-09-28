if ('serviceWorker' in navigator && window.isSecureContext) {
  window.addEventListener('load', () => {
    const workerUrl = document.querySelector('meta[name="school-service-worker"]')?.content;
    if (workerUrl) {
      navigator.serviceWorker.register(workerUrl, { updateViaCache: 'none' }).catch((error) => {
        console.warn('School app offline support could not start.', error);
      });
    }
  });
}
