// talks to cognito directly with fetch - its api is just json over https,
// didnt want to pull in the whole amplify sdk for 4 calls

const Auth = (() => {
  const { region, cognitoClientId } = window.APP_CONFIG;
  const endpoint = `https://cognito-idp.${region}.amazonaws.com/`;
  const KEY = "session";

  async function call(action, body) {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": `AWSCognitoIdentityProviderService.${action}`,
      },
      body: JSON.stringify({ ClientId: cognitoClientId, ...body }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.message || `Auth request failed (${res.status})`);
      err.code = (data.__type || "").split("#").pop(); // e.g. UserNotConfirmedException
      throw err;
    }
    return data;
  }

  // localStorage can throw in private mode etc, so everything's wrapped
  function load() {
    try {
      return JSON.parse(localStorage.getItem(KEY)) || null;
    } catch {
      return null;
    }
  }
  function save(session) {
    try {
      if (session) localStorage.setItem(KEY, JSON.stringify(session));
      else localStorage.removeItem(KEY);
    } catch {}
  }

  function store(result, email, refreshToken) {
    save({
      email,
      accessToken: result.AccessToken,
      refreshToken: result.RefreshToken || refreshToken,
      // refresh a minute early so a request doesn't land on an expired token
      expiresAt: Date.now() + (result.ExpiresIn - 60) * 1000,
    });
  }

  return {
    // no client id = running locally against dev_server.py, skip login
    enabled: Boolean(cognitoClientId),

    email: () => load()?.email,

    // cognito groups from the token. only used to hide stuff in the ui,
    // the api checks the real thing
    groups() {
      try {
        const payload = load().accessToken.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
        return JSON.parse(atob(payload))["cognito:groups"] || [];
      } catch {
        return [];
      }
    },

    signUp: (email, password) =>
      call("SignUp", { Username: email, Password: password, UserAttributes: [{ Name: "email", Value: email }] }),

    confirm: (email, code) => call("ConfirmSignUp", { Username: email, ConfirmationCode: code.trim() }),

    resendCode: (email) => call("ResendConfirmationCode", { Username: email }),

    async logIn(email, password) {
      const data = await call("InitiateAuth", {
        AuthFlow: "USER_PASSWORD_AUTH",
        AuthParameters: { USERNAME: email, PASSWORD: password },
      });
      store(data.AuthenticationResult, email);
    },

    logOut: () => save(null),

    // returns a valid access token, refreshing it if needed. null = logged out
    async token() {
      const session = load();
      if (!session) return null;
      if (Date.now() < session.expiresAt) return session.accessToken;
      try {
        const data = await call("InitiateAuth", {
          AuthFlow: "REFRESH_TOKEN_AUTH",
          AuthParameters: { REFRESH_TOKEN: session.refreshToken },
        });
        store(data.AuthenticationResult, session.email, session.refreshToken);
        return load().accessToken;
      } catch {
        save(null); // refresh token expired (30 days) or revoked
        return null;
      }
    },
  };
})();
