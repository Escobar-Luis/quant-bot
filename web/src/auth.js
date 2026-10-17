// Google sign-in and sign-out through Clerk (headless: our own button).
// Without a publishable key the app still runs, with a local stand-in
// sign-in, so the design can ship before the Clerk app exists.
import { Clerk } from '@clerk/clerk-js';

const PK = __CLERK_PK__;
const CALLBACK = 'sso-callback';
let clerk = null;
let fakeUser = null;

export const hasClerk = () => !!PK;

export async function initAuth(onChange) {
  if (!PK) {
    try { fakeUser = JSON.parse(sessionStorage.getItem('dta-fake-user') || 'null'); } catch (_) { fakeUser = null; }
    onChange(currentUser());
    return;
  }
  clerk = new Clerk(PK);
  await clerk.load();
  const qs = new URLSearchParams(location.search);
  if (qs.has(CALLBACK)) {
    try {
      await clerk.handleRedirectCallback({
        signInFallbackRedirectUrl: home(''),
        signUpFallbackRedirectUrl: home('')
      });
    } catch (e) {
      console.warn('Sign-in callback failed', e);
      history.replaceState(null, '', home('#signin'));
    }
  }
  clerk.addListener(() => onChange(currentUser()));
  onChange(currentUser());
}

// Keep the page's own query (e.g. ?still=1) through the Google round trip.
function home(hash) {
  const q = new URLSearchParams(location.search);
  q.delete(CALLBACK);
  [...q.keys()].filter(k => k.startsWith('__clerk')).forEach(k => q.delete(k));
  const s = q.toString();
  return location.origin + location.pathname + (s ? '?' + s : '') + hash;
}

export function currentUser() {
  if (!PK) return fakeUser;
  const u = clerk && clerk.user;
  if (!u) return null;
  const name = u.fullName || u.firstName || u.primaryEmailAddress?.emailAddress || 'You';
  return { name, initials: initials(name), image: u.imageUrl || '' };
}

function initials(name) {
  const p = name.replace(/@.*/, '').split(/[\s._-]+/).filter(Boolean);
  return ((p[0]?.[0] || '') + (p[1]?.[0] || '')).toUpperCase() || 'ME';
}

export async function signInWithGoogle() {
  if (!PK) {
    fakeUser = { name: 'Guest', initials: 'G', image: '' };
    try { sessionStorage.setItem('dta-fake-user', JSON.stringify(fakeUser)); } catch (_) {}
    return fakeUser;
  }
  await clerk.client.signIn.authenticateWithRedirect({
    strategy: 'oauth_google',
    redirectUrl: (() => { const u = new URL(home('')); u.searchParams.set(CALLBACK, ''); return u.toString(); })(),
    redirectUrlComplete: home('')
  });
  return null;
}

export async function signOut() {
  if (!PK) {
    fakeUser = null;
    try { sessionStorage.removeItem('dta-fake-user'); } catch (_) {}
    return;
  }
  await clerk.signOut();
}
