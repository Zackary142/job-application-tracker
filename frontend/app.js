// no framework, didnt need one for this

const API = window.APP_CONFIG.apiUrl.replace(/\/$/, "");
const form = document.getElementById("app-form");
const rows = document.getElementById("rows");
const errorEl = document.getElementById("error");
const submitBtn = document.getElementById("submit-btn");
const cancelBtn = document.getElementById("cancel-btn");

let applications = [];

async function request(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
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
      const cells = [company, app.role, app.status, app.applied_on];
      cells.forEach((value, i) => {
        const td = document.createElement("td");
        if (i === 2) td.className = `status status-${value}`;
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
    applications = await request("/applications");
    render();
  } catch (err) {
    errorEl.textContent = `Could not load applications: ${err.message}`;
  }
}

function startEdit(app) {
  for (const [key, value] of Object.entries(app)) {
    if (form.elements[key]) form.elements[key].value = value ?? "";
  }
  submitBtn.textContent = "Save changes";
  cancelBtn.hidden = false;
  form.scrollIntoView({ behavior: "smooth" });
}

function resetForm() {
  form.reset();
  form.elements.id.value = "";
  form.elements.applied_on.valueAsDate = new Date();
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
resetForm();
load();
