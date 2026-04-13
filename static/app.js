const form = document.getElementById("prediction-form");
const modelInfo = document.getElementById("model-info");
const resultBox = document.getElementById("result");
const locationBtn = document.getElementById("use-location");
const batchForm = document.getElementById("batch-form");
const batchResultBox = document.getElementById("batch-result");
const historyBody = document.getElementById("history-body");
const historyMoreBtn = document.getElementById("history-more");
const historyLessBtn = document.getElementById("history-less");
const refreshBtn = document.getElementById("refresh-history");
const clearBtn = document.getElementById("clear-history");
const historySearch = document.getElementById("history-search");
const historyFilter = document.getElementById("history-filter");
const dashboardSummary = document.getElementById("dashboard-summary");
const dashboardSoilBody = document.getElementById("dashboard-soil-body");
const dashboardTrend = document.getElementById("dashboard-trend");
const dashboardSoilChart = document.getElementById("dashboard-soil-chart");

let historiqueComplet = [];
let limiteHistoriqueVisible = 5;

async function lireMessageErreur(response, fallbackMessage) {
  const contentType = response.headers.get("Content-Type") || "";

  if (contentType.includes("application/json")) {
    const payload = await response.json();
    return payload.erreur || payload.error || fallbackMessage;
  }

  const texte = await response.text();
  if (texte && texte.trim().length > 0) {
    return `${fallbackMessage} (${texte.slice(0, 160)})`;
  }
  return fallbackMessage;
}

function corrigerTexteFrancais(texte) {
  if (typeof texte !== "string") {
    return texte;
  }

  return texte
    .replaceAll("Decision", "Décision")
    .replaceAll("alignee", "alignée")
    .replaceAll("modele", "modèle")
    .replaceAll("Desequilibre", "Déséquilibre")
    .replaceAll("severe", "sévère")
    .replaceAll("detecte", "détecté")
    .replaceAll("Confiance modele", "Confiance du modèle")
    .replaceAll("Prediction", "Prédiction")
    .replaceAll("legumineuse", "légumineuse")
    .replaceAll("Jachere", "Jachère")
    .replaceAll("amelioree", "améliorée")
    .replaceAll("reduire", "réduire")
    .replaceAll("Reduire", "Réduire")
    .replaceAll("verifier", "vérifier")
    .replaceAll("salinite", "salinité")
    .replaceAll("acidite", "acidité")
    .replaceAll("strategie", "stratégie")
    .replaceAll("eleve", "élevé")
    .replaceAll("elevee", "élevée")
    .replaceAll("equilibres", "équilibrés")
    .replaceAll("Aucune anomalie detectee", "Aucune anomalie détectée")
    .replaceAll("anormalement elevees", "anormalement élevées")
    .replaceAll("projete", "projeté");
}

function libelleIncertitude(niveau) {
  const map = {
    elevee: "élevée",
    moyenne: "moyenne",
    faible: "faible",
  };
  return map[niveau] || corrigerTexteFrancais(niveau || "-");
}

function traduireFacteur(facteur) {
  const map = {
    rainfall: "pluviométrie",
    future_rainfall: "pluie_future",
    humidity: "humidité",
    temperature: "température",
    temperature_forecast: "température_prévue",
    fertility_index: "indice_fertilité",
    climate_factor: "facteur_climatique",
    nitrogen: "azote",
    phosphorus: "phosphore",
    potassium: "potassium",
    ph: "pH",
    np_ratio: "ratio_NP",
    pk_ratio: "ratio_PK",
    rainfall_ratio_forecast: "ratio_pluie_future",
    temperature_delta_forecast: "delta_température",
  };
  return map[facteur] || facteur;
}

function renderResult(data, isError = false) {
  resultBox.classList.remove("hidden", "bad");

  if (isError) {
    resultBox.classList.add("bad");
    resultBox.textContent = data;
    return;
  }

  let status = "Non favorable";
  if (data.prediction === "favorable") {
    status = "Favorable";
  } else if (data.prediction === "a_verifier") {
    status = "À vérifier";
  }
  const recommandations = Array.isArray(data.recommandations_culture)
    ? data.recommandations_culture.map((item) => corrigerTexteFrancais(item)).join(", ")
    : "Aucune";
  const actions = Array.isArray(data.actions_recommandees)
    ? data.actions_recommandees.map((item) => corrigerTexteFrancais(item)).join(" | ")
    : "Aucune";
  const raisons = Array.isArray(data.raisons_principales)
    ? data.raisons_principales.map((item) => corrigerTexteFrancais(item)).join(", ")
    : "-";
  const incertitude = libelleIncertitude(data.niveau_incertitude);
  const score = data.score_sol !== undefined ? data.score_sol : "-";
  const niveauSol = data.niveau_sol || "-";
  const anomalies = Array.isArray(data.anomalies) && data.anomalies.length > 0
    ? data.anomalies.map((item) => corrigerTexteFrancais(item)).join(" | ")
    : "Aucune anomalie détectée";
  const explication = Array.isArray(data.explication_locale)
    ? data.explication_locale
      .map((item) => `${traduireFacteur(item.facteur)} (${item.influence})`)
      .join(", ")
    : "-";
  const meteo = formatWeatherContext(data.contexte_meteo);
  const motifDecision = corrigerTexteFrancais(data.motif_decision || "-");
  const modeResponsable = Boolean(data.mode_responsable);
  const avisResponsable = corrigerTexteFrancais(data.avis_responsable || "-");
  const motifsResponsables = Array.isArray(data.motifs_responsable) && data.motifs_responsable.length > 0
    ? data.motifs_responsable.map((item) => corrigerTexteFrancais(item)).join(" | ")
    : "Aucun";
  const badgeResponsable = modeResponsable
    ? '<span class="responsible-badge">Mode responsable actif</span><br/>'
    : "";

  resultBox.innerHTML = `${badgeResponsable}Décision : <strong>${status}</strong> | Confiance : <strong>${data.confiance}%</strong> | Incertitude : <strong>${incertitude}</strong><br/>Motif de la décision : <strong>${motifDecision}</strong><br/>Avis responsable : <strong>${avisResponsable}</strong><br/>Motifs de prudence : <strong>${motifsResponsables}</strong><br/>Score du sol : <strong>${score}/100</strong> (${niveauSol})<br/>Cultures recommandées : <strong>${recommandations}</strong><br/>Actions conseillées : <strong>${actions}</strong><br/>Raisons : <strong>${raisons}</strong><br/>Facteurs explicatifs : <strong>${explication}</strong><br/>Contexte météo : <strong>${meteo}</strong><br/>Contrôle des anomalies : <strong>${anomalies}</strong>`;
  if (!data.est_favorable) {
    resultBox.classList.add("bad");
  }
}

function formatWeatherContext(context) {
  if (!context) {
    return "Aucun contexte météo (ajoutez latitude/longitude ou utilisez votre position)";
  }

  if (context.erreur) {
    return `Contexte météo indisponible : ${corrigerTexteFrancais(context.erreur)}`;
  }

  const source = context.source_meteo || "inconnue";
  const pluie = context.future_rainfall !== undefined
    ? `${Number(context.future_rainfall).toFixed(2)} mm/an (projeté)`
    : "-";
  const temp = context.temperature_forecast !== undefined
    ? `${Number(context.temperature_forecast).toFixed(2)} °C`
    : "-";
  return `Source météo : ${source} | Pluie future : ${pluie} | Température prévue : ${temp}`;
}

function updateCoordinates(latitude, longitude) {
  const latInput = form.querySelector('input[name="latitude"]');
  const lonInput = form.querySelector('input[name="longitude"]');
  if (latInput) {
    latInput.value = Number(latitude).toFixed(6);
  }
  if (lonInput) {
    lonInput.value = Number(longitude).toFixed(6);
  }
}

async function loadHistory() {
  const response = await fetch("/history?limit=5");
  historiqueComplet = await response.json();

  if (!Array.isArray(historiqueComplet) || historiqueComplet.length === 0) {
    historyBody.innerHTML = `<tr><td colspan="7">Aucune analyse pour le moment</td></tr>`;
    if (historyMoreBtn) {
      historyMoreBtn.style.display = "none";
    }
    if (historyLessBtn) {
      historyLessBtn.style.display = "none";
    }
    return;
  }

  renderHistory();
}

function renderHistory() {
  historyBody.innerHTML = "";
  const searchText = (historySearch.value || "").trim().toLowerCase();
  const filterValue = historyFilter.value;

  let data = Array.isArray(historiqueComplet) ? [...historiqueComplet] : [];

  if (filterValue !== "all") {
    data = data.filter((item) => item.prediction === filterValue);
  }

  if (searchText) {
    data = data.filter((item) => {
      const haystack = [
        item.date_creation,
        item.prediction,
        item.donnees_entree?.ph,
        item.donnees_entree?.nitrogen,
        item.donnees_entree?.phosphorus,
        item.donnees_entree?.potassium,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(searchText);
    });
  }

  const visibleRows = data.slice(0, limiteHistoriqueVisible);

  if (visibleRows.length === 0) {
    historyBody.innerHTML = `<tr><td colspan="7">Aucun résultat pour ce filtre</td></tr>`;
    return;
  }

  visibleRows.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.date_creation}</td>
      <td>${item.prediction}</td>
      <td>${Number(item.confiance).toFixed(2)}%</td>
      <td>${item.donnees_entree.ph}</td>
      <td>${item.donnees_entree.nitrogen}</td>
      <td>${item.donnees_entree.phosphorus}</td>
      <td>${item.donnees_entree.potassium}</td>
    `;
    historyBody.appendChild(row);
  });

  if (historyMoreBtn) {
    historyMoreBtn.style.display = data.length > limiteHistoriqueVisible ? "inline-block" : "none";
  }
  if (historyLessBtn) {
    historyLessBtn.style.display = limiteHistoriqueVisible > 5 ? "inline-block" : "none";
  }

}

async function loadDashboard() {
  const response = await fetch("/dashboard/stats");
  const data = await response.json();

  dashboardSummary.innerHTML = `
    <div><strong>Total des analyses:</strong> ${data.total_analyses}</div>
    <div><strong>Taux favorable:</strong> ${data.taux_favorable}%</div>
    <div><strong>Confiance moyenne:</strong> ${data.confiance_moyenne}%</div>
    <div><strong>Nombre de feedbacks:</strong> ${data.nombre_feedbacks}</div>
    <div><strong>Précision terrain :</strong> ${data.precision_terrain}%</div>
  `;

  renderTrendChart(data.tendance_7_jours || []);
  renderSoilChart(data.repartition_par_type_sol || []);

  dashboardSoilBody.innerHTML = "";
  if (!Array.isArray(data.repartition_par_type_sol) || data.repartition_par_type_sol.length === 0) {
    dashboardSoilBody.innerHTML = `<tr><td colspan="3">Aucune donnée disponible</td></tr>`;
    return;
  }

  data.repartition_par_type_sol.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${traduireTypeSol(item.soil_type)}</td>
      <td>${item.total}</td>
      <td>${item.favorable_rate}%</td>
    `;
    dashboardSoilBody.appendChild(row);
  });
}

async function loadModelInfo() {
  try {
    const response = await fetch("/modele/info");
    if (!response.ok) {
      modelInfo.textContent = "Modèle : informations indisponibles";
      return;
    }
    const data = await response.json();
    const algo = data.algorithme || "inconnu";
    const precisionTestRaw = data.precision_test !== undefined ? data.precision_test : data.accuracy_test;
    const acc = precisionTestRaw !== null && precisionTestRaw !== undefined
      ? `${(Number(precisionTestRaw) * 100).toFixed(2)}%`
      : "-";
    const f1 = data.f1_cv !== null && data.f1_cv !== undefined
      ? Number(data.f1_cv).toFixed(4)
      : "-";
    modelInfo.textContent = `Modèle : ${algo} | Précision de test : ${acc} | Score F1 (CV) : ${f1}`;
  } catch (_error) {
    modelInfo.textContent = "Modèle : informations indisponibles";
  }
}

function renderTrendChart(points) {
  dashboardTrend.innerHTML = "";
  if (!Array.isArray(points) || points.length === 0) {
    dashboardTrend.innerHTML = `<div>Aucune tendance disponible</div>`;
    return;
  }

  const maxCount = Math.max(...points.map((p) => Number(p.count || 0)), 1);
  points.forEach((item) => {
    const count = Number(item.count || 0);
    const width = Math.max((count / maxCount) * 100, 2);
    const row = document.createElement("div");
    row.className = "chart-row";
    row.innerHTML = `
      <div class="chart-label">${item.date}</div>
      <div class="bar-wrap"><div class="bar-fill trend" style="width:${width}%"></div></div>
      <div class="chart-value">${count}</div>
    `;
    dashboardTrend.appendChild(row);
  });
}

function renderSoilChart(items) {
  dashboardSoilChart.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    dashboardSoilChart.innerHTML = `<div>Aucune répartition disponible</div>`;
    return;
  }

  items.forEach((item) => {
    const rate = Number(item.favorable_rate || 0);
    let rateClass = "low";
    if (rate >= 70) {
      rateClass = "high";
    } else if (rate >= 40) {
      rateClass = "medium";
    }
    const row = document.createElement("div");
    row.className = "chart-row";
    row.innerHTML = `
      <div class="chart-label">${traduireTypeSol(item.soil_type)}</div>
      <div class="bar-wrap"><div class="bar-fill soil ${rateClass}" style="width:${Math.max(rate, 2)}%"></div></div>
      <div class="chart-value">${rate.toFixed(1)}%</div>
    `;
    dashboardSoilChart.appendChild(row);
  });
}

function traduireTypeSol(typeSol) {
  const map = {
    sandy: "sableux",
    clay: "argileux",
    loam: "franc",
    silty: "limoneux",
  };
  return map[typeSol] || typeSol;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = Object.fromEntries(new FormData(form).entries());

  try {
    const response = await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const message = await lireMessageErreur(response, "Echec de la prediction");
      renderResult(message, true);
      return;
    }

    const data = await response.json();

    renderResult(data, false);
    await loadHistory();
    await loadDashboard();
  } catch (error) {
    renderResult(`Serveur injoignable (${error.message || "erreur reseau"})`, true);
  }
});

refreshBtn.addEventListener("click", loadHistory);
historySearch.addEventListener("input", () => {
  renderHistory();
});
historyFilter.addEventListener("change", () => {
  limiteHistoriqueVisible = 5;
  renderHistory();
});

if (historyMoreBtn) {
  historyMoreBtn.addEventListener("click", () => {
    limiteHistoriqueVisible += 5;
    renderHistory();
  });
}

if (historyLessBtn) {
  historyLessBtn.addEventListener("click", () => {
    limiteHistoriqueVisible = Math.max(5, limiteHistoriqueVisible - 5);
    renderHistory();
  });
}

clearBtn.addEventListener("click", async () => {
  const confirmation = window.confirm("Voulez-vous vraiment effacer tout l'historique ?");
  if (!confirmation) {
    return;
  }

  try {
    const response = await fetch("/history/effacer", { method: "POST" });
    if (!response.ok) {
      const message = await lireMessageErreur(response, "Echec de suppression de l'historique");
      alert(message);
      return;
    }
    await loadHistory();
    await loadDashboard();
  } catch (error) {
    alert(`Erreur reseau: ${error.message || "inconnue"}`);
  }
});

if (locationBtn) {
  locationBtn.addEventListener("click", () => {
    if (!navigator.geolocation) {
      renderResult("Geolocalisation non supportee par ce navigateur", true);
      return;
    }

    locationBtn.disabled = true;
    locationBtn.textContent = "Localisation...";

    navigator.geolocation.getCurrentPosition(
      (position) => {
        updateCoordinates(position.coords.latitude, position.coords.longitude);
        locationBtn.disabled = false;
        locationBtn.textContent = "Utiliser ma position";
      },
      (error) => {
        locationBtn.disabled = false;
        locationBtn.textContent = "Utiliser ma position";
        renderResult(`Impossible de recuperer la position (${error.message})`, true);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  });
}

if (batchForm && batchResultBox) {
  batchForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    batchResultBox.classList.remove("hidden", "bad");
    batchResultBox.textContent = "Traitement en cours...";

    const formData = new FormData(batchForm);

    try {
      const response = await fetch("/predict/batch", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        batchResultBox.classList.add("bad");
        batchResultBox.textContent = await lireMessageErreur(response, "Echec de la prediction en lot");
        return;
      }

      const blob = await response.blob();
      const total = response.headers.get("X-Lot-Total") || "0";
      const success = response.headers.get("X-Lot-Succes") || "0";
      const errors = response.headers.get("X-Lot-Erreurs") || "0";

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "predictions_batch_resultats.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      batchResultBox.classList.remove("bad");
      batchResultBox.innerHTML = `Traitement termine. Total: <strong>${total}</strong> | Succès: <strong>${success}</strong> | Erreurs: <strong>${errors}</strong><br/>Le fichier resultat a ete telecharge et les predictions sont ajoutees dans "Analyses recentes".`;
      await loadHistory();
      await loadDashboard();
    } catch (error) {
      batchResultBox.classList.add("bad");
      batchResultBox.textContent = `Serveur injoignable pour la prediction en lot (${error.message || "erreur reseau"})`;
    }
  });
}

loadHistory();
loadDashboard();
loadModelInfo();
