# Changelog

## 1.0.2 (2026-07-24)

### Added
- **Clipboard paste image upload**: Admin can Ctrl+V paste images directly onto the question editor page
- **Deferred image upload**: Images are previewed locally first; upload to R2 happens together with question save
- **Question import/export**:
  - Export all questions as downloadable JSON file (GET `/admin/questions/export`)
  - Bulk-import questions from JSON file (POST `/admin/questions/import`)
  - Export filename includes minutes/seconds (e.g. `questions-2026-07-24_09-35-22.json`)
- **Prev/next navigation**: Question detail page has «上一题 / 下一题» buttons to browse questions within the current list page
- **Question ID display**: Visible ID column in the question list table, and ID shown on the detail page
- **Server-side column sorting**: Click ID/difficulty/answer column headers to sort the full dataset (not just the current page)

### Changed
- Image upload flow: no longer uploads immediately on file selection; waits for save button
- Export/import buttons moved from toolbar pill buttons to muted text links in the toolbar
- Question list returns `answer` field (correct font name) in the API response
- Star-difficulty label on detail page changed from `★★★ 难度` to `难度 ★★★`

### Fixed
- Route conflict: added `:int` type constraint to `{question_id}` path parameters to prevent export/import routes from being intercepted
- Import validation: `image_url` accepts `null` values, and extra JSON fields (`id`, `created_at`, `updated_at`) are silently ignored
- Narrow-screen layout: export/import buttons no longer overflow or wrap incorrectly

### Version
- Bumped from `0.1.0` → `1.0.2`
