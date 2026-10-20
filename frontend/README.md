# Log Anomaly Detection — dashboard

Vite + React + TypeScript. Polls `GET /logs` on the backend, renders a live
event feed, a stacked-by-severity time chart, and filters (service, level,
time range).

## Develop

```bash
npm install
npm run dev
```

Requires the backend API running (see the repo root `README.md`); set
`VITE_API_URL` in `.env` if it's not at `http://localhost:8000`.

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
```

`docker-compose.yml` builds the `dev` target instead (Vite with HMR).
