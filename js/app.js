/**
 * Adivinhe o Carro • Jogo Diário com Zoom Progressivo e Ficha Técnica (Canal VE)
 */

(function () {
  "use strict";

  const MAX_ATTEMPTS = 6;
  const ZOOM_LEVELS = [3.5, 2.7, 2.1, 1.6, 1.25, 1.08]; // 1.0 quando finalizar
  const STORAGE_KEY_PROGRESS = "gtc_daily_progress_v1";
  const STORAGE_KEY_STATS = "gtc_player_stats_v1";

  // Estado Global
  let allCars = [];
  let carsById = {};
  let dailyPayload = null;
  let activeDateKey = "";
  let isCustomShuffleMode = false;
  let currentTriad = []; // Array de 3 objetos de carros
  let currentCarIndex = 0; // 0, 1 ou 2
  let roundStates = []; // Estado de cada um dos 3 carros
  let filteredSuggestions = [];
  let highlightedIndex = -1;
  let selectedCarFromList = null;
  let lastUnlockedCount = [0, 0, 0];

  // Elementos DOM
  const els = {
    dailyDateLabel: document.getElementById("dailyDateLabel"),
    carTabs: document.getElementById("carTabs"),
    dailyStatusSummary: document.getElementById("dailyStatusSummary"),
    btnBackToDaily: document.getElementById("btnBackToDaily"),
    zoomBadge: document.getElementById("zoomBadge"),
    attemptsBadge: document.getElementById("attemptsBadge"),
    photoViewport: document.getElementById("photoViewport"),
    carImage: document.getElementById("carImage"),
    zoomStepsBar: document.getElementById("zoomStepsBar"),
    guessBox: document.getElementById("guessBox"),
    carSearchInput: document.getElementById("carSearchInput"),
    btnClearInput: document.getElementById("btnClearInput"),
    autocompleteList: document.getElementById("autocompleteList"),
    btnSubmitGuess: document.getElementById("btnSubmitGuess"),
    btnSkipAttempt: document.getElementById("btnSkipAttempt"),
    inputFeedback: document.getElementById("inputFeedback"),
    roundResultCard: document.getElementById("roundResultCard"),
    resultBanner: document.getElementById("resultBanner"),
    resultIcon: document.getElementById("resultIcon"),
    resultTitle: document.getElementById("resultTitle"),
    resultSubtitle: document.getElementById("resultSubtitle"),
    revealedBrand: document.getElementById("revealedBrand"),
    revealedName: document.getElementById("revealedName"),
    revealedSourceLink: document.getElementById("revealedSourceLink"),
    fullSpecsGrid: document.getElementById("fullSpecsGrid"),
    btnNextCar: document.getElementById("btnNextCar"),
    btnOpenSummary: document.getElementById("btnOpenSummary"),
    hintsCounterBadge: document.getElementById("hintsCounterBadge"),
    hintsList: document.getElementById("hintsList"),
    guessesCountBadge: document.getElementById("guessesCountBadge"),
    guessesList: document.getElementById("guessesList"),
    btnNewShuffle: document.getElementById("btnNewShuffle"),
    btnStats: document.getElementById("btnStats"),
    btnHelp: document.getElementById("btnHelp"),
    statsModal: document.getElementById("statsModal"),
    helpModal: document.getElementById("helpModal"),
    statsKpis: document.getElementById("statsKpis"),
    dailySummaryCards: document.getElementById("dailySummaryCards"),
    btnShareResult: document.getElementById("btnShareResult"),
    shareFeedback: document.getElementById("shareFeedback"),
  };

  // Utilitários
  function normalizeStr(str) {
    return (str || "")
      .toString()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function getTodayIsoLocal() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const d = String(now.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  function formatDateBr(isoDate) {
    if (!isoDate || !isoDate.includes("-")) return isoDate;
    const [y, m, d] = isoDate.split("-");
    return `${d}/${m}/${y}`;
  }

  function getBaseModelFamily(car) {
    // Normaliza variações de bateria/ano do mesmo modelo para evitar frustração caso a foto seja idêntica
    let s = normalizeStr(car.name);
    s = s.replace(/\b202[0-9]\b/g, "").trim();
    return s;
  }

  function isMatchingCar(targetCar, guessedCar) {
    if (!targetCar || !guessedCar) return false;
    if (targetCar.id === guessedCar.id) return true;
    // Se compartilham exatamente a mesma imagem no Canal VE, aceita como acerto
    if (targetCar.sourceImageUrl && targetCar.sourceImageUrl === guessedCar.sourceImageUrl) {
      return true;
    }
    return false;
  }

  function getFocalPointForCar(carId) {
    // Gera um ponto focal determinístico centrado na região do carro (40%..60% X, 52%..64% Y)
    const x = 40 + ((carId * 17) % 21);
    const y = 52 + ((carId * 13) % 13);
    return `${x}% ${y}%`;
  }

  function maskModelName(car) {
    // Remove a marca do início para mascarar apenas o modelo
    let modelOnly = car.name;
    if (car.brand && normalizeStr(modelOnly).startsWith(normalizeStr(car.brand))) {
      modelOnly = modelOnly.slice(car.brand.length).trim();
    }
    return modelOnly
      .split(/\s+/)
      .map((word) => {
        if (word.length <= 2) return word[0] + "_";
        return (
          word[0] +
          word
            .slice(1)
            .replace(/[a-zA-ZÀ-ÿ]/g, "_")
        );
      })
      .join("   ");
  }

  function buildHintsForCar(car) {
    const seatsTxt = car.seats && car.seats !== "N/I" ? `${car.seats} lugares` : "";
    const trunkTxt = car.trunk && car.trunk !== "N/I" ? `Porta-malas: ${car.trunk}` : "";
    const hint1Parts = [car.bodyType, seatsTxt, trunkTxt].filter((x) => x && x !== "N/I");

    const powerTxt = car.power && car.power !== "N/I" ? `Potência: ${car.power}` : "";
    const tractionTxt = car.traction && car.traction !== "N/I" ? `Tração: ${car.traction}` : "";
    const hint2Parts = [car.powertrain, powerTxt, tractionTxt].filter((x) => x && x !== "N/I");

    const rangeTxt = car.range && car.range !== "N/I" ? `Autonomia: ${car.range}` : "";
    const speedTxt = car.topSpeed && car.topSpeed !== "N/I" ? `Vel. Máx: ${car.topSpeed}` : "";
    const hint3Parts = [`Ano: ${car.year}`, rangeTxt, speedTxt].filter((x) => x && x !== "N/I");

    return [
      {
        step: 1,
        label: "Carroceria & Porte",
        value: hint1Parts.join(" • ") || "SUV / Passeio",
      },
      {
        step: 2,
        label: "Motorização & Desempenho",
        value: hint2Parts.join(" • ") || car.powertrain,
      },
      {
        step: 3,
        label: "Ano & Autonomia",
        value: hint3Parts.join(" • ") || `Ano ${car.year}`,
      },
      {
        step: 4,
        label: "Marca / Fabricante",
        value: car.brand,
      },
      {
        step: 5,
        label: "Iniciais do Modelo",
        value: maskModelName(car),
      },
    ];
  }

  // Determina os 3 carros para a data atual
  function resolveDailyTriad(dateStr) {
    if (dailyPayload) {
      // 1. Se o payload do script corresponde à data ou tem na agenda pré-embaralhada
      if (dailyPayload.date === dateStr && Array.isArray(dailyPayload.todayIds) && dailyPayload.todayIds.length === 3) {
        const mapped = dailyPayload.todayIds.map((id) => carsById[id]).filter(Boolean);
        if (mapped.length === 3) return mapped;
      }
      if (dailyPayload.schedule && Array.isArray(dailyPayload.schedule[dateStr])) {
        const mapped = dailyPayload.schedule[dateStr].map((id) => carsById[id]).filter(Boolean);
        if (mapped.length === 3) return mapped;
      }
    }

    // 2. Fallback determinístico caso a data não esteja na agenda
    const seed = dateStr.split("-").reduce((acc, val) => acc * 31 + parseInt(val, 10), 7);
    const pool = [...allCars];
    for (let i = pool.length - 1; i > 0; i--) {
      const j = Math.abs((seed * (i + 11) + i * 97) % (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    return pool.slice(0, 3);
  }

  // Estado e Persistência
  function createEmptyRoundStates(triad) {
    return triad.map((car) => ({
      carId: car.id,
      guesses: [], // { type: 'guess' | 'skip', carId?: number, correct: boolean }
      status: "playing", // 'playing' | 'won' | 'lost'
    }));
  }

  function loadDailyProgress(dateKey, triad) {
    try {
      const raw = localStorage.getItem(STORAGE_KEY_PROGRESS);
      if (!raw) return createEmptyRoundStates(triad);
      const parsed = JSON.parse(raw);
      const entry = parsed[dateKey];
      if (!entry || !Array.isArray(entry.rounds) || entry.rounds.length !== 3) {
        return createEmptyRoundStates(triad);
      }
      // Verifica se os IDs dos carros ainda são os mesmos (caso o usuário tenha rodado daily_shuffle.py --force)
      const sameIds = entry.rounds.every((r, idx) => r.carId === triad[idx].id);
      if (!sameIds) {
        return createEmptyRoundStates(triad);
      }
      return entry.rounds;
    } catch (e) {
      return createEmptyRoundStates(triad);
    }
  }

  function saveDailyProgress() {
    if (isCustomShuffleMode) return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY_PROGRESS);
      const allProgress = raw ? JSON.parse(raw) : {};
      allProgress[activeDateKey] = {
        updatedAt: new Date().toISOString(),
        rounds: roundStates,
      };
      localStorage.setItem(STORAGE_KEY_PROGRESS, JSON.stringify(allProgress));
    } catch (e) {
      // Ignora erro de quota
    }
  }

  function getPlayerStats() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY_STATS);
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    return {
      carsPlayed: 0,
      carsWon: 0,
      currentStreak: 0,
      bestStreak: 0,
    };
  }

  function recordCarResultInStats(won) {
    try {
      const stats = getPlayerStats();
      stats.carsPlayed += 1;
      if (won) {
        stats.carsWon += 1;
        stats.currentStreak += 1;
        if (stats.currentStreak > stats.bestStreak) {
          stats.bestStreak = stats.currentStreak;
        }
      } else {
        stats.currentStreak = 0;
      }
      localStorage.setItem(STORAGE_KEY_STATS, JSON.stringify(stats));
    } catch (e) {}
  }

  // Renderização da Interface
  function renderHeader() {
    if (isCustomShuffleMode) {
      els.dailyDateLabel.textContent = "Modo Shuffle Livre • 3 Carros Sorteados";
      els.btnBackToDaily.hidden = false;
    } else {
      const dateBr = formatDateBr(activeDateKey);
      els.dailyDateLabel.textContent = `Desafio Diário (${dateBr}) • 3 Carros por Dia`;
      els.btnBackToDaily.hidden = true;
    }
  }

  function renderTabs() {
    els.carTabs.innerHTML = "";
    let finishedCount = 0;
    let wonCount = 0;

    currentTriad.forEach((car, idx) => {
      const st = roundStates[idx];
      if (st.status !== "playing") finishedCount++;
      if (st.status === "won") wonCount++;

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "car-tab-btn";
      if (idx === currentCarIndex) btn.classList.add("active");
      if (st.status === "won") btn.classList.add("won");
      if (st.status === "lost") btn.classList.add("lost");

      let sublabel = "Mistério";
      let pillText = `${st.guesses.length}/${MAX_ATTEMPTS}`;
      if (st.status === "won") {
        sublabel = car.name;
        pillText = "✅ Acertou";
      } else if (st.status === "lost") {
        sublabel = car.name;
        pillText = "❌ Fim";
      }

      btn.innerHTML = `
        <div class="tab-left">
          <span class="tab-label">Carro #${idx + 1}</span>
          <span class="tab-sublabel">${sublabel}</span>
        </div>
        <span class="tab-status-pill">${pillText}</span>
      `;

      btn.addEventListener("click", () => {
        currentCarIndex = idx;
        clearSearchInput();
        renderAll();
      });

      els.carTabs.appendChild(btn);
    });

    els.dailyStatusSummary.textContent = `Progresso da rodada: ${finishedCount}/3 concluídos (${wonCount} acertos)`;
  }

  function renderPhotoAndZoom() {
    const car = currentTriad[currentCarIndex];
    const st = roundStates[currentCarIndex];
    const attemptsUsed = st.guesses.length;
    const isFinished = st.status !== "playing";

    const currentZoom = isFinished
      ? 1.0
      : ZOOM_LEVELS[Math.min(attemptsUsed, ZOOM_LEVELS.length - 1)];

    // Define ponto focal consistente para o carro
    els.carImage.style.transformOrigin = isFinished ? "50% 50%" : getFocalPointForCar(car.id);
    els.carImage.src = car.image;
    els.carImage.alt = isFinished ? car.name : `Carro misterioso #${currentCarIndex + 1}`;
    els.carImage.style.transform = `scale(${currentZoom})`;

    els.zoomBadge.textContent = isFinished
      ? "🔓 Imagem Completa (1.0x)"
      : `🔍 Zoom: ${currentZoom.toFixed(2).replace(/\.00$/, ".0")}x`;

    els.attemptsBadge.textContent = isFinished
      ? st.status === "won"
        ? `Acertou na ${attemptsUsed}ª tentativa!`
        : "Tentativas esgotadas"
      : `Tentativa ${attemptsUsed + 1} de ${MAX_ATTEMPTS}`;

    // Barra de passos de zoom
    els.zoomStepsBar.innerHTML = "";
    ZOOM_LEVELS.forEach((z, idx) => {
      const pill = document.createElement("div");
      pill.className = "zoom-step-pill";
      pill.textContent = `${z}x`;
      if (isFinished && st.status === "won" && idx === attemptsUsed - 1) {
        pill.classList.add("won");
      } else if (idx < attemptsUsed) {
        pill.classList.add("passed");
      } else if (!isFinished && idx === attemptsUsed) {
        pill.classList.add("active");
      }
      els.zoomStepsBar.appendChild(pill);
    });
  }

  function renderHints() {
    const car = currentTriad[currentCarIndex];
    const st = roundStates[currentCarIndex];
    const isFinished = st.status !== "playing";
    const hints = buildHintsForCar(car);

    // Número de dicas desbloqueadas = número de erros cometidos (ou todas se terminou)
    const wrongCount = st.guesses.filter((g) => !g.correct).length;
    const unlockedCount = isFinished ? hints.length : Math.min(wrongCount, hints.length);
    const prevUnlocked = lastUnlockedCount[currentCarIndex] || 0;
    lastUnlockedCount[currentCarIndex] = unlockedCount;

    els.hintsCounterBadge.textContent = `${unlockedCount}/${hints.length} dicas`;
    els.hintsList.innerHTML = "";

    hints.forEach((h, idx) => {
      const isUnlocked = idx < unlockedCount;
      const item = document.createElement("div");
      item.className = `hint-item ${isUnlocked ? "unlocked" : "locked"}`;
      if (isUnlocked && idx >= prevUnlocked && !isFinished) {
        item.classList.add("just-unlocked");
      }

      item.innerHTML = `
        <div class="hint-left">
          <span class="hint-step-num">${h.step}</span>
          <div>
            <span class="hint-label">${h.label}</span>
            <span class="hint-value">${
              isUnlocked ? h.value : `Liberada após o ${h.step}º erro (-zoom)`
            }</span>
          </div>
        </div>
        <span class="hint-lock-tag">${isUnlocked ? "🔓 Revelada" : "🔒 Bloqueada"}</span>
      `;
      els.hintsList.appendChild(item);
    });
  }

  function compareAttribute(targetVal, guessedVal) {
    const t = normalizeStr(targetVal);
    const g = normalizeStr(guessedVal);
    if (!t || !g || t === "n/i" || g === "n/i") return "miss";
    return t === g ? "match" : "miss";
  }

  function compareYear(targetYear, guessedYear) {
    const ty = parseInt(targetYear, 10);
    const gy = parseInt(guessedYear, 10);
    if (isNaN(ty) || isNaN(gy)) {
      return { status: "miss", label: `Ano: ${guessedYear || "N/I"}` };
    }
    if (ty === gy) {
      return { status: "match", label: `Ano: ${gy} ✓` };
    }
    const arrow = ty > gy ? "↑ mais novo" : "↓ mais antigo";
    const status = Math.abs(ty - gy) <= 1 ? "near" : "miss";
    return { status, label: `Ano: ${gy} (${arrow})` };
  }

  function renderGuessesHistory() {
    const targetCar = currentTriad[currentCarIndex];
    const st = roundStates[currentCarIndex];

    els.guessesCountBadge.textContent = `${st.guesses.length}/${MAX_ATTEMPTS}`;
    els.guessesList.innerHTML = "";

    if (st.guesses.length === 0) {
      els.guessesList.innerHTML = `
        <div class="empty-guesses">
          Nenhum palpite ainda para o <strong>Carro #${currentCarIndex + 1}</strong>.<br/>
          Observe o detalhe na foto com zoom e faça seu primeiro chute!
        </div>
      `;
      return;
    }

    st.guesses.forEach((g, idx) => {
      const row = document.createElement("div");
      if (g.type === "skip") {
        row.className = "guess-row skipped";
        row.innerHTML = `
          <div class="guess-row-top">
            <span class="guess-car-name">⏭️ Tentativa pulada (Zoom reduzido + Dica liberada)</span>
            <span class="guess-num-tag">#${idx + 1}</span>
          </div>
        `;
      } else {
        const guessedCar = carsById[g.carId];
        row.className = `guess-row ${g.correct ? "correct" : ""}`;
        const brandCmp = guessedCar ? compareAttribute(targetCar.brand, guessedCar.brand) : "miss";
        const motorCmp = guessedCar ? compareAttribute(targetCar.powertrain, guessedCar.powertrain) : "miss";
        const bodyCmp = guessedCar ? compareAttribute(targetCar.bodyType, guessedCar.bodyType) : "miss";
        const yearCmp = guessedCar ? compareYear(targetCar.year, guessedCar.year) : { status: "miss", label: "Ano" };

        row.innerHTML = `
          <div class="guess-row-top">
            <span class="guess-car-name">${g.correct ? "✅ " : "❌ "}${guessedCar ? guessedCar.name : g.rawName}</span>
            <span class="guess-num-tag">Tentativa #${idx + 1}</span>
          </div>
          ${
            guessedCar
              ? `<div class="guess-compare-pills">
                  <span class="cmp-pill ${brandCmp}" title="Marca do veículo chutado">Marca: ${guessedCar.brand}</span>
                  <span class="cmp-pill ${motorCmp}" title="Motorização do veículo chutado">${guessedCar.powertrain}</span>
                  <span class="cmp-pill ${bodyCmp}" title="Carroceria do veículo chutado">${guessedCar.bodyType}</span>
                  <span class="cmp-pill ${yearCmp.status}" title="Comparação de ano">${yearCmp.label}</span>
                </div>`
              : ""
          }
        `;
      }
      els.guessesList.appendChild(row);
    });
  }

  function renderControlsAndResult() {
    const car = currentTriad[currentCarIndex];
    const st = roundStates[currentCarIndex];
    const isFinished = st.status !== "playing";

    els.inputFeedback.hidden = true;

    if (!isFinished) {
      els.guessBox.hidden = false;
      els.roundResultCard.hidden = true;
      return;
    }

    // Rodada deste carro finalizada: esconde input e exibe ficha técnica completa
    els.guessBox.hidden = true;
    els.roundResultCard.hidden = false;

    const won = st.status === "won";
    els.resultBanner.className = `result-banner ${won ? "won" : "lost"}`;
    els.resultIcon.textContent = won ? "🏆" : "🔎";
    els.resultTitle.textContent = won
      ? `Mandou bem! Você acertou na ${st.guesses.length}ª tentativa!`
      : "Fim das tentativas para este carro!";
    els.resultSubtitle.textContent = won
      ? "A imagem foi aberta em 100% e a ficha técnica completa está disponível abaixo."
      : `O veículo misterioso era o ${car.name}. Confira a ficha técnica abaixo!`;

    els.revealedBrand.textContent = car.brand;
    els.revealedName.textContent = car.name;
    els.revealedSourceLink.href = car.sourceUrl || "https://canalve.com.br/ficha-tecnica/";

    const specItems = [
      { label: "Marca", val: car.brand },
      { label: "Ano", val: car.year },
      { label: "Motorização", val: car.powertrain },
      { label: "Carroceria", val: car.bodyType },
      { label: "Potência", val: car.power },
      { label: "Torque", val: car.torque },
      { label: "Autonomia", val: car.range },
      { label: "Bateria", val: car.battery },
      { label: "Vel. Máxima", val: car.topSpeed },
      { label: "Tração", val: car.traction },
      { label: "Peso", val: car.weight },
      { label: "Porta-malas", val: car.trunk },
    ];

    els.fullSpecsGrid.innerHTML = specItems
      .map(
        (s) => `
        <div class="spec-mini-box">
          <span class="spec-mini-label">${s.label}</span>
          <span class="spec-mini-val">${s.val && s.val !== "N/I" ? s.val : "—"}</span>
        </div>
      `
      )
      .join("");

    // Verifica se há próximo carro pendente
    const nextPendingIdx = roundStates.findIndex((r, i) => i !== currentCarIndex && r.status === "playing");
    if (nextPendingIdx !== -1) {
      els.btnNextCar.hidden = false;
      els.btnNextCar.textContent = `Ir para o Carro #${nextPendingIdx + 1} →`;
      els.btnNextCar.onclick = () => {
        currentCarIndex = nextPendingIdx;
        clearSearchInput();
        renderAll();
      };
    } else if (currentCarIndex < 2) {
      els.btnNextCar.hidden = false;
      els.btnNextCar.textContent = `Ver Carro #${currentCarIndex + 2} →`;
      els.btnNextCar.onclick = () => {
        currentCarIndex = currentCarIndex + 1;
        clearSearchInput();
        renderAll();
      };
    } else {
      els.btnNextCar.hidden = true;
    }
  }

  function renderAll() {
    renderHeader();
    renderTabs();
    renderPhotoAndZoom();
    renderHints();
    renderGuessesHistory();
    renderControlsAndResult();
  }

  // Autocomplete & Palpites
  function clearSearchInput() {
    els.carSearchInput.value = "";
    els.btnClearInput.hidden = true;
    els.autocompleteList.hidden = true;
    selectedCarFromList = null;
    highlightedIndex = -1;
  }

  function updateAutocomplete() {
    const query = normalizeStr(els.carSearchInput.value);
    els.btnClearInput.hidden = query.length === 0;
    selectedCarFromList = null;

    if (!query) {
      els.autocompleteList.hidden = true;
      filteredSuggestions = [];
      return;
    }

    const st = roundStates[currentCarIndex];
    const alreadyGuessedIds = new Set(st.guesses.filter((g) => g.carId).map((g) => g.carId));

    const queryTokens = query.split(/\s+/).filter(Boolean);
    filteredSuggestions = allCars
      .filter((car) => {
        if (alreadyGuessedIds.has(car.id)) return false;
        const hay = normalizeStr(`${car.name} ${car.brand} ${car.year} ${car.bodyType}`);
        return queryTokens.every((t) => hay.includes(t));
      })
      .slice(0, 12);

    if (filteredSuggestions.length === 0) {
      els.autocompleteList.hidden = true;
      return;
    }

    highlightedIndex = 0;
    renderAutocompleteItems();
    els.autocompleteList.hidden = false;
  }

  function renderAutocompleteItems() {
    els.autocompleteList.innerHTML = "";
    filteredSuggestions.forEach((car, idx) => {
      const li = document.createElement("li");
      li.className = `autocomplete-item ${idx === highlightedIndex ? "highlighted" : ""}`;
      li.setAttribute("role", "option");
      li.innerHTML = `
        <span class="ac-name">${car.name}</span>
        <span class="ac-meta">${car.brand} • ${car.year}</span>
      `;
      li.addEventListener("mousedown", (e) => {
        e.preventDefault();
        selectCarSuggestion(car);
      });
      els.autocompleteList.appendChild(li);
    });
  }

  function selectCarSuggestion(car) {
    selectedCarFromList = car;
    els.carSearchInput.value = car.name;
    els.btnClearInput.hidden = false;
    els.autocompleteList.hidden = true;
    els.inputFeedback.hidden = true;
  }

  function showInputError(msg) {
    els.inputFeedback.textContent = msg;
    els.inputFeedback.hidden = false;
  }

  function handleGuessSubmit() {
    const st = roundStates[currentCarIndex];
    if (st.status !== "playing") return;

    const targetCar = currentTriad[currentCarIndex];
    let guessedCar = selectedCarFromList;

    if (!guessedCar) {
      const q = normalizeStr(els.carSearchInput.value);
      if (!q) {
        showInputError("Digite o nome de um carro ou selecione uma opção da lista.");
        return;
      }
      // Busca correspondência exata ou a primeira sugestão filtrada
      guessedCar =
        allCars.find((c) => normalizeStr(c.name) === q) ||
        (filteredSuggestions.length > 0 ? filteredSuggestions[0] : null);
    }

    if (!guessedCar) {
      showInputError("Carro não encontrado no catálogo. Escolha uma das sugestões da lista!");
      return;
    }

    if (st.guesses.some((g) => g.carId === guessedCar.id)) {
      showInputError("Você já chutou esse modelo nesta rodada!");
      return;
    }

    const isCorrect = isMatchingCar(targetCar, guessedCar);
    st.guesses.push({
      type: "guess",
      carId: guessedCar.id,
      rawName: guessedCar.name,
      correct: isCorrect,
    });

    if (isCorrect) {
      st.status = "won";
      recordCarResultInStats(true);
    } else if (st.guesses.length >= MAX_ATTEMPTS) {
      st.status = "lost";
      recordCarResultInStats(false);
    }

    saveDailyProgress();
    clearSearchInput();
    renderAll();

    // Se terminou todos os 3 carros do dia, abre o modal de resumo após um breve delay
    if (roundStates.every((r) => r.status !== "playing")) {
      setTimeout(() => openStatsModal(), 900);
    }
  }

  function handleSkipAttempt() {
    const st = roundStates[currentCarIndex];
    if (st.status !== "playing") return;

    st.guesses.push({
      type: "skip",
      correct: false,
    });

    if (st.guesses.length >= MAX_ATTEMPTS) {
      st.status = "lost";
      recordCarResultInStats(false);
    }

    saveDailyProgress();
    clearSearchInput();
    renderAll();
  }

  // Shuffle Manual no Navegador (para testar ou jogar novas rodadas)
  function startNewBrowserShuffle() {
    isCustomShuffleMode = true;
    const pool = [...allCars];
    for (let i = pool.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }

    // Escolhe 3 carros com marcas e fotos distintas
    const picked = [];
    const usedBrands = new Set();
    const usedPhotos = new Set();
    for (const c of pool) {
      if (picked.length >= 3) break;
      if (!usedBrands.has(c.brand) && !usedPhotos.has(c.sourceImageUrl)) {
        picked.push(c);
        usedBrands.add(c.brand);
        usedPhotos.add(c.sourceImageUrl);
      }
    }
    while (picked.length < 3 && pool.length > picked.length) {
      const next = pool.find((c) => !picked.includes(c));
      if (next) picked.push(next);
    }

    currentTriad = picked;
    currentCarIndex = 0;
    lastUnlockedCount = [0, 0, 0];
    roundStates = createEmptyRoundStates(currentTriad);
    clearSearchInput();
    renderAll();
  }

  function returnToOfficialDaily() {
    isCustomShuffleMode = false;
    activeDateKey = getTodayIsoLocal();
    currentTriad = resolveDailyTriad(activeDateKey);
    currentCarIndex = 0;
    lastUnlockedCount = [0, 0, 0];
    roundStates = loadDailyProgress(activeDateKey, currentTriad);
    clearSearchInput();
    renderAll();
  }

  // Modal de Estatísticas e Compartilhamento
  function openStatsModal() {
    const stats = getPlayerStats();
    const winRate = stats.carsPlayed > 0 ? Math.round((stats.carsWon / stats.carsPlayed) * 100) : 0;

    els.statsKpis.innerHTML = `
      <div class="kpi-box">
        <span class="kpi-num">${stats.carsPlayed}</span>
        <span class="kpi-label">Carros Jogados</span>
      </div>
      <div class="kpi-box">
        <span class="kpi-num">${winRate}%</span>
        <span class="kpi-label">Taxa de Acerto</span>
      </div>
      <div class="kpi-box">
        <span class="kpi-num">${stats.currentStreak}</span>
        <span class="kpi-label">Sequência Atual</span>
      </div>
      <div class="kpi-box">
        <span class="kpi-num">${stats.bestStreak}</span>
        <span class="kpi-label">Melhor Sequência</span>
      </div>
    `;

    els.dailySummaryCards.innerHTML = currentTriad
      .map((car, idx) => {
        const st = roundStates[idx];
        const finished = st.status !== "playing";
        const emojis = st.guesses
          .map((g) => (g.correct ? "🟩" : g.type === "skip" ? "🟨" : "🟥"))
          .join("");
        return `
          <div class="summary-car-row">
            <div>
              <strong>Carro #${idx + 1}: ${finished ? car.name : "Em andamento (???)"}</strong>
              <div style="font-size: 0.78rem; color: var(--text-secondary);">
                ${finished ? `${car.brand} • ${car.year} • ${car.powertrain}` : "Termine este carro para revelar"}
              </div>
            </div>
            <div style="text-align: right;">
              <div>${emojis || "⬜⬜⬜"}</div>
              <span style="font-size: 0.75rem; color: var(--text-secondary);">
                ${st.status === "won" ? `Acertou (${st.guesses.length}/${MAX_ATTEMPTS})` : st.status === "lost" ? `X/${MAX_ATTEMPTS}` : `${st.guesses.length}/${MAX_ATTEMPTS}`}
              </span>
            </div>
          </div>
        `;
      })
      .join("");

    els.shareFeedback.hidden = true;
    els.statsModal.hidden = false;
  }

  function copyShareSummary() {
    const title = isCustomShuffleMode
      ? "🚗 Adivinhe o Carro (Modo Shuffle)"
      : `🚗 Adivinhe o Carro (${formatDateBr(activeDateKey)})`;

    const lines = currentTriad.map((_, idx) => {
      const st = roundStates[idx];
      const track = Array.from({ length: MAX_ATTEMPTS }, (__, i) => {
        const g = st.guesses[i];
        if (!g) return "⬛";
        if (g.correct) return "🟩";
        if (g.type === "skip") return "🟨";
        return "🟥";
      }).join("");
      const score = st.status === "won" ? `${st.guesses.length}/${MAX_ATTEMPTS}` : `X/${MAX_ATTEMPTS}`;
      return `Carro #${idx + 1}: ${track} (${score})`;
    });

    const text = `${title}\n${lines.join("\n")}`;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        els.shareFeedback.hidden = false;
      });
    }
  }

  // Eventos
  function bindEvents() {
    els.carSearchInput.addEventListener("input", updateAutocomplete);
    els.carSearchInput.addEventListener("focus", () => {
      if (els.carSearchInput.value.trim()) updateAutocomplete();
    });

    els.carSearchInput.addEventListener("keydown", (e) => {
      if (!els.autocompleteList.hidden && filteredSuggestions.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          highlightedIndex = (highlightedIndex + 1) % filteredSuggestions.length;
          renderAutocompleteItems();
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          highlightedIndex =
            (highlightedIndex - 1 + filteredSuggestions.length) % filteredSuggestions.length;
          renderAutocompleteItems();
          return;
        }
        if (e.key === "Enter" && highlightedIndex >= 0) {
          e.preventDefault();
          if (!selectedCarFromList) {
            selectCarSuggestion(filteredSuggestions[highlightedIndex]);
          } else {
            handleGuessSubmit();
          }
          return;
        }
        if (e.key === "Escape") {
          els.autocompleteList.hidden = true;
          return;
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        handleGuessSubmit();
      }
    });

    document.addEventListener("click", (e) => {
      if (!e.target.closest(".autocomplete-wrapper")) {
        els.autocompleteList.hidden = true;
      }
    });

    els.btnClearInput.addEventListener("click", () => {
      clearSearchInput();
      els.carSearchInput.focus();
    });

    els.btnSubmitGuess.addEventListener("click", handleGuessSubmit);
    els.btnSkipAttempt.addEventListener("click", handleSkipAttempt);
    els.btnNewShuffle.addEventListener("click", startNewBrowserShuffle);
    els.btnBackToDaily.addEventListener("click", returnToOfficialDaily);

    els.btnStats.addEventListener("click", openStatsModal);
    els.btnOpenSummary.addEventListener("click", openStatsModal);
    els.btnHelp.addEventListener("click", () => {
      els.helpModal.hidden = false;
    });

    els.btnShareResult.addEventListener("click", copyShareSummary);

    document.querySelectorAll("[data-close-modal]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = btn.getAttribute("data-close-modal");
        document.getElementById(targetId).hidden = true;
      });
    });

    [els.statsModal, els.helpModal].forEach((modal) => {
      modal.addEventListener("click", (e) => {
        if (e.target === modal) modal.hidden = true;
      });
    });
  }

  // Inicialização
  async function init() {
    // 1. Carrega de window.GUESS_THE_CAR_DATA (funciona via file:// e servidor)
    if (window.GUESS_THE_CAR_DATA) {
      allCars = window.GUESS_THE_CAR_DATA.cars || [];
      dailyPayload = window.GUESS_THE_CAR_DATA.daily || null;
    }

    // 2. Se estiver rodando via http(s), tenta buscar os JSONs mais recentes caso o script Python tenha acabado de rodar
    if (window.location.protocol.startsWith("http")) {
      try {
        const [carsResp, dailyResp] = await Promise.all([
          fetch(`data/cars.json?t=${Date.now()}`),
          fetch(`data/daily.json?t=${Date.now()}`),
        ]);
        if (carsResp.ok && dailyResp.ok) {
          allCars = await carsResp.json();
          dailyPayload = await dailyResp.json();
        }
      } catch (e) {
        // Mantém fallback do window.GUESS_THE_CAR_DATA
      }
    }

    carsById = {};
    allCars.forEach((c) => {
      carsById[c.id] = c;
    });

    activeDateKey = dailyPayload && dailyPayload.date ? dailyPayload.date : getTodayIsoLocal();
    // Se o dia real da máquina mudou em relação ao último run do script, usa o dia atual da máquina
    const machineToday = getTodayIsoLocal();
    if (machineToday !== activeDateKey) {
      activeDateKey = machineToday;
    }

    currentTriad = resolveDailyTriad(activeDateKey);
    roundStates = loadDailyProgress(activeDateKey, currentTriad);

    // Posiciona na primeira aba ainda não concluída
    const firstOpen = roundStates.findIndex((r) => r.status === "playing");
    currentCarIndex = firstOpen !== -1 ? firstOpen : 0;

    bindEvents();
    renderAll();
  }

  init();
})();

