const state = {
  user: null,
  csrfToken: null,
  reference: null,
  activeTab: "overview",
};

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function $(selector, root = document) {
  return root.querySelector(selector);
}

function $all(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.csrfToken) headers["x-csrf-token"] = state.csrfToken;
  const response = await fetch(path, { credentials: "same-origin", ...options, headers });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Request failed");
  return payload;
}

function show(view) {
  $all("[data-view]").forEach((node) => node.classList.toggle("hidden", node.dataset.view !== view));
}

function context() {
  return {
    role: $("#globalRole").value,
    level: $("#globalLevel").value,
    location: $("#globalLocation").value,
  };
}

function params(values) {
  return new URLSearchParams(values).toString();
}

function fillSelect(select, items, valueKey, labelKey, selectedValue) {
  select.innerHTML = items
    .map((item) => `<option value="${item[valueKey]}">${item[labelKey]}</option>`)
    .join("");
  if (selectedValue) select.value = selectedValue;
}

function hydrateControls() {
  const { roleFamilies, levels, locations } = state.reference;
  fillSelect($("#globalRole"), roleFamilies, "slug", "name", "software-engineering");
  fillSelect($("#globalLevel"), levels, "code", "code", "L5");
  fillSelect($("#globalLocation"), locations, "slug", "name", "remote-us");

  $all("[data-cohort]").forEach((cohort, index) => {
    fillSelect($("[data-field='role']", cohort), roleFamilies, "slug", "name", "software-engineering");
    fillSelect($("[data-field='level']", cohort), levels, "code", "code", index === 0 ? "L5" : "L6");
    fillSelect($("[data-field='location']", cohort), locations, "slug", "name", "remote-us");
  });

  const form = $("#submissionForm");
  fillSelect($("[name='role']", form), roleFamilies, "slug", "name", "software-engineering");
  fillSelect($("[name='level']", form), levels, "code", "code", "L5");
  fillSelect($("[name='location']", form), locations, "slug", "name", "remote-us");
}

function metric(label, value, detail = "") {
  return `<div class="metric"><span>${label}</span><strong>${value}</strong>${detail ? `<small>${detail}</small>` : ""}</div>`;
}

function renderMix(summary, target) {
  target.innerHTML = `
    <div class="mix-bar" aria-label="Median compensation structure">
      <span class="base" style="width:${summary.baseShare}%"></span>
      <span class="bonus" style="width:${summary.bonusShare}%"></span>
      <span class="equity" style="width:${summary.equityShare}%"></span>
    </div>
    <div class="legend">
      <span><i class="base-key"></i>Base ${summary.baseShare}%</span>
      <span><i class="bonus-key"></i>Bonus ${summary.bonusShare}%</span>
      <span><i class="equity-key"></i>Equity ${summary.equityShare}%</span>
    </div>
    <div class="mix-numbers">
      ${metric("Base", money.format(summary.baseMedian))}
      ${metric("Bonus", money.format(summary.bonusMedian))}
      ${metric("Equity", money.format(summary.equityMedian))}
    </div>
  `;
}

function renderOverview(data) {
  const summary = data.summary;
  $("#overviewMetrics").innerHTML = [
    metric("Median total", money.format(summary.median), `${summary.count} comparable records`),
    metric("Market range", `${money.format(summary.p25)} - ${money.format(summary.p75)}`, "P25 to P75 total compensation"),
    metric("Level signal", $("#globalLevel").value, "Primary comparison anchor"),
    metric("Confidence", `${Math.round(summary.confidence * 100)}%`, "Weighted source confidence"),
  ].join("");

  $("#recordsTable").innerHTML = data.records
    .map((record) => {
      const total = record.base_salary + record.bonus + record.equity_annual_value;
      return `<tr>
        <td>${record.company_name}<small>${record.company_stage} · ${record.company_size}</small></td>
        <td>${record.role_name}</td>
        <td><strong>${record.level_code}</strong><small>${record.level_name}</small></td>
        <td>${record.location_name}</td>
        <td>${money.format(total)}</td>
        <td>${money.format(record.base_salary)} / ${money.format(record.bonus)} / ${money.format(record.equity_annual_value)}</td>
      </tr>`;
    })
    .join("");
  renderMix(summary, $("#overviewStructure"));
}

async function loadOverview() {
  const data = await api(`/api/benchmarks?${params(context())}`);
  renderOverview(data);
}

async function loadLevelMap() {
  const { role, location } = context();
  const data = await api(`/api/levels/matrix?${params({ role, location })}`);
  const max = Math.max(...data.levels.map((item) => item.summary.median), 1);
  $("#levelMap").innerHTML = data.levels
    .map((item) => {
      const width = Math.max((item.summary.median / max) * 100, 5);
      return `<article class="level-row">
        <div>
          <strong>${item.level.code}</strong>
          <span>${item.level.name}</span>
          <p>${item.level.scope}</p>
        </div>
        <div class="level-value">
          <b>${money.format(item.summary.median)}</b>
          <small>${item.stepUp ? `+${money.format(item.stepUp)} from prior level (${item.stepUpPercent}%)` : "Entry point for this ladder"}</small>
          <span class="progress"><i style="width:${width}%"></i></span>
        </div>
      </article>`;
    })
    .join("");
}

async function runCompare() {
  const cohorts = $all("[data-cohort]").map((cohort) => ({
    role: $("[data-field='role']", cohort).value,
    level: $("[data-field='level']", cohort).value,
    location: $("[data-field='location']", cohort).value,
  }));
  const data = await api("/api/compare", { method: "POST", body: JSON.stringify({ cohorts }) });
  $("#compareResults").innerHTML = data.cohorts
    .map((cohort) => {
      const deltaClass = cohort.deltaFromBaseline >= 0 ? "good" : "warn";
      return `<article class="compare-card">
        <h4>${cohort.label}</h4>
        <strong>${money.format(cohort.summary.median)}</strong>
        <p>${money.format(cohort.summary.baseMedian)} base · ${money.format(cohort.summary.bonusMedian)} bonus · ${money.format(cohort.summary.equityMedian)} equity</p>
        <span class="delta ${deltaClass}">${cohort.deltaPercent}% vs baseline (${money.format(cohort.deltaFromBaseline)})</span>
      </article>`;
    })
    .join("");
}

async function loadStructure() {
  const data = await api(`/api/structure?${params(context())}`);
  $("#structureInsights").innerHTML = `
    <div class="structure-summary"></div>
    ${data.mixes
      .map(
        (mix) => `<article class="structure-row">
          <div>
            <strong>${mix.companyName}</strong>
            <span>${mix.stage} · ${mix.sizeBand} · ${money.format(mix.total)}</span>
          </div>
          <div class="mix-bar compact">
            <span class="base" style="width:${mix.baseShare}%"></span>
            <span class="bonus" style="width:${mix.bonusShare}%"></span>
            <span class="equity" style="width:${mix.equityShare}%"></span>
          </div>
          <small>${mix.baseShare}% base · ${mix.bonusShare}% bonus · ${mix.equityShare}% equity</small>
        </article>`
      )
      .join("")}
  `;
  renderMix(data.summary, $(".structure-summary"));
}

async function loadLocations() {
  const { role, level } = context();
  const data = await api(`/api/locations/adjustment?${params({ role, level })}`);
  const max = Math.max(...data.locations.map((item) => item.summary.median), 1);
  $("#locationIndex").innerHTML = data.locations
    .map((item) => {
      const width = Math.max((item.summary.median / max) * 100, 5);
      const deltaClass = item.deltaFromRemote >= 0 ? "good" : "warn";
      return `<article class="location-row">
        <div>
          <strong>${item.location.name}</strong>
          <span>${item.location.region}</span>
        </div>
        <div>
          <b>${money.format(item.summary.median)}</b>
          <small class="${deltaClass}">${item.deltaPercent}% vs Remote US (${money.format(item.deltaFromRemote)})</small>
          <span class="progress"><i style="width:${width}%"></i></span>
        </div>
      </article>`;
    })
    .join("");
}

async function loadSubmissions() {
  const data = await api("/api/submissions");
  $("#submissionsTable").innerHTML = data.submissions
    .map((item) => {
      const total = item.base_salary + item.bonus + item.equity_annual_value;
      return `<tr>
        <td>${item.company_name}</td>
        <td>${item.role_name} ${item.level_code}</td>
        <td>${item.location_name}</td>
        <td>${money.format(total)}</td>
        <td><span class="status">${item.status}</span></td>
      </tr>`;
    })
    .join("");
}

async function refreshActive() {
  if (state.activeTab === "overview") await loadOverview();
  if (state.activeTab === "levels") await loadLevelMap();
  if (state.activeTab === "compare") await runCompare();
  if (state.activeTab === "structure") await loadStructure();
  if (state.activeTab === "locations") await loadLocations();
  if (state.activeTab === "submit") await loadSubmissions();
}

async function switchTab(tab) {
  state.activeTab = tab;
  $all(".nav").forEach((button) => button.classList.toggle("active", button.dataset.tab === tab));
  $all("[data-panel]").forEach((panel) => panel.classList.toggle("hidden", panel.dataset.panel !== tab));
  $("#pageTitle").textContent = {
    overview: "Overview",
    levels: "Level map",
    compare: "Compare cohorts",
    structure: "Pay structure",
    locations: "Location index",
    submit: "Contribute data",
  }[tab];
  await refreshActive();
}

async function bootWorkspace() {
  $("#userLabel").textContent = state.user.email;
  state.reference = await api("/api/reference");
  hydrateControls();
  show("workspace");
  await refreshActive();
}

$("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#authError").textContent = "";
  const form = new FormData(event.currentTarget);
  try {
    const data = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
    });
    state.user = data.user;
    state.csrfToken = data.csrfToken;
    await bootWorkspace();
  } catch (error) {
    $("#authError").textContent = error.message;
  }
});

$("#logoutButton").addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST", body: "{}" });
  state.user = null;
  state.csrfToken = null;
  show("auth");
});

$("#refreshAll").addEventListener("click", refreshActive);
$("#runCompare").addEventListener("click", runCompare);
$all(".nav").forEach((button) => button.addEventListener("click", () => switchTab(button.dataset.tab)));

$("#submissionForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const payload = Object.fromEntries(form.entries());
  payload.baseSalary = Number(payload.baseSalary);
  payload.bonus = Number(payload.bonus);
  payload.equityAnnualValue = Number(payload.equityAnnualValue);
  payload.currency = "USD";
  await api("/api/submissions", { method: "POST", body: JSON.stringify(payload) });
  event.currentTarget.reset();
  hydrateControls();
  await loadSubmissions();
});

(async function restoreSession() {
  try {
    const data = await api("/api/me");
    if (data.user) {
      state.user = data.user;
      state.csrfToken = data.csrfToken;
      await bootWorkspace();
      return;
    }
  } catch (error) {
    // Anonymous users land on the sign-in screen.
  }
  show("auth");
})();
