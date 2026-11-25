const RIGHTS = {
  SRE:     ["Просмотр трейсов", "Просмотр аудита", "Просмотр PII"],
  DEV:     ["Просмотр трейсов"],
  ADMIN:   ["Просмотр трейсов", "Просмотр аудита", "Управление политиками", "Просмотр PII"],
  AUDITOR: ["Просмотр трейсов", "Просмотр аудита", "Просмотр PII"],
};

async function loadUsers() {
  const r = await fetch("/api/users");
  const data = await r.json();
  const sel = document.getElementById("username");
  for (const u of data.users) {
    const opt = document.createElement("option");
    opt.value = u.username;
    opt.textContent = `${u.display_name} — ${u.role_label}`;
    opt.dataset.role = u.role;
    sel.appendChild(opt);
  }
}

function showRole(role) {
  const box = document.getElementById("role-info");
  if (!role) { box.hidden = true; return; }
  box.hidden = false;
  document.getElementById("role-name").textContent = role;
  document.getElementById("role-rights").textContent =
    (RIGHTS[role] || []).join(", ");
}

document.addEventListener("DOMContentLoaded", async () => {
  await loadUsers();
  const sel = document.getElementById("username");
  sel.addEventListener("change", () => {
    const opt = sel.selectedOptions[0];
    showRole(opt?.dataset?.role || "");
  });

  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = sel.value;
    if (!username) return;
    const btn = e.target.querySelector("button");
    btn.disabled = true;
    try {
      const r = await fetch("/api/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({username}),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.error || "login failed");
      }
      window.location.href = "/";
    } catch (err) {
      const box = document.getElementById("error");
      box.hidden = false;
      box.textContent = err.message;
      btn.disabled = false;
    }
  });
});