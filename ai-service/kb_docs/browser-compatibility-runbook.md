# Browser Compatibility Runbook

## Safari-Specific Issues

### Login Page Blank Screen (Safari 17+)
**Symptom:** Users on Safari 17+ see a white/blank screen at `/login`.

**Known Causes:**
- Safari 17 enforces stricter Content Security Policy (CSP) rules. Inline `<script>` tags or `eval()` calls will be silently blocked.
- Safari 17 dropped support for `document.domain` mutation. Apps that rely on it for subdomain auth will break silently.
- WebKit's ITP (Intelligent Tracking Prevention) may block third-party cookies used for session tokens.

**Diagnostic Steps:**
1. Open Safari DevTools → Console: look for CSP violation errors or blocked script warnings.
2. Check the Network tab: does `/login` return 200 but fail to execute JS?
3. Test with a clean Safari profile (no extensions) to rule out content blockers.
4. Check if the issue also occurs on Safari on iOS — same WebKit engine.

**Resolutions:**
- Add a strict CSP header that explicitly allows `self` and any CDN origins.
- Replace `eval()` and `new Function()` with safe alternatives.
- Move session tokens from cookies to `localStorage` or `sessionStorage` if ITP is the cause.
- Ensure the login bundle has no `document.domain` assignments.

---

## Firefox-Specific Issues

### Mixed Content Warnings
Firefox blocks HTTP sub-resources on HTTPS pages. Ensure all assets (fonts, scripts, images) are served over HTTPS.

### IndexedDB in Private Mode
Firefox disables IndexedDB in private browsing. Do not use IndexedDB as a required storage mechanism for authentication flows.

---

## Cross-Browser CSS Issues

### Flexbox on Safari
Safari has known bugs with `gap` on flexbox containers (pre-2021). Use `margin` as a fallback.

### CSS Grid on IE/Edge Legacy
CSS Grid spec differs slightly from the old Edge implementation. Always test grid layouts on major browsers.

---

## General Debugging Checklist
- Test on Chrome (latest), Firefox (latest), Safari (latest + -1), and Edge.
- Use BrowserStack or LambdaTest for mobile browser coverage.
- Enable verbose logging in staging to capture JS errors from all browsers.
