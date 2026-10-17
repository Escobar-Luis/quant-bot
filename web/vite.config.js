import { defineConfig, loadEnv } from 'vite';
import { readFileSync, existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

// The Clerk publishable key is public by design. It comes from the host's
// env, web/.env (the Ninoo ZIP) or, locally, ~/dev/quant-bot/.env. Never logged.
function clerkKey(mode) {
  const env = { ...loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), ''), ...process.env };
  const fromEnv = env.CLERK_PUBLISHABLE_KEY || env.VITE_CLERK_PUBLISHABLE_KEY;
  if (fromEnv) return fromEnv.trim();
  const file = join(homedir(), 'dev/quant-bot/.env');
  if (!existsSync(file)) return '';
  const line = readFileSync(file, 'utf8').split('\n').find(l => /^\s*(VITE_)?CLERK_PUBLISHABLE_KEY\s*=/.test(l));
  return line ? line.split('=').slice(1).join('=').trim().replace(/^['"]|['"]$/g, '') : '';
}

export default defineConfig(({ mode }) => ({
  define: { __CLERK_PK__: JSON.stringify(clerkKey(mode)) },
  // results/ and proofs/ live at the repo root, one level up.
  server: { fs: { allow: ['.', '../results', '../proofs'] } },
  build: { target: 'es2022' }
}));
