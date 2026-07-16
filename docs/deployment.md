# Deployment

## Architecture

- Frontend: Cloudflare Pages (`apps/web`)
- API: Render Docker web service (`render.yaml`)
- Initial deployment: Render Free web service for API verification

Cloudflare Pages must receive only `VITE_API_BASE_URL`. Do not add OpenAI, FMP,
or KRX keys to Pages because Vite exposes `VITE_*` variables to the browser.

## Render API (free verification)

1. In Render, choose **New > Blueprint** and select this GitHub repository.
2. Render detects `render.yaml`. Enter values when prompted for `OPENAI_API_KEY`
   and `FMP_API_KEY`. Leave `KRX_API_KEY` empty until KRX approval is complete.
3. Create the service, then open `https://<render-service>.onrender.com/health`.
   It must return `{"status":"ok"}`.
4. Copy the API origin, without a trailing slash.

Free Render web services stop after inactivity and use an ephemeral filesystem.
That means saved backtest results and cached OHLCV files disappear on a restart,
redeploy, or spin-down. This mode is suitable only for a no-cost demonstration.

## Persistent upgrade

When preserving backtest history is needed, upgrade the Render service to a paid
instance and add a disk at `/var/data` in **Settings > Disks**. The Docker image
already writes SQLite and market-data cache files there, so no code change is
needed. Set these environment variables after attaching the disk:

```text
ALPHALENS_DATABASE_PATH=/var/data/alphalens.db
ALPHALENS_MARKET_DATA_PATH=/var/data/market_data
```

## Cloudflare Pages

1. Open **Settings > Environment variables** for `alphalens-cds`.
2. Add `VITE_API_BASE_URL` with the Render API origin copied above.
3. Redeploy the production branch.

`ALPHALENS_ALLOWED_ORIGINS` in `render.yaml` already permits
`https://alphalens-cds.pages.dev`. Add a custom frontend domain to this value
before using that domain.
