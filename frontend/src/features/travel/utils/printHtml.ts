/**
 * Open the system print dialog with an HTML document.
 * Uses a hidden iframe to avoid popup blockers and noopener write restrictions.
 */
export function printHtmlContent(fullHtml: string): void {
  const iframe = document.createElement('iframe');
  iframe.setAttribute('title', 'travel-plan-print');
  iframe.style.cssText =
    'position:fixed;right:0;bottom:0;width:0;height:0;border:0;opacity:0;pointer-events:none';

  document.body.appendChild(iframe);

  const win = iframe.contentWindow;
  const doc = win?.document;
  if (!win || !doc) {
    iframe.remove();
    throw new Error('PRINT_FAILED');
  }

  doc.open();
  doc.write(fullHtml);
  doc.close();

  const cleanup = () => {
    iframe.remove();
  };

  const triggerPrint = () => {
    try {
      win.focus();
      win.print();
    } finally {
      window.setTimeout(cleanup, 1500);
    }
  };

  if (doc.readyState === 'complete') {
    window.setTimeout(triggerPrint, 150);
    return;
  }

  win.addEventListener(
    'load',
    () => {
      window.setTimeout(triggerPrint, 150);
    },
    { once: true },
  );
}
