# Campus Customs Operations Desk (frontend)

React + Vite + TypeScript dashboard for the Homework 5 agent team. It calls the Problem 7 FastAPI backend at `http://localhost:8000`. Set `VITE_API_BASE` in `.env.local` to change it (see `.env.example`).

## Run

Start the backend first, from `Homework-5/backend` with the HW5 venv active:

```bash
uvicorn main:app --reload --port 8000
```

Then, from `Homework-5/frontend`:

```bash
npm install
npm run dev
```

Open the URL Vite prints, normally http://localhost:5173. If 5173 is taken, Vite uses the next free port; the backend allows 5173–5179.

## Checks

```bash
npm run typecheck
npm run lint
npm test
npm run build
```

- `npm test` runs Vitest with Testing Library against a mocked backend built from real API snapshots (`src/test/fixtures.json`). It makes no network or Portkey calls.

Design notes: `../output/design.md`.
