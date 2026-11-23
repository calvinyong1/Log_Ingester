# Log Monitor — dashboard

Vite + React + TypeScript. Polls the backend (`/logs`, `/logs/histogram`,
`/logs/services`, `/services/error-rates` and `/alerts`) and renders a live
event feed, a stacked-by-severity time chart, a services rail, alert history,
and filters (service, levels, message search, time range including a custom From/To), with Pause and pagination.

## Develop

```bash
npm install
npm run dev
```

Requires the backend API running (see the repo root `README.md`); set
`VITE_API_URL` in `.env` if it's not at `http://localhost:8000`. The "Pipeline" section embeds Grafana panels from `VITE_GRAFANA_URL` (default `http://localhost:3000`).

## Scripts

- `npm run dev` — dev server with HMR
- `npm run build` — typecheck + production build
- `npm run test` — component tests (Vitest + Testing Library)
- `npm run lint` — ESLint

## Production image

The default Docker target builds the bundle and serves it with nginx on port
8080. `VITE_API_URL` is baked in at build time, so pass it as a build arg:

```bash
docker build --build-arg VITE_API_URL=https://api.example.com -t dashboard .
# VITE_GRAFANA_URL is a build arg too
```

`docker-compose.yml` builds the `dev` target instead (Vite with HMR).
