// no framework, didnt need one for this

const API = window.APP_CONFIG.apiUrl.replace(/\/$/, "");
const form = document.getElementById("app-form");
const rows = document.getElementById("rows");
const errorEl = document.getElementById("error");
const submitBtn = document.getElementById("submit-btn");
const cancelBtn = document.getElementById("cancel-btn");

let applications = [];

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (Auth.enabled) {
    const token = await Auth.token();
    if (!token) return showAuth("login", "Your session expired, please log in again.");
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${API}${path}`, { ...options, headers });
  if (res.status === 401) {
    Auth.logOut();
    return showAuth("login", "Your session expired, please log in again.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

function render() {
  rows.replaceChildren(
    ...applications.map((app) => {
      const tr = document.createElement("tr");
      const company = app.url
        ? Object.assign(document.createElement("a"), { href: app.url, textContent: app.company, target: "_blank", rel: "noopener" })
        : document.createTextNode(app.company);
      // append/textContent not innerHTML - avoids xss from notes etc
      const role = [app.role, app.salary].filter(Boolean).join(" · ");
      const closes = app.closes_on ? `closes ${app.closes_on}` : "";
      const cells = [company, role, app.status, app.applied_on, closes];
      cells.forEach((value, i) => {
        const td = document.createElement("td");
        if (i === 2) td.className = `status status-${value}`;
        if (i === 4 && closingSoon(app)) td.className = "closing-soon";
        td.append(value);
        tr.append(td);
      });
      const actions = document.createElement("td");
      const wrap = document.createElement("div");
      wrap.className = "row-actions";
      wrap.append(button("Edit", () => startEdit(app)), button("Delete", () => remove(app)));
      actions.append(wrap);
      tr.append(actions);
      return tr;
    }),
  );
  document.getElementById("empty").hidden = applications.length > 0;
  const active = applications.filter((a) => ["applied", "interviewing"].includes(a.status)).length;
  document.getElementById("summary").textContent =
    `${applications.length} applications, ${active} still in progress`;
}

// still open and closes in the next week
function closingSoon(app) {
  if (!app.closes_on || app.status !== "applied") return false;
  const days = (new Date(app.closes_on) - new Date()) / 86400000;
  return days >= -1 && days <= 7;
}

function button(label, onClick) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "secondary small";
  b.textContent = label;
  b.addEventListener("click", onClick);
  return b;
}

async function load() {
  try {
    applications = (await request("/applications")) ?? [];
    render();
  } catch (err) {
    errorEl.textContent = `Could not load applications: ${err.message}`;
  }
}

function startEdit(app) {
  for (const [key, value] of Object.entries(app)) {
    if (form.elements[key]) form.elements[key].value = formValue(value);
  }
  submitBtn.textContent = "Save changes";
  cancelBtn.hidden = false;
  form.scrollIntoView({ behavior: "smooth" });
}

// skills is a list in the api but a comma separated box in the form
function formValue(value) {
  return Array.isArray(value) ? value.join(", ") : (value ?? "");
}

function resetForm() {
  form.reset();
  form.elements.id.value = "";
  form.elements.applied_on.valueAsDate = new Date();
  document.getElementById("ad-text").value = "";
  autofillMsg.textContent = "";
  submitBtn.textContent = "Add application";
  cancelBtn.hidden = true;
  errorEl.textContent = "";
}

async function remove(app) {
  if (!confirm(`Delete ${app.role} at ${app.company}?`)) return;
  await request(`/applications/${app.id}`, { method: "DELETE" });
  await load();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form));
  const id = data.id;
  delete data.id;
  if (!data.url) delete data.url;
  if (!data.closes_on) delete data.closes_on;
  if (!data.work_mode) delete data.work_mode;
  data.skills = data.skills.split(",").map((s) => s.trim()).filter(Boolean);
  try {
    await request(id ? `/applications/${id}` : "/applications", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(data),
    });
    resetForm();
    await load();
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

cancelBtn.addEventListener("click", resetForm);

// --- paste a job ad, ai fills the form in. you still check it and hit save ---

const autofillBtn = document.getElementById("autofill-btn");
const autofillMsg = document.getElementById("autofill-msg");

autofillBtn.addEventListener("click", async () => {
  const text = document.getElementById("ad-text").value.trim();
  if (text.length < 20) {
    autofillMsg.textContent = "Paste the job ad in first.";
    return;
  }
  autofillBtn.disabled = true;
  autofillMsg.textContent = "Reading the ad...";
  errorEl.textContent = "";
  try {
    const fields = await request("/extract", { method: "POST", body: JSON.stringify({ text }) });
    if (!fields) return;
    let filled = 0;
    for (const [key, value] of Object.entries(fields)) {
      // only fill what it found, dont wipe things you've typed
      if (!form.elements[key] || value == null || value === "" || value.length === 0) continue;
      form.elements[key].value = formValue(value);
      filled++;
    }
    autofillMsg.textContent = filled
      ? `Filled in ${filled} fields, check them over then save.`
      : "Couldn't find much in that, fill it in manually.";
  } catch (err) {
    autofillMsg.textContent = "";
    errorEl.textContent = err.message;
  } finally {
    autofillBtn.disabled = false;
  }
});

// --- login / sign up ---

const authSection = document.getElementById("auth");
const authForm = document.getElementById("auth-form");
const authError = document.getElementById("auth-error");
const authMsg = document.getElementById("auth-msg");
let authMode = "login"; // login | signup | confirm

function showAuth(mode, message = "") {
  authMode = mode;
  const titles = { login: "Log in", signup: "Create an account", confirm: "Check your email" };
  const buttons = { login: "Log in", signup: "Sign up", confirm: "Confirm" };
  document.getElementById("auth-title").textContent = titles[mode];
  document.getElementById("auth-submit").textContent = buttons[mode];
  document.getElementById("auth-toggle").textContent =
    mode === "login" ? "Need an account? Sign up" : "Already have an account? Log in";
  document.getElementById("password-field").hidden = mode === "confirm";
  authForm.elements.password.required = mode !== "confirm";
  authForm.elements.password.autocomplete = mode === "signup" ? "new-password" : "current-password";
  document.getElementById("code-field").hidden = mode !== "confirm";
  authForm.elements.code.required = mode === "confirm";
  document.getElementById("resend-btn").hidden = mode !== "confirm";
  authMsg.textContent = message;
  authError.textContent = "";
  authSection.hidden = false;
  document.getElementById("tracker").hidden = true;
  document.getElementById("account").hidden = true;
  document.getElementById("summary").textContent = "";
}

function showTracker() {
  authSection.hidden = true;
  document.getElementById("tracker").hidden = false;
  if (Auth.enabled) {
    document.getElementById("who").textContent = Auth.email();
    document.getElementById("account").hidden = false;
  }
  // auto-fill is only switched on for some accounts
  document.getElementById("autofill").hidden = Auth.enabled && !Auth.groups().includes("autofill");
  resetForm();
  load();
}

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const { email, password, code } = Object.fromEntries(new FormData(authForm));
  authError.textContent = "";
  try {
    if (authMode === "signup") {
      await Auth.signUp(email, password);
      showAuth("confirm", `We've emailed a code to ${email}.`);
    } else if (authMode === "confirm") {
      await Auth.confirm(email, code);
      if (authForm.elements.password.value) {
        await Auth.logIn(email, authForm.elements.password.value);
        showTracker();
      } else {
        showAuth("login", "Account confirmed, you can log in now.");
      }
    } else {
      await Auth.logIn(email, password);
      authForm.reset();
      showTracker();
    }
  } catch (err) {
    if (err.code === "UserNotConfirmedException") {
      showAuth("confirm", "You need to confirm your email first. Enter the code we sent you.");
    } else {
      authError.textContent = err.message;
    }
  }
});

document.getElementById("auth-toggle").addEventListener("click", () => {
  showAuth(authMode === "login" ? "signup" : "login");
});

document.getElementById("resend-btn").addEventListener("click", async () => {
  try {
    await Auth.resendCode(authForm.elements.email.value);
    authMsg.textContent = "Sent a new code.";
  } catch (err) {
    authError.textContent = err.message;
  }
});

document.getElementById("logout-btn").addEventListener("click", () => {
  Auth.logOut();
  applications = [];
  showAuth("login");
});

// start
if (Auth.enabled && !Auth.email()) showAuth("login");
else showTracker();
