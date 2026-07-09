export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * Open a PDF blob and jump straight to the browser's print dialog (no download).
 * The OS dialog still appears — the browser sandbox can't print silently — but
 * the user only has to pick their label printer and confirm. Set the printer to
 * the 75x125mm media and "Actual size" so tags aren't rescaled.
 */
export function printBlob(blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const iframe = document.createElement('iframe');
  iframe.style.position = 'fixed';
  iframe.style.right = '0';
  iframe.style.bottom = '0';
  iframe.style.width = '0';
  iframe.style.height = '0';
  iframe.style.border = '0';
  iframe.src = url;

  let cleaned = false;
  const cleanup = () => {
    if (cleaned) return;
    cleaned = true;
    URL.revokeObjectURL(url);
    iframe.remove();
  };

  iframe.onload = () => {
    const win = iframe.contentWindow;
    if (!win) {
      window.open(url, '_blank');
      return;
    }
    // Revoke only once the dialog is dismissed — never mid-print, however long
    // the user spends configuring the printer.
    win.addEventListener('afterprint', cleanup);
    try {
      win.focus();
      win.print();
    } catch {
      // some browsers block iframe PDF printing — fall back to a new tab
      window.open(url, '_blank');
      cleanup();
    }
  };
  document.body.appendChild(iframe);
}
