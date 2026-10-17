import { defineConfig } from 'vite';
import { readFileSync, existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

// The Clerk publishable key is public by design. It comes from the host's
// env (Vercel, Ninoo) or, locally, from ~/dev/quant-bot/.env. Never logged.
function clerkKey() {
  const fromEnv = process.env.CLERK_PUBLISHABLE_KEY || process.env.VITE_CLERK_PUBLISHABLE_KEY;
  if (fromEnv) return fromEnv.trim();
  const file = join(homedir(), 'dev/quant-bot/.env');
  if (!existsSync(file)) return '';
  const line = readFileSync(file, 'utf8').split('\n').find(l => /^\s*(VITE_)?CLERK_PUBLISHABLE_KEY\s*=/.test(l));
  return line ? line.split('=').slice(1).join('=').trim().replace(/^['"]|['"]$/g, '') : '';
}

export default defineConfig({
  define: { __CLERK_PK__: JSON.stringify(clerkKey()) },
  // results/ and proofs/ live at the repo root, one level up.
  server: { fs: { allow: ['..'] } },
  build: { target: 'es2022' }
});
