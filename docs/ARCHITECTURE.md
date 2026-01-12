# TKFL OCR — Architecture Overview 📚

## Purpose
A concise reference for developers describing the application's structure, core components, data flows, and recommended areas for change or testing. Use this document when planning bug fixes, feature work, or refactors.

---

## 1) Quick Summary
- Web application that accepts receipt images, runs OCR, parses structured data (master/items/deductions), and stores results in PostgreSQL.
- Supports single-file uploads and bulk/queue workflows, with experimental "beta" OCR modes and quality-aware preprocessing.

---

## 2) High-level Components 🔧
- **App bootstrap**: `run.py` → calls `backend.create_app()` in `backend/__init__.py`.
- **Blueprints / Routes** (UI + API):
  - `backend/routes/main.py` — UI pages: index, upload, receipts, review, validate, batch pages, static file serving.
  - `backend/routes/api.py` — core upload & processing API endpoints (upload, re-extract, save validation, delete all).
  - `backend/routes/api_bulk.py` — batch upload endpoints (status/results/save).
  - `backend/routes/api_queue.py` — queue lifecycle API (create, crop, ocr, validate, skip, previous, save_batch).
  - `backend/routes/main_beta_v2.py`, `backend/routes/api_beta*.py` — beta/experimental flows.
- **Services**:
  - `backend/services/voucher_service.py` — DB operations: create/update vouchers, insert items/deductions, delete/reset.
  - `backend/services/batch_service.py` — create/update/complete batches and fetch batch+vouchers.
- **OCR & Parsing**:
  - `backend/ocr_service.py` (and variants `ocr_service_beta.py`, `ocr_roi_service.py`) — multiple preprocessing modes like `simple`, `enhanced`, `adaptive`, `optimal`, `aggressive`.
  - `backend/parser.py` / `backend/parser_beta.py` — transform raw OCR text into structured JSON.
  - `backend/dynamic_whitelist.py`, `backend/image_quality.py`, `backend/advanced_binarization.py` — helpers used by OCR.
- **DB Layer**: `backend/db.py` — connection pooling, fallback single connection for scripts, `init_db()` for schema creation. `init_beta_db.sql` and `migrate_beta_to_prod.py` support beta migrations.

---

## 3) Data Flow (Upload → Review) 🔁
1. Client uploads image → `api.upload_file`.
2. File saved to `UPLOAD_FOLDER`.
3. OCR run via `ocr_service.extract_text(...)` (returns text, confidence, other metadata).
4. Text parsed via `parser.parse_receipt_text(...)` → `parsed_data`.
5. `VoucherService.create_voucher(...)` saves master + items + deductions and metadata to Postgres.
6. User redirected to `main.review_voucher` to review and optionally validate; validated data saved via `api.save_validated_data`.

---

## 4) Database Notes
- Main tables in `backend/db.py`'s `init_db()`:
  - `vouchers_master`, `voucher_items`, `voucher_deductions`, `voucher_bboxes`.
- Beta tables exist under `*_beta` and can be migrated with `backend/migrate_beta_to_prod.py`.
- `DATABASE_URL` must be set prior to app initialization for pooling to be active; code contains fallback to create a standalone connection for scripts.

---

## 5) Notable Implementation Details & Pitfalls ⚠️
- Duplicate Flask route endpoints cause assertion errors (fixed by removing duplicates). When adding routes, ensure unique endpoint function names.
- `requirements.txt` has an incorrectly formatted line (space-separated, unpinned packages). Pinning dev/test deps and cleaning formatting is recommended for reproducible installs.
- OCR code prints debugging info to stdout. Prefer structured logging via `backend.logger` to capture telemetry and make logs test-friendly.
- `db.get_connection()` creates fallback connections for standalone scripts which may bypass pooled behavior — be careful when testing concurrency.

---

## 6) Testing & CI Recommendations ✅
- Add smoke test: import `create_app()` and assert blueprints registered and config loads.
- Unit tests for `VoucherService` (DB interactions), `parser.parse_receipt_text`, and `image_quality` helper functions.
- Integration test for `api.upload` that runs a small sample image through OCR & parser in a controlled environment (mock OCR or use a deterministic test image).
- Add GitHub Actions workflow to run linters and tests on PRs.

---

## 7) Developer Guidance / How to make safe changes
- Start by adding unit tests for the service or parser you intend to change.
- Use `run.py` to start dev server; use environment variables to switch configs (`FLASK_CONFIG` / `DATABASE_URL`).
- When changing DB schema, provide migration script and test with `migrate_beta_to_prod.py` if relevant.

---

## 8) Where to look for common tasks
- Add new UI route → `backend/routes/main.py` (+ template in `backend/templates/`).
- Add API endpoint → `backend/routes/api*.py` and test via `curl` / Postman.
- Modify OCR preprocessing → `backend/ocr_service.py`, and add unit tests for `preprocess_image_*` helpers.

---

## 9) Next suggested follow-ups
- Clean and pin `requirements.txt` and add test/dev dependencies.
- Replace `print(...)` debug statements in OCR modules with structured logging.
- Add an `ARCHITECTURE.md` section listing maintainers and contact points for beta vs prod flows.

---

_Last updated: generated automatically — please review and adjust as needed._
