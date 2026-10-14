# Web Visual Baselines

Captured locally against the Vite development server with a migrated temporary SQLite database on 2026-07-22. These are historical visual baselines, not a claim that the current UI is pixel-identical. “Viewport” is the requested browser viewport; the in-app browser capture API omits scrollbar chrome, so the vertically scrollable editor raster is 1425 × 891 while it was rendered in a 1440 × 900 viewport.

| View | Viewport | Baseline |
| --- | --- | --- |
| Public home | 1440 × 900 | [web-home-1440x900.png](web-home-1440x900.png) |
| Public home | 1024 × 900 | [web-home-1024x900.png](web-home-1024x900.png) |
| Public home | 768 × 900 | [web-home-768x900.png](web-home-768x900.png) |
| Public home (200% logical-width equivalent) | 720 × 900 | [web-home-720x900-zoom-equivalent.png](web-home-720x900-zoom-equivalent.png) |
| Difficulty selection | 1440 × 900 | [web-levels-1440x900.png](web-levels-1440x900.png) |
| Quiz | 1440 × 900 | [web-quiz-1440x900.png](web-quiz-1440x900.png) |
| Result | 1440 × 900 | [web-result-1440x900.png](web-result-1440x900.png) |
| Administrator question list | 1440 × 900 | [web-admin-questions-1440x900.png](web-admin-questions-1440x900.png) |
| Administrator question editor | 1440 × 900 | [web-admin-question-editor-1425x891.png](web-admin-question-editor-1425x891.png) |
| Font reference empty state | 1440 × 900 | [web-font-reference-1440x900.png](web-font-reference-1440x900.png) |

The administrator screenshot uses a temporary test account and two temporary acceptance questions. The two broken image thumbnails demonstrate the implemented image-error state because that historical fixture intentionally used unserved legacy image URLs.

## Accessibility checks

- Keyboard: the current quiz page uses focused buttons for font options and page-level `ArrowLeft`/`ArrowRight` handlers for previous/next question navigation. The older focused-radio B-to-C check belongs to the historical capture and is not a current implementation contract.
- Reduced motion: with `prefers-reduced-motion: reduce` emulated, the answer option computed `transitionDuration` was `0s`.
- 200% logical-width equivalent: at 720 CSS px (the layout width a 1440 px viewport reaches at 200% scaling), `scrollWidth` did not exceed `clientWidth`; the compact baseline is saved above. A target-browser manual zoom check remains part of release smoke testing.

These files verify desktop two-column public layout, 768 px stacking, the 232 px administrator sidebar, and the warm visual token system. Production domain, real image-host delivery, high-contrast mode, true browser zoom, and WeChat-device checks remain deployment acceptance work.
