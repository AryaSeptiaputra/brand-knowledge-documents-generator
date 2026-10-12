# Frontend

React 18, Vite, and TypeScript frontend for the Brand Knowledge Document Generator.

## Local development

Start the FastAPI backend at `http://127.0.0.1:8000`, then run:

```powershell
pnpm install
pnpm generate:api
pnpm dev
```

Vite proxies `/api` requests to the backend. Generate API types again after changing FastAPI request or response schemas.

## Checks

```powershell
pnpm test
pnpm lint
pnpm typecheck
pnpm build
```

The backend serves `frontend/dist` when that directory exists.
