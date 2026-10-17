#!/usr/bin/env bash
# Ninoo Builder imports a whole repo or a ZIP. This makes a ZIP whose root is
# the app, with results/ and proofs/ JSON copied in and the (public) Clerk
# publishable key in .env, so Ninoo needs nothing from the rest of the repo.
# Usage: ./pack-ninoo.sh  ->  web/ninoo/day-trader-ai.zip
set -euo pipefail
cd "$(dirname "$0")"
out="$PWD/ninoo"; tmp="$(mktemp -d)"; app="$tmp/day-trader-ai"
mkdir -p "$app" "$out"
cp -R index.html package.json package-lock.json vite.config.js src "$app/"
mkdir -p "$app/results" "$app/proofs"
(cd .. && find results -name '*.json' | while read -r f; do mkdir -p "$app/$(dirname "$f")"; cp "$f" "$app/$f"; done)
[ -f ../proofs/prism.json ] && cp ../proofs/prism.json "$app/proofs/"
key="${CLERK_PUBLISHABLE_KEY:-$(grep -E '^CLERK_PUBLISHABLE_KEY=' "$HOME/dev/quant-bot/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)}"
[ -n "$key" ] && printf 'CLERK_PUBLISHABLE_KEY=%s\n' "$key" > "$app/.env"
printf 'node_modules/\ndist/\n' > "$app/.gitignore"
rm -f "$out/day-trader-ai.zip"
(cd "$tmp" && zip -qr "$out/day-trader-ai.zip" day-trader-ai)
rm -rf "$tmp"
echo "$out/day-trader-ai.zip"
[ -n "$key" ] && echo "Clerk key: included" || echo "Clerk key: missing (stand-in sign-in)"
