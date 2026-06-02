import DOMPurify from 'dompurify';

/**
 * Sanitize HTML before it is handed to `dangerouslySetInnerHTML`.
 *
 * Notes are user-authored and rendered via `marked`, and search highlights are
 * server-generated HTML. `marked` does NOT sanitize, so an untrusted note like
 * `<img src=x onerror=...>` would execute on render and could exfiltrate the
 * access/refresh tokens we keep in localStorage (UI_REVIEW U-2 / AUDIT P1-5).
 * Every HTML string that reaches the DOM via dangerouslySetInnerHTML MUST pass
 * through here first.
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
}
