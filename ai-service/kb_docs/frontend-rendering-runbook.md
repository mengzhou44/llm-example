# Frontend Rendering Runbook

## Chart / Data Visualization Issues

### Charts Blank on Mobile (< 768px)
**Symptom:** Bar, line, or pie charts render fine on desktop but show empty containers on mobile.

**Known Causes:**
1. **Zero-width container at render time.** Chart libraries (Chart.js, Recharts, D3) calculate dimensions synchronously on mount. If the parent container hasn't finished layout (common on mobile with deferred CSS), the chart renders into a 0×0 box and displays nothing.
2. **SVG viewBox not set.** SVG-based charts without an explicit `viewBox` collapse on small screens.
3. **ResizeObserver not triggered.** Some chart libraries only re-render on explicit resize events, which may not fire after orientation change on mobile.

**Diagnostic Steps:**
1. Open Chrome DevTools in mobile emulation mode (375px width). Check if chart container has `width: 0` or `height: 0` in the computed styles.
2. Add `console.log(containerRef.current.getBoundingClientRect())` inside the chart's `useEffect` to confirm dimensions at render time.
3. Check if disabling CSS transitions or lazy-loading resolves the issue (rules out a timing problem).

**Resolutions:**
- Wrap the chart in a `ResizeObserver` and force a re-render when dimensions change:
  ```js
  useEffect(() => {
    const observer = new ResizeObserver(() => setWidth(containerRef.current.offsetWidth));
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);
  ```
- Set an explicit `min-height` on the chart container so it never collapses to zero.
- Use `ResponsiveContainer` from Recharts (or equivalent) which handles resizing automatically.
- Defer chart rendering with `requestAnimationFrame` to ensure layout is complete.

---

## CSS / Layout Issues

### Responsive Breakpoints
All layout breakpoints use Tailwind's `sm` (640px), `md` (768px), `lg` (1024px). The `< 768px` breakpoint is `md` in Tailwind. Always use `md:hidden` / `block md:flex` patterns for mobile-first layouts.

### Z-Index Conflicts
Tooltips and dropdowns must use `z-50` or higher to render above modals and sticky headers.

---

## Performance

### Large Dataset Rendering
Tables and lists with > 500 rows must use virtual scrolling (react-window or react-virtual). Direct DOM rendering of large datasets causes jank and dropped frames on mobile CPUs.

### Bundle Size
Run `npm run build -- --analyze` to check bundle size. Any single chunk > 200 KB should be code-split.
