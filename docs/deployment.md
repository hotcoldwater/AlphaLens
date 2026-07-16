# Deployment

## Architecture

- Frontend: Cloudflare Pages (`apps/web`)
- API: Render Docker web service (`render.yaml`)
- Persistence: Render disk at `/var/data` for SQLite results and cached market data

Cloudflare Pages must receive only `VITE_API_BASE_URL`. Do not add OpenAI, FMP,
or KRX keys to Pages because Vite exposes `VITE_*` variables to the browser.

## Render API

1. In Render, choose **New > Blueprint** and select this GitHub repository.
2. Render detects `render.yaml`. Enter values when prompted for `OPENAI_API_KEY`
   and `FMP_API_KEY`. Leave `KRX_API_KEY` empty until KRX approval is complete.
3. Create the service, then open `https://<render-service>.onrender.com/health`.
   It must return `{"status":"ok"}`.
4. Copy the API origin, without a trailing slash.

The configured persistent disk is required because Render otherwise removes local
SQLite and cached OHLCV files whenever the service restarts or redeploys.

## Cloudflare Pages

1. Open **Settings > Environment variables** for `alphalens-cds`.
2. Add `VITE_API_BASE_URL` with the Render API origin copied above.
3. Redeploy the production branch.

`ALPHALENS_ALLOWED_ORIGINS` in `render.yaml` already permits
`https://alphalens-cds.pages.dev`. Add a custom frontend domain to this value
before using that domain.
