/**
 * Firebase Authentication for super admins. Loaded on demand so students never download it.
 * Configure with VITE_FIREBASE_* in web/.env (see web/.env.example).
 */
const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const firebaseConfigured = Boolean(config.apiKey && config.projectId);

let authPromise;
async function getFirebaseAuth() {
  if (!authPromise) {
    authPromise = (async () => {
      const [{ initializeApp }, authMod] = await Promise.all([import("firebase/app"), import("firebase/auth")]);
      return { auth: authMod.getAuth(initializeApp(config)), mod: authMod };
    })();
  }
  return authPromise;
}

const FRIENDLY = {
  "auth/popup-closed-by-user": "The Google window was closed before signing in.",
  "auth/cancelled-popup-request": "The Google window was closed before signing in.",
  "auth/popup-blocked": "The browser blocked the Google window. Allow pop-ups for this site and try again.",
  "auth/invalid-credential": "Wrong email or password.",
  "auth/wrong-password": "Wrong email or password.",
  "auth/user-not-found": "Wrong email or password.",
  "auth/too-many-requests": "Too many attempts. Wait a few minutes and try again.",
  "auth/operation-not-allowed": "This sign-in method isn't enabled in your Firebase project (Authentication → Sign-in method).",
  "auth/unauthorized-domain": "This website's address isn't allowed in Firebase. Add it under Authentication → Settings → Authorized domains.",
  "auth/network-request-failed": "Can't reach Firebase. Check the internet connection.",
};

function friendly(err) {
  return new Error(FRIENDLY[err?.code] || err?.message || "Firebase sign-in failed");
}

/** Returns a Firebase ID token for the server to verify. */
export async function firebaseSignIn(method, email, password) {
  const { auth, mod } = await getFirebaseAuth();
  try {
    const cred = method === "google"
      ? await mod.signInWithPopup(auth, new mod.GoogleAuthProvider())
      : await mod.signInWithEmailAndPassword(auth, email, password);
    if (!cred.user.emailVerified) {
      await mod.sendEmailVerification(cred.user);
      await mod.signOut(auth);
      throw new Error("Your email isn't verified yet. We've sent a verification link to "
        + `${cred.user.email}. Open it, then sign in again.`);
    }
    const token = await cred.user.getIdToken();
    await mod.signOut(auth); // Reios issues its own session; don't keep a Firebase one around
    return token;
  } catch (err) {
    throw err instanceof Error && !err.code ? err : friendly(err);
  }
}
