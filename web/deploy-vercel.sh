#!/usr/bin/env bash
# Fallback deploy: build here (results/ and proofs/ baked in, Clerk key from
# the env or ~/dev/quant-bot/.env), then upload the static files to Vercel.
# Usage: ./deploy-vercel.sh [--prod]
set -euo pipefail
cd "$(dirname "$0")"
npm ci --silent
npx vite build
rm -rf .vercel/output && mkdir -p .vercel/output
cp -R dist .vercel/output/static
printf '{"version":3}\n' > .vercel/output/config.json
[ -f .vercel/project.json ] || npx -y vercel@latest link --yes --project day-trader-ai >/dev/null
npx -y vercel@latest deploy --prebuilt --yes "$@"
