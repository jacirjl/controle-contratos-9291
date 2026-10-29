// ============================================================================
// MOTOR DE APLICAÇÃO — PLATAFORMA DE GOVERNANÇA E AUDITORIA CONTRATO 9291/2025
// ============================================================================

const AppState = {
  activeTab: "dashboard",
  osSearch: "",
  osOrgaoFilter: "TODOS",
  osSeveridadeFilter: "TODAS",
  osTipoFilter: "TODOS",
  auditSeveridadeFilter: "TODAS",
  selectedOSId: null,
  charts: {}
};

// Formatadores Utilitários
const fmtBRL = (val) => {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(val);
};

const fmtNum = (val, decimals = 2) => {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(val);
};

const fmtInt = (val) => {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(val);
};

// Inicialização Principal
document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  renderAllViews();
  initCharts();
  setupSimulatorEvents();
  setupInvoiceReconcilerEvents();
  setupIMRCalculatorEvents();
  setupSLADateCalculatorEvents();
  if (window.lucide) window.lucide.createIcons();
});

// Navegação entre Módulos (Abas)
function initNavigation() {
  const navButtons = document.querySelectorAll("[data-nav-target]");
  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.getAttribute("data-nav-target");
      switchTab(target);
    });
  });
}

function switchTab(tabId) {
  AppState.activeTab = tabId;

  document.querySelectorAll("[data-nav-target]").forEach((btn) => {
    const isTarget = btn.getAttribute("data-nav-target") === tabId;
    btn.classList.toggle("active", isTarget);
  });

  document.querySelectorAll(".view-section").forEach((sec) => {
    const isTarget = sec.id === `view-${tabId}`;
    sec.classList.toggle("hidden", !isTarget);
  });

  if (tabId === "dashboard") {
    setTimeout(() => {
      Object.values(AppState.charts).forEach((ch) => ch && ch.resize());
    }, 60);
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// Renderização Global
function renderAllViews() {
  renderDashboardKPIs();
  renderCronologiaView();
  renderVetorialView();
  renderConciliacaoView();
  renderFinanceiroView();
  renderAuditoriaView();
  renderCatalogoTable();
  renderDocumentosView();
}

// ============================================================================
// 1. DASHBOARD EXECUTIVO & CURVA S
// ============================================================================
function renderDashboardKPIs() {
  const D = window.CONTRACT_DATA;
  const osList = D.ordensServico;

  // Cálculos agregados das 27 OSs
  const totalUSNMensalPT = osList.reduce((acc, o) => acc + (o.camadaPT.usnMensalPT || 0), 0);
  const totalValorUSNMensalPT = osList.reduce((acc, o) => acc + (o.camadaPT.valorUSNMensalPT || 0), 0);
  const totalUSTMensalPT = osList.reduce((acc, o) => acc + (o.camadaPT.ustMensalPT || 0), 0);
  const totalValorUSTMensalPT = osList.reduce((acc, o) => acc + (o.camadaPT.valorUSTMensalPT || 0), 0);
  const totalMensalPT = osList.reduce((acc, o) => acc + (o.camadaPT.totalMensalPT || 0), 0);

  const totalUSNMensalOS = osList.reduce((acc, o) => acc + (o.camadaOS.usnMensalOS || 0), 0);
  const totalMensalOS = osList.reduce((acc, o) => acc + (o.camadaOS.totalMensalOS || 0), 0);

  const countCriticas = osList.filter((o) => o.severidade === "CRÍTICA").length;
  const countAltas = osList.filter((o) => o.severidade === "ALTA").length;
  const countSemOrcamentoOS = osList.filter((o) => o.camadaOS.totalMensalOS === 0).length;
  const countDesmembramento = osList.filter((o) => o.camadaOS.desmembramentoDe !== null).length;

  const kpiContainer = document.getElementById("dashboard-kpi-grid");
  if (!kpiContainer) return;

  kpiContainer.innerHTML = `
    <!-- KPI 1: Teto Global vs Saldo GMS -->
    <div class="glass-card p-5 relative overflow-hidden">
      <div class="flex justify-between items-start mb-3">
        <div>
          <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Teto Global (36 Meses)</span>
          <h3 class="text-2xl font-bold text-white font-mono mt-1">${fmtBRL(D.metadata.valoresGlobais.valorTotal)}</h3>
        </div>
        <span class="badge badge-info">GMS 47396/2025</span>
      </div>
      <div class="space-y-1.5 text-xs text-slate-300">
        <div class="flex justify-between">
          <span>USN (68.089.068 @ R$ 1,76):</span>
          <span class="font-mono font-semibold text-sky-300">${fmtBRL(D.metadata.valoresGlobais.usn.valorTotal)}</span>
        </div>
        <div class="flex justify-between">
          <span>UST (42.984 @ R$ 309,85):</span>
          <span class="font-mono font-semibold text-indigo-300">${fmtBRL(D.metadata.valoresGlobais.ust.valorTotal)}</span>
        </div>
        <div class="flex justify-between pt-1 border-t border-slate-800">
          <span>Saldo Contratual GMS:</span>
          <span class="font-mono font-bold text-emerald-400">${fmtBRL(D.metadata.resumoExecucaoFinanceira.saldoContratualGMS)}</span>
        </div>
      </div>
    </div>

    <!-- KPI 2: Execução Orçamentária Ano 1 (Limite 20% TR) -->
    <div class="glass-card p-5 relative overflow-hidden">
      <div class="flex justify-between items-start mb-3">
        <div>
          <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Empenhado 2026 (Teto Ano 1: 20%)</span>
          <h3 class="text-2xl font-bold text-white font-mono mt-1">${fmtBRL(D.metadata.resumoExecucaoFinanceira.empenhado2026)}</h3>
        </div>
        <span class="badge badge-success">20,00% do Teto</span>
      </div>
      <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden my-2">
        <div class="bg-gradient-to-r from-sky-500 to-emerald-400 h-full rounded-full" style="width: 53.56%"></div>
      </div>
      <div class="space-y-1 text-xs text-slate-300">
        <div class="flex justify-between">
          <span>Liquidado & Pago (7 NFs):</span>
          <span class="font-mono font-bold text-amber-300">${fmtBRL(D.metadata.resumoExecucaoFinanceira.faturadoLiquidadoPago2026)} (53,6%)</span>
        </div>
        <div class="flex justify-between">
          <span>Saldo Empenho 2026NE000298:</span>
          <span class="font-mono font-semibold text-emerald-400">${fmtBRL(D.metadata.resumoExecucaoFinanceira.saldoEmpenho2026)}</span>
        </div>
      </div>
    </div>

    <!-- KPI 3: Descompasso PT/Dimensionamento vs OS Assinada -->
    <div class="glass-card p-5 relative overflow-hidden border-amber-500/30">
      <div class="flex justify-between items-start mb-3">
        <div>
          <span class="text-xs font-semibold uppercase tracking-wider text-amber-300">Run-Rate Mensal (PT/Dim vs OS)</span>
          <h3 class="text-2xl font-bold text-amber-400 font-mono mt-1">${fmtBRL(totalMensalPT)}<span class="text-xs text-slate-400 font-normal">/mês</span></h3>
        </div>
        <span class="badge badge-danger">+125% Acima Média</span>
      </div>
      <div class="space-y-1.5 text-xs text-slate-300">
        <div class="flex justify-between">
          <span>Planejado nos Autos (PT/Dim):</span>
          <span class="font-mono font-semibold text-amber-300">${fmtNum(totalUSNMensalPT, 0)} USN + ${fmtNum(totalUSTMensalPT, 0)} UST</span>
        </div>
        <div class="flex justify-between">
          <span>Transcrito nas OSs Assinadas:</span>
          <span class="font-mono font-semibold text-rose-400">${fmtBRL(totalMensalOS)}/mês</span>
        </div>
        <div class="flex justify-between pt-1 border-t border-slate-800">
          <span>Média Mensal Sustentável TR:</span>
          <span class="font-mono text-slate-400">${fmtBRL(3698759.78)}/mês</span>
        </div>
      </div>
    </div>

    <!-- KPI 4: Diagnóstico de Conformidade das 27 OSs -->
    <div class="glass-card p-5 relative overflow-hidden border-rose-500/30">
      <div class="flex justify-between items-start mb-3">
        <div>
          <span class="text-xs font-semibold uppercase tracking-wider text-rose-300">Auditoria das 27 Ordens de Serviço</span>
          <h3 class="text-2xl font-bold text-white font-mono mt-1">27 <span class="text-sm font-normal text-slate-400">OSs Analisadas</span></h3>
        </div>
        <span class="badge badge-danger">${countCriticas} Críticas | ${countAltas} Altas</span>
      </div>
      <div class="space-y-1.5 text-xs text-slate-300">
        <div class="flex justify-between">
          <span>OSs sem Tabela de Valor R$:</span>
          <span class="font-mono font-bold text-rose-400">${countSemOrcamentoOS} de 27 OSs (74%)</span>
        </div>
        <div class="flex justify-between">
          <span>Desmembramentos da OS_06:</span>
          <span class="font-mono font-semibold text-amber-300">${countDesmembramento} OSs (Data Foundation)</span>
        </div>
        <div class="flex justify-between pt-1 border-t border-slate-800">
          <span>Faturas sem Anexo SIGA nos Autos:</span>
          <span class="font-mono font-bold text-rose-400">4 de 7 NFs (R$ 8,94M)</span>
        </div>
      </div>
    </div>
  `;
}

function initCharts() {
  const ctxCurvaS = document.getElementById("chart-curva-s");
  const ctxTopOS = document.getElementById("chart-top-os");

  if (ctxCurvaS && window.Chart) {
    // Meses de Fev/26 a Out/26 + Projeção Nov/26
    const labels = [
      "Fev/26 (NF 1353)",
      "Mar/26 (NF 2275)",
      "Abr/26 (NF 3008)",
      "Mai/26 (NF 3300)",
      "Jun/26 (NF 3486)",
      "Jul/26 (NF 4336)",
      "Ago/26 (NF 4827)",
      "Set/26 (Proj. Run-Rate)",
      "Out/26 (Proj. Run-Rate)"
    ];

    const faturadoMensal = [
      235122.40,
      479074.22,
      1290224.57,
      2138486.79,
      3789740.71,
      2771812.42,
      3559565.67,
      null,
      null
    ];

    const faturadoAcumulado = [
      235122.40,
      714196.62,
      2004421.19,
      4142907.98,
      7932648.69,
      10704461.11,
      14264026.78,
      18064026.78,
      22164026.78
    ];

    // Curva S planejada no Ano 1 (R$ 26,63M distribuídos em rampa logística)
    const curvaSPlanejadaAcum = [
      1200000,
      2800000,
      5100000,
      8200000,
      12000000,
      16200000,
      20500000,
      23800000,
      26631072
    ];

    // Média mensal contratual linear (R$ 3.698.759,78/mês)
    const mediaMensalLinha = labels.map(() => 3698759.78);

    AppState.charts.curvaS = new Chart(ctxCurvaS, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            type: "bar",
            label: "Faturado & Pago no Mês (NFs Reais)",
            data: faturadoMensal,
            backgroundColor: "rgba(56, 189, 248, 0.75)",
            borderColor: "#38bdf8",
            borderWidth: 1,
            borderRadius: 6,
            yAxisID: "y"
          },
          {
            type: "line",
            label: "Média Mensal Contratual (R$ 3,70M/mês)",
            data: mediaMensalLinha,
            borderColor: "#f59e0b",
            borderDash: [6, 4],
            borderWidth: 2,
            pointRadius: 0,
            fill: false,
            yAxisID: "y"
          },
          {
            type: "line",
            label: "Execução Acumulada Real + Projeção (R$)",
            data: faturadoAcumulado,
            borderColor: "#10b981",
            backgroundColor: "rgba(16, 185, 129, 0.12)",
            borderWidth: 3,
            tension: 0.3,
            fill: true,
            yAxisID: "y1"
          },
          {
            type: "line",
            label: "Teto Curva S Ano 1 (20% = R$ 26,63M)",
            data: curvaSPlanejadaAcum,
            borderColor: "#a855f7",
            borderDash: [4, 4],
            borderWidth: 2,
            tension: 0.3,
            pointRadius: 2,
            fill: false,
            yAxisID: "y1"
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { color: "#cbd5e1", font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${fmtBRL(ctx.raw)}`
            }
          }
        },
        scales: {
          x: { ticks: { color: "#94a3b8", font: { size: 10 } }, grid: { color: "rgba(148,163,184,0.08)" } },
          y: {
            position: "left",
            title: { display: true, text: "Faturamento Mensal (R$)", color: "#38bdf8" },
            ticks: {
              color: "#94a3b8",
              callback: (v) => "R$ " + (v / 1e6).toFixed(1) + "M"
            },
            grid: { color: "rgba(148,163,184,0.08)" }
          },
          y1: {
            position: "right",
            title: { display: true, text: "Acumulado no Ano 1 (R$)", color: "#10b981" },
            ticks: {
              color: "#10b981",
              callback: (v) => "R$ " + (v / 1e6).toFixed(1) + "M"
            },
            grid: { drawOnChartArea: false }
          }
        }
      }
    });
  }

  if (ctxTopOS && window.Chart) {
    // Comparativo entre o que consta no Plano de Trabalho/Dimensionamento vs O que foi impresso na OS Assinada
    const topOS = [
      { label: "OS_06 Data Foundation", pt: 4318810.20, os: 0 },
      { label: "OS_02 SOT Paraná+Sust.", pt: 2000383.37, os: 2000383.37 },
      { label: "OS_18 Defesa Civil PRISMA", pt: 393193.17, os: 0 },
      { label: "OS_04 PMPR Intranet IA", pt: 348705.79, os: 348705.79 },
      { label: "OS_03 PCP Sistrânsito", pt: 331956.38, os: 283619.78 },
      { label: "OS_19 DPE-PR Data Lake", pt: 298335.80, os: 0 },
      { label: "OS_01 CEASA J.A.C.A.", pt: 178491.92, os: 178491.92 },
      { label: "OS_07 SEJU G-Migra", pt: 151935.52, os: 0 },
      { label: "OS_05 SEIA 5k Gemini", pt: 103801.28, os: 103801.28 },
      { label: "OS_14..17 SEFA/REPR (4 OSs)", pt: 202648.16, os: 0 }
    ];

    AppState.charts.topOS = new Chart(ctxTopOS, {
      type: "bar",
      data: {
        labels: topOS.map((x) => x.label),
        datasets: [
          {
            label: "Planejado nos Autos (PT / Dim. Inicial — R$/mês)",
            data: topOS.map((x) => x.pt),
            backgroundColor: "rgba(245, 158, 11, 0.8)",
            borderColor: "#f59e0b",
            borderWidth: 1,
            borderRadius: 4
          },
          {
            label: "Formalizado no Quadro da OS Assinada (R$/mês)",
            data: topOS.map((x) => x.os),
            backgroundColor: "rgba(16, 185, 129, 0.8)",
            borderColor: "#10b981",
            borderWidth: 1,
            borderRadius: 4
          }
        ]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#cbd5e1", font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${fmtBRL(ctx.raw)}`
            }
          }
        },
        scales: {
          x: {
            ticks: {
              color: "#94a3b8",
              callback: (v) => "R$ " + (v / 1e3).toFixed(0) + "k"
            },
            grid: { color: "rgba(148,163,184,0.08)" }
          },
          y: {
            ticks: { color: "#e2e8f0", font: { size: 11 } },
            grid: { display: false }
          }
        }
      }
    });
  }
}

// ============================================================================
// 2. MATRIZ DE CONCILIAÇÃO EM 4 CAMADAS (PT × OS × EXECUÇÃO × COBRANÇA)
// ============================================================================
function renderConciliacaoView() {
  const D = window.CONTRACT_DATA;
  const osList = D.ordensServico;

  // Popular filtro de órgãos caso ainda não esteja populado
  const selectOrgao = document.getElementById("filter-os-orgao");
  if (selectOrgao && selectOrgao.options.length <= 1) {
    const orgaosUnicos = [...new Set(osList.map((o) => o.siglaOrgao))];
    orgaosUnicos.forEach((sigla) => {
      const opt = document.createElement("option");
      opt.value = sigla;
      opt.textContent = sigla;
      selectOrgao.appendChild(opt);
    });
  }

  // Aplicar filtros ativos
  const filtered = osList.filter((os) => {
    const q = AppState.osSearch.trim().toLowerCase();
    const matchText =
      !q ||
      os.id.toLowerCase().includes(q) ||
      os.codigoOS.toLowerCase().includes(q) ||
      os.titulo.toLowerCase().includes(q) ||
      os.orgao.toLowerCase().includes(q) ||
      os.protocolo.toLowerCase().includes(q) ||
      os.statusConciliacao.toLowerCase().includes(q);

    const matchOrgao = AppState.osOrgaoFilter === "TODOS" || os.siglaOrgao === AppState.osOrgaoFilter;
    const matchSev = AppState.osSeveridadeFilter === "TODAS" || os.severidade === AppState.osSeveridadeFilter;

    let matchTipo = true;
    if (AppState.osTipoFilter === "DESMEMBRAMENTO") matchTipo = os.camadaOS.desmembramentoDe !== null;
    else if (AppState.osTipoFilter === "BLOQUEIO") matchTipo = os.camadaOS.bloqueioProducao === true;
    else if (AppState.osTipoFilter === "SEM_ORCAMENTO_OS") matchTipo = os.camadaOS.totalMensalOS === 0;
    else if (AppState.osTipoFilter === "DIVERGENCIA_VALOR") matchTipo = os.camadaAuditoria.divergenciaFinanceiraMensal !== 0 || os.id === "OS_03" || os.id === "OS_04";

    return matchText && matchOrgao && matchSev && matchTipo;
  });

  // Atualizar faixa de totalizadores filtrados
  const sumPTMensal = filtered.reduce((a, b) => a + (b.camadaPT.totalMensalPT || 0), 0);
  const sumOSMensal = filtered.reduce((a, b) => a + (b.camadaOS.totalMensalOS || 0), 0);
  const sumUSNPT = filtered.reduce((a, b) => a + (b.camadaPT.usnMensalPT || 0), 0);
  const sumUSNOS = filtered.reduce((a, b) => a + (b.camadaOS.usnMensalOS || 0), 0);

  const summaryBar = document.getElementById("conciliacao-summary-bar");
  if (summaryBar) {
    summaryBar.innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-4 text-xs">
        <div class="flex items-center gap-2">
          <span class="px-2.5 py-1 rounded-md bg-sky-500/20 text-sky-300 font-mono font-bold">${filtered.length} de 27 OSs exibidas</span>
          <span class="text-slate-400">Clique em qualquer linha para abrir o <strong>Inspetor Lateral de 4 Camadas</strong> e os PDFs originais.</span>
        </div>
        <div class="flex flex-wrap items-center gap-6">
          <div>
            <span class="text-slate-400">Soma USN/mês (PT vs OS):</span>
            <span class="font-mono font-semibold text-amber-300 ml-1">${fmtNum(sumUSNPT, 0)}</span>
            <span class="text-slate-500 mx-1">×</span>
            <span class="font-mono font-semibold text-emerald-300">${fmtNum(sumUSNOS, 0)} USN</span>
          </div>
          <div>
            <span class="text-slate-400">Total Mensal (PT/Dim vs OS):</span>
            <span class="font-mono font-bold text-amber-300 ml-1">${fmtBRL(sumPTMensal)}</span>
            <span class="text-slate-500 mx-1">×</span>
            <span class="font-mono font-bold text-emerald-400">${fmtBRL(sumOSMensal)}</span>
          </div>
          <div>
            <span class="text-slate-400">Gap Não Transcrito na OS:</span>
            <span class="font-mono font-bold text-rose-400 ml-1">${fmtBRL(sumPTMensal - sumOSMensal)}/mês</span>
          </div>
        </div>
      </div>
    `;
  }

  // Renderizar linhas da tabela
  const tbody = document.getElementById("conciliacao-table-body");
  if (!tbody) return;

  tbody.innerHTML = filtered
    .map((os) => {
      const sevBadge =
        os.severidade === "CRÍTICA"
          ? `<span class="badge badge-danger">CRÍTICA</span>`
          : os.severidade === "ALTA"
          ? `<span class="badge badge-warning">ALTA</span>`
          : os.severidade === "MÉDIA"
          ? `<span class="badge badge-info">MÉDIA</span>`
          : `<span class="badge badge-success">BAIXA</span>`;

      const ptTag = os.camadaPT.existePT
        ? `<span class="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 text-[10px] font-semibold">PT OK</span>`
        : `<span class="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-semibold">Sem PT</span>`;

      const dimTag = os.camadaPT.existeDimInicial
        ? `<span class="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-300 text-[10px] font-semibold">Dim. OK</span>`
        : `<span class="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 text-[10px] font-semibold">Sem Dim.</span>`;

      const osAssinadaTag = os.camadaOS.existeOSAssinada
        ? `<span class="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 text-[10px] font-semibold">Assinada</span>`
        : `<span class="px-1.5 py-0.5 rounded bg-rose-500/25 text-rose-300 text-[10px] font-bold">SEM OS!</span>`;

      const bloqueioTag = os.camadaOS.bloqueioProducao
        ? `<span class="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-semibold">Bloqueio Prod.</span>`
        : os.camadaOS.desmembramentoDe
        ? `<span class="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[10px] font-semibold">Desmembr. OS_06</span>`
        : "";

      return `
        <tr onclick="openOSDrawer('${os.id}')" class="cursor-pointer transition-colors hover:bg-sky-500/10 border-b border-slate-800/80">
          <td class="py-3 px-3 font-mono font-bold text-sky-400 whitespace-nowrap">${os.id}</td>
          <td class="py-3 px-3">
            <div class="font-semibold text-white text-xs line-clamp-1">${os.titulo}</div>
            <div class="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
              <span class="font-mono text-slate-300">${os.siglaOrgao}</span>
              <span>•</span>
              <span class="font-mono">e-Prot: ${os.protocolo}</span>
              <span>•</span>
              <span>${os.dataEmissao}</span>
            </div>
          </td>
          <td class="py-3 px-3">
            <div class="flex flex-wrap gap-1 mb-1">${ptTag} ${dimTag}</div>
            <div class="font-mono text-xs text-amber-300 font-semibold">${os.camadaPT.totalMensalPT > 0 ? fmtBRL(os.camadaPT.totalMensalPT) + "/mês" : "Não orçado"}</div>
            <div class="text-[10px] text-slate-400 font-mono">${os.camadaPT.usnMensalPT > 0 ? fmtNum(os.camadaPT.usnMensalPT, 0) + " USN | " + fmtNum(os.camadaPT.ustMensalPT, 0) + " UST" : "0 USN | 0 UST"}</div>
          </td>
          <td class="py-3 px-3">
            <div class="flex flex-wrap gap-1 mb-1">${osAssinadaTag} ${bloqueioTag}</div>
            <div class="font-mono text-xs ${os.camadaOS.totalMensalOS > 0 ? "text-emerald-400 font-semibold" : "text-slate-500"}">${os.camadaOS.totalMensalOS > 0 ? fmtBRL(os.camadaOS.totalMensalOS) + "/mês" : "R$ 0,00 na OS"}</div>
            <div class="text-[10px] text-slate-400 font-mono">${os.camadaOS.usnMensalOS > 0 || os.camadaOS.ustMensalOS > 0 ? fmtNum(os.camadaOS.usnMensalOS, 0) + " USN | " + fmtNum(os.camadaOS.ustMensalOS, 0) + " UST" : "Sem tabela na OS"}</div>
          </td>
          <td class="py-3 px-3">
            <div class="text-xs font-medium text-slate-200">${os.statusExecucao}</div>
            <div class="text-[10px] text-slate-400 font-mono mt-0.5 truncate max-w-[180px]">${os.camadaExecucao.ambientesGCP.join(", ")}</div>
          </td>
          <td class="py-3 px-3">
            <div class="mb-1">${sevBadge}</div>
            <div class="text-[11px] font-semibold text-slate-200">${os.statusConciliacao}</div>
          </td>
          <td class="py-3 px-3 text-right whitespace-nowrap" onclick="event.stopPropagation()">
            <div class="flex items-center justify-end gap-1.5">
              ${
                os.arquivos.osPdf
                  ? `<a href="${os.arquivos.osPdf}" target="_blank" title="Abrir PDF da OS" class="px-2 py-1 rounded bg-slate-800 hover:bg-sky-600 text-slate-200 hover:text-white text-[11px] font-mono transition">OS.pdf</a>`
                  : `<span class="px-2 py-1 rounded bg-rose-950/60 text-rose-400 text-[11px] font-mono">Sem OS</span>`
              }
              <a href="${os.arquivos.processoPdf}" target="_blank" title="Abrir PDF Completo do Processo e-Protocolo" class="px-2 py-1 rounded bg-slate-800 hover:bg-indigo-600 text-slate-200 hover:text-white text-[11px] font-mono transition">Autos</a>
              <button onclick="openOSDrawer('${os.id}')" class="px-2 py-1 rounded bg-sky-500/20 hover:bg-sky-500/40 text-sky-300 text-[11px] font-semibold transition">Auditar</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

// Eventos de Filtro da Matriz de Conciliação
function filterConciliacao(type, value) {
  if (type === "search") AppState.osSearch = value;
  if (type === "orgao") AppState.osOrgaoFilter = value;
  if (type === "severidade") AppState.osSeveridadeFilter = value;
  if (type === "tipo") AppState.osTipoFilter = value;
  renderConciliacaoView();
}

// Inspetor Lateral (Side-Drawer) de 4 Camadas da OS
function openOSDrawer(osId) {
  const os = window.CONTRACT_DATA.ordensServico.find((o) => o.id === osId);
  if (!os) return;
  AppState.selectedOSId = osId;

  const drawer = document.getElementById("os-detail-drawer");
  const backdrop = document.getElementById("os-drawer-backdrop");
  const content = document.getElementById("os-drawer-content");
  if (!drawer || !content) return;

  const sevColor =
    os.severidade === "CRÍTICA"
      ? "border-rose-500/50 bg-rose-500/10 text-rose-300"
      : os.severidade === "ALTA"
      ? "border-amber-500/50 bg-amber-500/10 text-amber-300"
      : "border-sky-500/50 bg-sky-500/10 text-sky-300";

  content.innerHTML = `
    <div class="flex items-start justify-between border-b border-slate-800 pb-4 mb-5">
      <div>
        <div class="flex items-center gap-2 mb-1">
          <span class="px-2.5 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono text-xs font-bold">${os.id}</span>
          <span class="font-mono text-xs text-slate-400">${os.codigoOS}</span>
          <span class="px-2 py-0.5 rounded border text-[11px] font-bold ${sevColor}">Severidade: ${os.severidade}</span>
        </div>
        <h2 class="text-lg font-bold text-white">${os.titulo}</h2>
        <p class="text-xs text-slate-400 mt-0.5">${os.orgao} • Parceiro: <strong class="text-slate-200">${os.parceiroTecnico}</strong> • Protocolo: <strong class="font-mono text-sky-300">${os.protocolo}</strong></p>
      </div>
      <button onclick="closeOSDrawer()" class="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300">✕</button>
    </div>

    <!-- Botões de Ação Documental Imediata -->
    <div class="flex flex-wrap gap-2 mb-6">
      ${
        os.arquivos.osPdf
          ? `<a href="${os.arquivos.osPdf}" target="_blank" class="px-3 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold flex items-center gap-2 shadow-lg shadow-sky-900/30">
              <span>📄 Abrir Ordem de Serviço Assinada (${os.id}.pdf)</span>
            </a>`
          : `<span class="px-3 py-2 rounded-lg bg-rose-950/80 border border-rose-500/40 text-rose-300 text-xs font-semibold">
              ⚠️ Processo NÃO possui Ordem de Serviço Assinada nos Autos
            </span>`
      }
      <a href="${os.arquivos.processoPdf}" target="_blank" class="px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-2">
        <span>📚 Abrir Processo Integral e-Protocolo (${os.protocolo}.pdf)</span>
      </a>
      ${(os.arquivos.pastaExtras || [])
        .map(
          (ex) => `
        <a href="${ex.url}" target="_blank" class="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700">
          📎 ${ex.nome}
        </a>
      `
        )
        .join("")}
    </div>

    <!-- Comparativo Lado a Lado: Camada 1 (PT/Dim) vs Camada 2 (OS Emitida) -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      <!-- Camada 1: Plano de Trabalho & Dimensionamento -->
      <div class="p-4 rounded-xl bg-slate-900/90 border border-amber-500/30">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-bold uppercase tracking-wider text-amber-300">1. Camada Plano de Trabalho / Dim.</span>
          <span class="text-[11px] font-mono text-slate-400">${os.camadaPT.existePT ? "✅ PT Presente" : "❌ Sem PT"} | ${os.camadaPT.existeDimInicial ? "✅ Dim. Inicial" : "❌ Sem Dim."}</span>
        </div>
        <p class="text-xs text-slate-300 mb-3 leading-relaxed">${os.camadaPT.resumoEscopo}</p>
        <div class="text-[11px] text-slate-400 mb-3 p-2 rounded bg-slate-950/70 border border-slate-800">
          <strong>Ref. Parceiro/Autos:</strong> ${os.camadaPT.custoReferenciaParceiro}
        </div>
        <div class="space-y-1.5 text-xs border-t border-slate-800 pt-2">
          <div class="flex justify-between">
            <span class="text-slate-400">USN Mensal Planejada:</span>
            <span class="font-mono font-semibold text-white">${fmtNum(os.camadaPT.usnMensalPT)} USN (${fmtBRL(os.camadaPT.valorUSNMensalPT)})</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">UST Mensal Planejada:</span>
            <span class="font-mono font-semibold text-white">${fmtNum(os.camadaPT.ustMensalPT)} UST (${fmtBRL(os.camadaPT.valorUSTMensalPT)})</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">UST Única Planejada:</span>
            <span class="font-mono font-semibold text-white">${fmtNum(os.camadaPT.ustUnicaPT)} UST (${fmtBRL(os.camadaPT.valorUSTUnicaPT)})</span>
          </div>
          <div class="flex justify-between pt-1 border-t border-slate-800 font-bold text-amber-300">
            <span>Total Mensal no PT/Dim:</span>
            <span class="font-mono">${fmtBRL(os.camadaPT.totalMensalPT)}/mês</span>
          </div>
        </div>
      </div>

      <!-- Camada 2: Ordem de Serviço Emitida -->
      <div class="p-4 rounded-xl bg-slate-900/90 border border-sky-500/30">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-bold uppercase tracking-wider text-sky-300">2. Camada Ordem de Serviço Emitida</span>
          <span class="text-[11px] font-mono text-slate-400">Emissão: ${os.dataEmissao}</span>
        </div>
        <div class="space-y-1 text-xs text-slate-300 mb-3">
          <div><strong>Prazo Vigência OS:</strong> ${os.prazoInicio} até ${os.prazoFim}</div>
          <div><strong>Bloqueio de Produção:</strong> ${os.camadaOS.bloqueioProducao ? '<span class="text-amber-300 font-bold">SIM (Bloqueado até orçamento)</span>' : '<span class="text-emerald-400 font-semibold">NÃO (Produção Liberada)</span>'}</div>
          <div><strong>Vinculação Contábil:</strong> ${os.camadaOS.desmembramentoDe || "Demanda Originária Independente"}</div>
        </div>
        <div class="space-y-1.5 text-xs border-t border-slate-800 pt-2">
          <div class="flex justify-between">
            <span class="text-slate-400">USN Mensal na OS:</span>
            <span class="font-mono font-semibold text-white">${fmtNum(os.camadaOS.usnMensalOS)} USN (${fmtBRL(os.camadaOS.valorUSNMensalOS)})</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">UST Mensal na OS:</span>
            <span class="font-mono font-semibold text-white">${fmtNum(os.camadaOS.ustMensalOS)} UST (${fmtBRL(os.camadaOS.valorUSTMensalOS)})</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">UST Única na OS:</span>
            <span class="font-mono font-semibold text-white">${fmtNum(os.camadaOS.ustUnicaOS)} UST (${fmtBRL(os.camadaOS.valorUSTUnicaOS)})</span>
          </div>
          <div class="flex justify-between pt-1 border-t border-slate-800 font-bold text-emerald-400">
            <span>Total Mensal Formalizado na OS:</span>
            <span class="font-mono">${fmtBRL(os.camadaOS.totalMensalOS)}/mês</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Camada 3: Execução Técnica, Marcos e Ambientes GCP -->
    <div class="p-4 rounded-xl bg-slate-900/90 border border-slate-800 mb-6">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-bold uppercase tracking-wider text-indigo-300">3. Camada Execução Técnica, Ambientes GCP & RMEC</span>
        <span class="badge ${os.camadaExecucao.rmecApresentado ? "badge-success" : "badge-danger"}">${os.camadaExecucao.rmecApresentado ? "RMEC Juntado" : "Sem RMEC nos Autos"}</span>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        <div>
          <span class="text-slate-400 block mb-1">Ambientes / Projetos Google Cloud Identificados:</span>
          <div class="flex flex-wrap gap-1.5">
            ${os.camadaExecucao.ambientesGCP.map((env) => `<span class="px-2 py-1 rounded bg-slate-950 border border-slate-700 font-mono text-sky-300">${env}</span>`).join("")}
          </div>
        </div>
        <div>
          <span class="text-slate-400 block mb-1">Evidências e Marcos de Entrega:</span>
          <p class="text-slate-200">${os.camadaExecucao.marcosEntregues}</p>
          <p class="text-slate-400 mt-1">${os.camadaExecucao.evidencias}</p>
        </div>
      </div>
    </div>

    <!-- Fluxo instruções.md (Etapas 1 a 5) + Histórico RMEC no Processo 25.609.621-8 -->
    ${(() => {
      const wf = (window.CONTRACT_DATA.fluxoInstrucoesOS || {})[os.id];
      const ciclos = (window.CONTRACT_DATA.ciclosRMEC || []).filter((c) =>
        (c.os_breakdown || []).some((b) => b.os === os.id && (b.total > 0 || b.obs))
      );
      return `
      <div class="p-4 rounded-xl bg-purple-950/20 border border-purple-500/40 mb-6">
        <div class="flex items-center justify-between mb-3">
          <span class="text-xs font-bold uppercase tracking-wider text-purple-300">⏱️ Checagem <code class="font-mono">instruções.md</code> (Etapas 1 a 5) & RMEC (Etapa 6)</span>
          <a href="../Processo_25.609.621-8_1.pdf" target="_blank" class="text-[11px] font-mono text-purple-300 hover:underline">Abrir Proc. 25.609.621-8 ↗</a>
        </div>
        ${
          wf
            ? `<div class="grid grid-cols-1 sm:grid-cols-5 gap-2 text-[11px] mb-3">
                <div class="p-2 rounded bg-slate-950/90 border border-slate-800">
                  <div class="font-mono text-purple-300 font-bold">1. Solicitação+PT</div>
                  <div class="text-white font-mono mt-0.5">${wf.s1_date} (${wf.s1_page})</div>
                  <div class="text-slate-400 mt-0.5">${wf.s1_note}</div>
                </div>
                <div class="p-2 rounded bg-slate-950/90 border border-slate-800">
                  <div class="font-mono text-purple-300 font-bold">2. SEIA➔CELEPAR</div>
                  <div class="text-white font-mono mt-0.5">${wf.s2_date} (${wf.s2_page})</div>
                  <div class="text-slate-400 mt-0.5">${wf.s2_note}</div>
                </div>
                <div class="p-2 rounded bg-slate-950/90 border border-slate-800">
                  <div class="font-mono text-purple-300 font-bold">3. Retorno Custos</div>
                  <div class="text-white font-mono mt-0.5">${wf.s3_date} (${wf.s3_page})</div>
                  <div class="text-slate-400 mt-0.5">${wf.s3_note}</div>
                </div>
                <div class="p-2 rounded bg-slate-950/90 border border-slate-800">
                  <div class="font-mono text-purple-300 font-bold">4. Emissão OS</div>
                  <div class="text-white font-mono mt-0.5">${wf.s4_date} (${wf.s4_page})</div>
                  <div class="text-slate-400 mt-0.5">${wf.s4_note}</div>
                </div>
                <div class="p-2 rounded bg-slate-950/90 border border-slate-800">
                  <div class="font-mono text-purple-300 font-bold">5. Início Execução</div>
                  <div class="text-white font-mono mt-0.5">${wf.s5_date} (${wf.s5_page})</div>
                  <div class="text-slate-400 mt-0.5">${wf.s5_note}</div>
                </div>
              </div>`
            : ""
        }
        ${
          ciclos.length > 0
            ? `<div class="text-[11px] text-slate-300 font-semibold mb-1.5">Medições Mensais RMEC no Processo 25.609.621-8_1.pdf:</div>
               <div class="space-y-1.5">
                 ${ciclos
                   .map((c) => {
                     const item = c.os_breakdown.find((b) => b.os === os.id);
                     return `<div class="flex flex-wrap items-center justify-between gap-2 px-2.5 py-1.5 rounded bg-slate-950/80 border border-slate-800 text-[11px]">
                       <span class="font-mono font-bold text-purple-300">${c.competencia}</span>
                       <span class="font-mono text-slate-300">${fmtNum(item.usn)} USN | ${fmtNum(item.ust)} UST</span>
                       <span class="font-mono font-bold text-emerald-400">${fmtBRL(item.total)}</span>
                       <a href="../Processo_25.609.621-8_1.pdf#page=${item.rmec_page}" target="_blank" class="px-2 py-0.5 rounded bg-purple-900/40 text-purple-200 font-mono hover:bg-purple-800">Pág. ${item.rmec_page} ↗</a>
                     </div>`;
                   })
                   .join("")}
               </div>`
            : `<div class="text-[11px] text-slate-400 italic">Sem medição individualizada de RMEC c/ consumo financeiro até Set/2026 no Proc. 25.609.621-8.</div>`
        }
      </div>
      `;
    })()}

    <!-- Camada 4: Auditoria de Cobrança e Achados Específicos da OS -->
    <div class="p-4 rounded-xl bg-rose-950/20 border border-rose-500/40">
      <div class="flex items-center justify-between mb-3">
        <span class="text-xs font-bold uppercase tracking-wider text-rose-300">4. Camada Cobrança SIGA & Parecer de Auditoria da OS</span>
        <span class="font-mono text-xs text-rose-300 font-bold">${os.statusConciliacao}</span>
      </div>
      <p class="text-xs text-slate-300 mb-3"><strong>Rastreabilidade nas Notas Fiscais:</strong> ${os.camadaAuditoria.faturamentoRastreado}</p>
      <div class="space-y-2">
        ${os.camadaAuditoria.achados
          .map(
            (ach) => `
          <div class="p-3 rounded-lg bg-slate-950/90 border border-rose-500/30 text-xs text-slate-200 flex items-start gap-2.5">
            <span class="text-rose-400 font-bold mt-0.5">⚠️</span>
            <span class="leading-relaxed">${ach}</span>
          </div>
        `
          )
          .join("")}
      </div>
    </div>
  `;

  drawer.classList.remove("translate-x-full");
  backdrop.classList.remove("hidden");
}

function closeOSDrawer() {
  const drawer = document.getElementById("os-detail-drawer");
  const backdrop = document.getElementById("os-drawer-backdrop");
  if (drawer) drawer.classList.add("translate-x-full");
  if (backdrop) backdrop.classList.add("hidden");
}

// ============================================================================
// 3. EXECUÇÃO FINANCEIRA, EMPENHOS (NE) E CONCILIADOR DE FATURAS (SIGA)
// ============================================================================
function renderFinanceiroView() {
  const D = window.CONTRACT_DATA;

  // Renderizar Notas de Empenho
  const neContainer = document.getElementById("ne-cards-container");
  if (neContainer) {
    neContainer.innerHTML = D.notasEmpenho
      .map((ne) => {
        const pct = ne.valorEmpenhado > 0 ? ((ne.valorLiquidadoPago / ne.valorEmpenhado) * 100).toFixed(1) : "0.0";
        return `
        <div class="glass-card p-4 border-l-4 ${ne.saldo > 0 ? "border-l-emerald-500" : "border-l-sky-500"}">
          <div class="flex items-center justify-between mb-2">
            <span class="font-mono font-bold text-sm text-white">${ne.numero}</span>
            <span class="text-xs font-mono text-slate-400">${ne.data}</span>
          </div>
          <div class="text-xs text-slate-400 mb-3">${ne.protocolo}</div>
          <div class="space-y-1 text-xs">
            <div class="flex justify-between">
              <span class="text-slate-400">Valor Empenhado:</span>
              <span class="font-mono font-bold text-white">${fmtBRL(ne.valorEmpenhado)}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-400">Liquidado & Pago:</span>
              <span class="font-mono font-semibold text-sky-300">${fmtBRL(ne.valorLiquidadoPago)} (${pct}%)</span>
            </div>
            <div class="flex justify-between pt-1 border-t border-slate-800">
              <span class="text-slate-400">Saldo Disponível:</span>
              <span class="font-mono font-bold ${ne.saldo > 0 ? "text-emerald-400" : "text-slate-500"}">${fmtBRL(ne.saldo)}</span>
            </div>
          </div>
          <p class="text-[11px] text-slate-400 mt-3 pt-2 border-t border-slate-800/80">${ne.observacao}</p>
        </div>
      `;
      })
      .join("");
  }

  // Renderizar Tabela das 7 Notas Fiscais + 8 NLs + 8 OBs
  const nfTbody = document.getElementById("nf-table-body");
  if (nfTbody) {
    nfTbody.innerHTML = D.notasFiscais
      .map((nf) => {
        const sigaBadge = nf.temAnexoSIGA
          ? `<span class="badge badge-success">Com Anexo SIGA</span>`
          : `<span class="badge badge-danger">SEM ANEXO SIGA</span>`;

        const auditBadge =
          nf.statusAuditoria.includes("CRÍTICO")
            ? `<span class="badge badge-danger">${nf.statusAuditoria}</span>`
            : nf.statusAuditoria.includes("ALERTA")
            ? `<span class="badge badge-warning">${nf.statusAuditoria}</span>`
            : `<span class="badge badge-info">${nf.statusAuditoria}</span>`;

        const nlList = nf.liquidacoes
          .map(
            (l) =>
              `<div class="font-mono text-[11px]"><span class="text-sky-300">${l.nl}</span> → <span class="text-emerald-300">${l.ob}</span> (${l.dataPagamento}) — ${fmtBRL(l.valor)} <span class="text-slate-500">[${l.ne}]</span></div>`
          )
          .join("");

        return `
        <tr class="border-b border-slate-800/80 hover:bg-slate-800/40">
          <td class="py-3 px-3">
            <div class="font-mono font-bold text-white text-sm">NFS-e ${nf.nfNumero}</div>
            <div class="text-[11px] text-slate-400">Emissão: ${nf.dataEmissao}</div>
            <div class="text-[11px] text-sky-400 font-medium">${nf.competencia}</div>
          </td>
          <td class="py-3 px-3">
            <div class="mb-1">${sigaBadge}</div>
            <div class="text-[11px] text-slate-300 font-mono">${nf.periodoSIGA}</div>
          </td>
          <td class="py-3 px-3 font-mono text-xs">
            ${
              nf.usnQuantidade !== null
                ? `<div class="text-sky-300 font-semibold">${fmtNum(nf.usnQuantidade)} USN</div><div class="text-slate-400 text-[11px]">${fmtBRL(nf.usnValor)}</div>`
                : `<span class="text-rose-400 text-[11px]">Não discriminado na NF</span>`
            }
          </td>
          <td class="py-3 px-3 font-mono text-xs">
            ${
              nf.ustQuantidade !== null
                ? `<div class="text-indigo-300 font-semibold">${fmtNum(nf.ustQuantidade)} UST</div><div class="text-slate-400 text-[11px]">${fmtBRL(nf.ustValor)}</div>`
                : `<span class="text-rose-400 text-[11px]">Não discriminado na NF</span>`
            }
          </td>
          <td class="py-3 px-3 font-mono font-bold text-white text-sm">${fmtBRL(nf.valorTotal)}</td>
          <td class="py-3 px-3">
            <div class="text-xs text-white font-medium">Atesto: ${nf.dataAtesto} <span class="font-mono text-[11px] ${nf.diasEmissaoAteAtesto > 15 ? "text-rose-400 font-bold" : "text-slate-400"}">(${nf.diasEmissaoAteAtesto}d)</span></div>
            <div class="mt-1 space-y-0.5">${nlList}</div>
          </td>
          <td class="py-3 px-3">
            <div class="mb-1">${auditBadge}</div>
            <p class="text-[11px] text-slate-300 leading-snug max-w-xs">${nf.observacaoAuditoria}</p>
          </td>
          <td class="py-3 px-3 text-right whitespace-nowrap">
            <a href="${nf.linkProcesso}" target="_blank" class="px-2.5 py-1.5 rounded bg-indigo-600/80 hover:bg-indigo-500 text-white text-xs font-mono inline-block">
              📄 ${nf.paginasProcessoMae}
            </a>
          </td>
        </tr>
      `;
      })
      .join("");
  }
}

// Conciliador Interativo de Fatura Mensal (Batimento NF × Anexo SIGA × OSs)
function setupInvoiceReconcilerEvents() {
  const selectPreset = document.getElementById("reconciler-nf-preset");
  const btnRun = document.getElementById("btn-run-invoice-reconciler");

  if (selectPreset) {
    selectPreset.addEventListener("change", () => {
      const val = selectPreset.value;
      const nf = window.CONTRACT_DATA.notasFiscais.find((n) => n.nfNumero === val);
      if (nf) {
        document.getElementById("rec-nf-numero").value = `NFS-e ${nf.nfNumero} (${nf.competencia})`;
        document.getElementById("rec-valor-nf").value = nf.valorTotal;
        document.getElementById("rec-usn-siga").value = nf.usnQuantidade || 0;
        document.getElementById("rec-ust-siga").value = nf.ustQuantidade || 0;
        document.getElementById("rec-tem-siga").value = nf.temAnexoSIGA ? "SIM_GLOBAL" : "NAO";
      }
      runInvoiceReconciliation();
    });
  }

  if (btnRun) {
    btnRun.addEventListener("click", runInvoiceReconciliation);
  }
  runInvoiceReconciliation();
}

function runInvoiceReconciliation() {
  const nfIdent = document.getElementById("rec-nf-numero")?.value || "NFS-e 4827";
  const valorNF = parseFloat(document.getElementById("rec-valor-nf")?.value || "3559565.67");
  const usnSIGA = parseFloat(document.getElementById("rec-usn-siga")?.value || "1936567.54");
  const ustSIGA = parseFloat(document.getElementById("rec-ust-siga")?.value || "488");
  const statusSIGA = document.getElementById("rec-tem-siga")?.value || "SIM_GLOBAL";

  const calcUSN = +(usnSIGA * 1.76).toFixed(2);
  const calcUST = +(ustSIGA * 309.85).toFixed(2);
  const calcTotal = +(calcUSN + calcUST).toFixed(2);
  const diffNF = +(valorNF - calcTotal).toFixed(2);

  // Comparar contra o somatório das OSs formalmente assinadas com valor (R$ 2.671.505,17/mês)
  const tetoOSAssinadas = 2671505.17;
  const excessoSemOS = Math.max(0, +(valorNF - tetoOSAssinadas).toFixed(2));
  const mediaMensalUSN = 1891363;
  const excessoMediaUSN = Math.max(0, +(usnSIGA - mediaMensalUSN).toFixed(2));

  const out = document.getElementById("invoice-reconciler-output");
  if (!out) return;

  const isMathOk = Math.abs(diffNF) < 1.0;

  out.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
      <div class="p-3 rounded-lg bg-slate-950 border border-slate-800">
        <span class="text-[11px] text-slate-400 block">Valor Calculado (USN×1,76 + UST×309,85)</span>
        <span class="font-mono text-base font-bold ${isMathOk ? "text-emerald-400" : "text-rose-400"}">${fmtBRL(calcTotal)}</span>
        <span class="text-[11px] text-slate-400 block mt-0.5">Diferença p/ NF: ${fmtBRL(diffNF)}</span>
      </div>
      <div class="p-3 rounded-lg bg-slate-950 border border-slate-800">
        <span class="text-[11px] text-slate-400 block">Faturamento Acima das OSs Assinadas c/ Valor</span>
        <span class="font-mono text-base font-bold ${excessoSemOS > 0 ? "text-amber-400" : "text-emerald-400"}">${fmtBRL(excessoSemOS)}</span>
        <span class="text-[11px] text-slate-400 block mt-0.5">Teto OSs Assinadas: R$ 2,67M/mês</span>
      </div>
      <div class="p-3 rounded-lg bg-slate-950 border border-slate-800">
        <span class="text-[11px] text-slate-400 block">Desvio vs Média Contratual USN (1,89M)</span>
        <span class="font-mono text-base font-bold ${excessoMediaUSN > 0 ? "text-rose-400" : "text-emerald-400"}">${excessoMediaUSN > 0 ? "+" + fmtNum(excessoMediaUSN) + " USN" : "Dentro da Média"}</span>
        <span class="text-[11px] text-slate-400 block mt-0.5">Média TR: 1.891.363 USN/mês</span>
      </div>
    </div>

    <div class="p-4 rounded-lg bg-slate-950 border border-indigo-500/30 text-xs space-y-2">
      <div class="font-bold text-indigo-300 uppercase tracking-wider">Minuta Automática de Despacho de Fiscalização (${nfIdent})</div>
      <p class="text-slate-300 leading-relaxed font-mono text-[11px]">
        "1. Em análise de conformidade da <strong>${nfIdent}</strong> no valor de <strong>${fmtBRL(valorNF)}</strong>, verifica-se que:
        ${
          statusSIGA === "NAO"
            ? " ❌ NÃO FOI JUNTADO o Relatório Analítico SIGA/GCP nem o RMEC, inviabilizando a conferência aritmética de USN × R$ 1,76 e UST × R$ 309,85 (Infração à Seção 11.1 do TR). Recomenda-se RETENÇÃO CAUTELAR DO ATESTO até juntada do espelho de medição."
            : statusSIGA === "SIM_GLOBAL"
            ? ` ⚠️ Foi juntado Anexo SIGA global (${fmtNum(usnSIGA)} USN = ${fmtBRL(calcUSN)} e ${fmtNum(ustSIGA)} UST = ${fmtBRL(calcUST)}), com fechamento aritmético exato (${fmtBRL(calcTotal)}), porém SEM DESMEMBRAMENTO POR ORDEM DE SERVIÇO (OS_01 a OS_27). Além disso, ${fmtBRL(excessoSemOS)} referem-se a projetos cuja OS não possui tabela financeira assinada (como OS_06 Data Foundation). Solicita-se à CELEPAR a abertura analítica por projeto GCP/OS.`
            : " ✅ Anexo SIGA analítico por OS e RMEC validados em conformidade com os limites autorizados nas Ordens de Serviço."
        }"
      </p>
    </div>
  `;
}

// ============================================================================
// 4. AUDITORIA DE CONFORMIDADE (14 ACHADOS) & CALCULADORA DE GLOSAS (IMR)
// ============================================================================
function renderAuditoriaView() {
  const achados = window.CONTRACT_DATA.achadosAuditoria;
  const filtered = achados.filter(
    (a) => AppState.auditSeveridadeFilter === "TODAS" || a.severidade === AppState.auditSeveridadeFilter
  );

  const container = document.getElementById("auditoria-achados-grid");
  if (!container) return;

  container.innerHTML = filtered
    .map((a) => {
      const badgeClass =
        a.severidade === "CRÍTICA" ? "badge-danger" : a.severidade === "ALTA" ? "badge-warning" : "badge-info";

      return `
      <div class="glass-card p-5 border-l-4 ${
        a.severidade === "CRÍTICA" ? "border-l-rose-500" : a.severidade === "ALTA" ? "border-l-amber-500" : "border-l-sky-500"
      }">
        <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div class="flex items-center gap-2">
            <span class="font-mono font-bold text-xs px-2 py-0.5 rounded bg-slate-800 text-sky-300">${a.id}</span>
            <span class="text-xs font-semibold text-slate-400">${a.categoria}</span>
          </div>
          <span class="badge ${badgeClass}">${a.severidade}</span>
        </div>
        <h4 class="text-sm font-bold text-white mb-2">${a.titulo}</h4>
        <p class="text-xs text-slate-300 leading-relaxed mb-3">${a.descricao}</p>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] bg-slate-950/70 p-3 rounded-lg border border-slate-800 mb-3">
          <div><span class="text-slate-400">Base Legal/Contratual:</span> <strong class="text-slate-200">${a.referenciaLegal}</strong></div>
          <div><span class="text-slate-400">Exposição Financeira Associada:</span> <strong class="font-mono text-amber-300">${a.impactoFinanceiroEstimado > 0 ? fmtBRL(a.impactoFinanceiroEstimado) : "Risco Operacional / Qualitativo"}</strong></div>
          <div class="md:col-span-2"><span class="text-slate-400">OSs Impactadas:</span> <span class="font-mono text-sky-300">${a.osImpactadas.join(", ")}</span></div>
        </div>
        <div class="text-xs text-emerald-300 bg-emerald-950/30 border border-emerald-500/30 p-2.5 rounded-lg">
          <strong>Recomendação de Engenharia & Controle:</strong> ${a.recomendacao}
        </div>
      </div>
    `;
    })
    .join("");
}

function filterAuditoria(sev) {
  AppState.auditSeveridadeFilter = sev;
  renderAuditoriaView();
}

function setupIMRCalculatorEvents() {
  const inputs = ["imr-valor-fatura", "imr-valor-ust-os", "imr-uptime", "imr-atraso-orcamento", "imr-atraso-rmec", "imr-ust-sem-evidencia"];
  inputs.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", calculateIMRGlosa);
  });
  calculateIMRGlosa();
}

function calculateIMRGlosa() {
  const valorFatura = parseFloat(document.getElementById("imr-valor-fatura")?.value || "3559565.67");
  const valorUSTOS = parseFloat(document.getElementById("imr-valor-ust-os")?.value || "151206.80");
  const uptime = parseFloat(document.getElementById("imr-uptime")?.value || "99.20");
  const diasAtrasoOrc = parseInt(document.getElementById("imr-atraso-orcamento")?.value || "12", 10);
  const diasAtrasoRMEC = parseInt(document.getElementById("imr-atraso-rmec")?.value || "5", 10);
  const ustSemEvidencia = parseFloat(document.getElementById("imr-ust-sem-evidencia")?.value || "156");

  // 1. Glosa por Disponibilidade GCP (< 99.5%)
  let pctGlosaUptime = 0;
  if (uptime < 98.0) pctGlosaUptime = 10.0;
  else if (uptime < 99.0) pctGlosaUptime = 5.0;
  else if (uptime < 99.5) pctGlosaUptime = 2.0;
  const glosaUptime = +(valorUSTOS * (pctGlosaUptime / 100)).toFixed(2);

  // 2. Glosa por Atraso na Entrega de Orçamento (> 10 dias úteis)
  const diasExcedentesOrc = Math.max(0, diasAtrasoOrc - 10);
  const pctGlosaOrc = Math.min(2.0, diasExcedentesOrc * 0.25);
  const glosaOrcamento = +(valorUSTOS * (pctGlosaOrc / 100)).toFixed(2);

  // 3. Glosa por Atraso no RMEC (> 5º dia útil)
  const pctGlosaRMEC = diasAtrasoRMEC > 0 ? Math.min(2.0, diasAtrasoRMEC * 0.2) : 0;
  const glosaRMEC = +(valorUSTOS * (pctGlosaRMEC / 100)).toFixed(2);

  // 4. Glosa Direta por UST cobrada sem entregável/evidência (ex: erro OS_03 / OS_04)
  const glosaUSTDireta = +(ustSemEvidencia * 309.85).toFixed(2);

  const totalGlosa = +(glosaUptime + glosaOrcamento + glosaRMEC + glosaUSTDireta).toFixed(2);
  const valorLiquidoPagar = Math.max(0, +(valorFatura - totalGlosa).toFixed(2));

  const resEl = document.getElementById("imr-calculator-result");
  if (!resEl) return;

  resEl.innerHTML = `
    <div class="space-y-2 text-xs">
      <div class="flex justify-between py-1.5 border-b border-slate-800">
        <span class="text-slate-400">1. Glosa SLA Disponibilidade (${uptime.toFixed(2)}% → ${pctGlosaUptime}% s/ UST):</span>
        <span class="font-mono font-semibold text-rose-400">- ${fmtBRL(glosaUptime)}</span>
      </div>
      <div class="flex justify-between py-1.5 border-b border-slate-800">
        <span class="text-slate-400">2. Glosa Atraso Orçamento OS (${diasExcedentesOrc}d úteis excedentes → ${pctGlosaOrc.toFixed(2)}%):</span>
        <span class="font-mono font-semibold text-rose-400">- ${fmtBRL(glosaOrcamento)}</span>
      </div>
      <div class="flex justify-between py-1.5 border-b border-slate-800">
        <span class="text-slate-400">3. Glosa Atraso RMEC/SIGA (${diasAtrasoRMEC}d úteis atraso → ${pctGlosaRMEC.toFixed(2)}%):</span>
        <span class="font-mono font-semibold text-rose-400">- ${fmtBRL(glosaRMEC)}</span>
      </div>
      <div class="flex justify-between py-1.5 border-b border-slate-800">
        <span class="text-slate-400">4. Glosa Técnica Direta (${fmtNum(ustSemEvidencia)} UST × R$ 309,85 s/ evidência):</span>
        <span class="font-mono font-semibold text-rose-400">- ${fmtBRL(glosaUSTDireta)}</span>
      </div>
      <div class="flex justify-between py-2 bg-rose-950/40 px-3 rounded-lg border border-rose-500/30 font-bold text-sm">
        <span class="text-rose-300">Total de Glosa / Retenção Apurada (IMR):</span>
        <span class="font-mono text-rose-400">- ${fmtBRL(totalGlosa)}</span>
      </div>
      <div class="flex justify-between py-2 bg-emerald-950/40 px-3 rounded-lg border border-emerald-500/30 font-bold text-sm">
        <span class="text-emerald-300">Valor Líquido Autorizado para Liquidação (NL):</span>
        <span class="font-mono text-emerald-400">${fmtBRL(valorLiquidoPagar)}</span>
      </div>
    </div>
  `;
}

// ============================================================================
// 5. CATÁLOGO OFICIAL UST/USN & SIMULADOR DE DIMENSIONAMENTO ("ANTI-ERRO OS_03/04")
// ============================================================================
function renderCatalogoTable() {
  const cat = window.CONTRACT_DATA.catalogoUST;
  const tbody = document.getElementById("catalogo-ust-tbody");
  if (!tbody) return;

  tbody.innerHTML = cat.ofertas
    .map(
      (o) => `
    <tr class="border-b border-slate-800/80 hover:bg-slate-800/40">
      <td class="py-2.5 px-3 font-mono font-bold text-sky-400 text-xs">${o.codigo}</td>
      <td class="py-2.5 px-3 text-xs text-slate-300">${o.categoria}</td>
      <td class="py-2.5 px-3 text-xs font-semibold text-white">${o.nome}</td>
      <td class="py-2.5 px-3"><span class="badge ${o.periodicidade === "Mensal" ? "badge-info" : "badge-warning"}">${o.periodicidade}</span></td>
      <td class="py-2.5 px-3 font-mono font-bold text-indigo-300 text-xs">${o.ustBase} UST</td>
      <td class="py-2.5 px-3 font-mono text-emerald-400 text-xs">${fmtBRL(o.valorBase)}</td>
      <td class="py-2.5 px-3 text-[11px] text-slate-400">${o.entregaveis}</td>
    </tr>
  `
    )
    .join("");
}

function setupSimulatorEvents() {
  const ids = ["sim-usn-mensal", "sim-entidades", "sim-complexidade", "sim-compare-os"];
  ids.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", runUSTSimulator);
  });

  document.querySelectorAll(".sim-oferta-check").forEach((chk) => {
    chk.addEventListener("change", runUSTSimulator);
  });

  // Preset de comparação com OS real
  const compareSelect = document.getElementById("sim-compare-os");
  if (compareSelect) {
    compareSelect.addEventListener("change", () => {
      const osId = compareSelect.value;
      if (osId === "CUSTOM") return;
      const os = window.CONTRACT_DATA.ordensServico.find((o) => o.id === osId);
      if (os) {
        document.getElementById("sim-usn-mensal").value = os.camadaPT.usnMensalPT || 58459.38;
        // Ajustar checkboxes padrão conforme a OS
        document.querySelectorAll(".sim-oferta-check").forEach((c) => (c.checked = true));
        if (osId === "OS_01" || osId === "OS_04") {
          // JACA e PMPR não cobraram GCP_DEV_001 e GCP_DEV_002 na parcela única (apenas 208 UST de gestão)
          const c1 = document.querySelector('.sim-oferta-check[value="GCP_DEV_001"]');
          const c2 = document.querySelector('.sim-oferta-check[value="GCP_DEV_002"]');
          if (c1) c1.checked = false;
          if (c2) c2.checked = false;
        }
        runUSTSimulator();
      }
    });
  }

  runUSTSimulator();
}

function runUSTSimulator() {
  const usnMensal = parseFloat(document.getElementById("sim-usn-mensal")?.value || "145655.10");
  const fatorEntidades = parseFloat(document.getElementById("sim-entidades")?.value || "1.0");
  const fatorComplexidade = parseFloat(document.getElementById("sim-complexidade")?.value || "1.0");
  const compareOSId = document.getElementById("sim-compare-os")?.value || "OS_03";

  // Determinar porte pelo volume de USN conforme TR Anexo II
  let porteNome = "Pequeno (≤ 30k USN)";
  let fatorTamanho = 1.0;
  if (usnMensal > 1000000) {
    porteNome = "Muito Grande (> 1M USN)";
    fatorTamanho = 3.0;
  } else if (usnMensal > 200000) {
    porteNome = "Grande (200k a 1M USN)";
    fatorTamanho = 3.0;
  } else if (usnMensal > 30000) {
    porteNome = "Médio (30k a 200k USN)";
    fatorTamanho = 2.0;
  }

  const checkedCodes = Array.from(document.querySelectorAll(".sim-oferta-check:checked")).map((c) => c.value);
  const ofertas = window.CONTRACT_DATA.catalogoUST.ofertas;

  let ustUnicaTotal = 0;
  let ustMensalTotal = 0;

  ofertas.forEach((of) => {
    if (!checkedCodes.includes(of.codigo)) return;
    // No dimensionamento padrão base (1x) usado pela Celepar nas OSs 01, 03, 04, 18:
    const mult = of.categoria === "Gestão de Projetos" ? fatorEntidades : fatorComplexidade;
    const qtd = +(of.ustBase * mult).toFixed(2);
    if (of.periodicidade === "Única") ustUnicaTotal += qtd;
    else ustMensalTotal += qtd;
  });

  const valorUSNMensal = +(usnMensal * 1.76).toFixed(2);
  const valorUSTMensal = +(ustMensalTotal * 309.85).toFixed(2);
  const valorUSTUnica = +(ustUnicaTotal * 309.85).toFixed(2);
  const totalMensalSimulado = +(valorUSNMensal + valorUSTMensal).toFixed(2);

  // Comparação com OS selecionada
  let comparacaoHTML = "";
  if (compareOSId !== "CUSTOM") {
    const os = window.CONTRACT_DATA.ordensServico.find((o) => o.id === compareOSId);
    if (os) {
      const diffMensalOS = +(os.camadaOS.valorUSTMensalOS - valorUSTMensal).toFixed(2);
      const diffUnicaOS = +(os.camadaOS.valorUSTUnicaOS - valorUSTUnica).toFixed(2);
      const diffQtdMensal = +(os.camadaOS.ustMensalOS - ustMensalTotal).toFixed(2);

      comparacaoHTML = `
        <div class="mt-4 p-3.5 rounded-xl bg-slate-950 border ${
          Math.abs(diffMensalOS) > 1 || Math.abs(diffUnicaOS) > 1 || Math.abs(diffQtdMensal) > 0.1
            ? "border-rose-500/50"
            : "border-emerald-500/40"
        }">
          <div class="text-xs font-bold uppercase tracking-wider text-sky-300 mb-2">
            Auditoria Automática contra ${os.id} (${os.siglaOrgao})
          </div>
          <div class="space-y-1 text-xs">
            <div class="flex justify-between">
              <span class="text-slate-400">UST Mensal (Catálogo × Impresso na ${os.id}):</span>
              <span class="font-mono">${fmtNum(ustMensalTotal)} UST (${fmtBRL(valorUSTMensal)}) vs <strong>${fmtNum(os.camadaOS.ustMensalOS)} UST (${fmtBRL(os.camadaOS.valorUSTMensalOS)})</strong></span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-400">UST Única (Catálogo × Impresso na ${os.id}):</span>
              <span class="font-mono">${fmtNum(ustUnicaTotal)} UST (${fmtBRL(valorUSTUnica)}) vs <strong>${fmtNum(os.camadaOS.ustUnicaOS)} UST (${fmtBRL(os.camadaOS.valorUSTUnicaOS)})</strong></span>
            </div>
            <div class="pt-1.5 border-t border-slate-800 font-semibold ${
              Math.abs(diffMensalOS) > 1 || Math.abs(diffQtdMensal) > 0.1 ? "text-rose-400" : "text-emerald-400"
            }">
              ${
                os.id === "OS_03"
                  ? `⚠️ ERRO DETECTADO NA OS_03: A OS imprimiu R$ 27.266,80 para 244 UST/mês (diferença de ${fmtBRL(diffMensalOS)}/mês) e R$ 84.279,20 para 688 UST única (diferença de ${fmtBRL(diffUnicaOS)})!`
                  : os.id === "OS_04"
                  ? `⚠️ ERRO DETECTADO NA OS_04: A OS imprimiu 732,00 UST/mês na coluna de quantidade para o valor de 244 UST/mês (excesso de +488 UST/mês = R$ 151.206,80/mês)!`
                  : Math.abs(diffMensalOS) > 1
                  ? `⚠️ Divergência de ${fmtBRL(diffMensalOS)}/mês entre o Catálogo Oficial e o quadro impresso na ${os.id}.`
                  : `✅ Quadro aritmético da ${os.id} fecha exatamente com a memória de cálculo do Catálogo UST.`
              }
            </div>
          </div>
        </div>
      `;
    }
  }

  const out = document.getElementById("ust-simulator-output");
  if (!out) return;

  out.innerHTML = `
    <div class="flex items-center justify-between text-xs bg-slate-950 p-3 rounded-lg border border-slate-800 mb-3">
      <span class="text-slate-400">Classificação Automática de Porte (TR Anexo II):</span>
      <span class="font-mono font-bold text-sky-300">${porteNome} (Fator Porte Ref.: ${fatorTamanho}x)</span>
    </div>
    <div class="grid grid-cols-2 gap-3">
      <div class="p-3 rounded-lg bg-slate-950 border border-slate-800">
        <span class="text-[11px] text-slate-400 block">USN Mensal (@ R$ 1,76)</span>
        <span class="font-mono text-base font-bold text-sky-300">${fmtBRL(valorUSNMensal)}</span>
        <span class="font-mono text-[11px] text-slate-400 block">${fmtNum(usnMensal)} USN/mês</span>
      </div>
      <div class="p-3 rounded-lg bg-slate-950 border border-slate-800">
        <span class="text-[11px] text-slate-400 block">UST Mensal (@ R$ 309,85)</span>
        <span class="font-mono text-base font-bold text-indigo-300">${fmtBRL(valorUSTMensal)}</span>
        <span class="font-mono text-[11px] text-slate-400 block">${fmtNum(ustMensalTotal)} UST/mês</span>
      </div>
      <div class="p-3 rounded-lg bg-slate-950 border border-slate-800">
        <span class="text-[11px] text-slate-400 block">UST Parcela Única (@ R$ 309,85)</span>
        <span class="font-mono text-base font-bold text-amber-300">${fmtBRL(valorUSTUnica)}</span>
        <span class="font-mono text-[11px] text-slate-400 block">${fmtNum(ustUnicaTotal)} UST única</span>
      </div>
      <div class="p-3 rounded-lg bg-emerald-950/30 border border-emerald-500/40">
        <span class="text-[11px] text-emerald-300 block">Custo Total Mensal Recorrente</span>
        <span class="font-mono text-base font-bold text-emerald-400">${fmtBRL(totalMensalSimulado)}/mês</span>
        <span class="font-mono text-[11px] text-emerald-300/80 block">Anualizado: ${fmtBRL(totalMensalSimulado * 12)}</span>
      </div>
    </div>
    ${comparacaoHTML}
  `;
}

// ============================================================================
// 6. CALCULADORA DE PRAZOS ÚTEIS (SLA) & REPOSITÓRIO DOCUMENTAL COMPLETO
// ============================================================================
function setupSLADateCalculatorEvents() {
  const dtInput = document.getElementById("sla-start-date");
  const typeSelect = document.getElementById("sla-rule-type");
  if (dtInput) dtInput.addEventListener("change", calculateSLADeadline);
  if (typeSelect) typeSelect.addEventListener("change", calculateSLADeadline);
  calculateSLADeadline();
}

function addBusinessDays(startDateStr, businessDays) {
  const parts = startDateStr.split("-");
  let cur = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
  let added = 0;
  while (added < businessDays) {
    cur.setDate(cur.getDate() + 1);
    const day = cur.getDay();
    if (day !== 0 && day !== 6) {
      added++;
    }
  }
  return cur.toLocaleDateString("pt-BR");
}

function calculateSLADeadline() {
  const startDate = document.getElementById("sla-start-date")?.value || "2026-10-13";
  const ruleDays = parseInt(document.getElementById("sla-rule-type")?.value || "10", 10);
  const deadlineStr = addBusinessDays(startDate, ruleDays);
  const extendedStr = addBusinessDays(startDate, ruleDays + 5);

  const out = document.getElementById("sla-deadline-output");
  if (!out) return;

  out.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-4 p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
      <div>
        <span class="text-slate-400 block">Prazo Fatal Ordinário (${ruleDays} dias úteis):</span>
        <span class="font-mono text-base font-bold text-emerald-400">${deadlineStr}</span>
      </div>
      <div>
        <span class="text-slate-400 block">Limite c/ Prorrogação Justificada (+5 dias úteis):</span>
        <span class="font-mono text-base font-bold text-amber-300">${extendedStr}</span>
      </div>
      <div class="text-[11px] text-slate-400 max-w-xs">
        Cálculo exclui sábados e domingos conforme regra de contagem em dias úteis da Lei 14.133/2021 (Art. 183) e TR 9291/2025.
      </div>
    </div>
  `;
}

function renderDocumentosView() {
  const D = window.CONTRACT_DATA;

  // Tabela de SLAs
  const slaTbody = document.getElementById("sla-rules-tbody");
  if (slaTbody) {
    slaTbody.innerHTML = D.regrasSLA
      .map(
        (s) => `
      <tr class="border-b border-slate-800/80">
        <td class="py-3 px-3 font-mono font-bold text-sky-400 text-xs">${s.codigo}</td>
        <td class="py-3 px-3 text-xs font-semibold text-white">${s.etapa}</td>
        <td class="py-3 px-3 text-xs text-slate-300">${s.indicador}</td>
        <td class="py-3 px-3 font-mono text-xs text-emerald-300">${s.prazoContratual}</td>
        <td class="py-3 px-3 text-xs text-amber-300">${s.penalidadeIMR}</td>
        <td class="py-3 px-3 text-xs text-rose-300 font-medium">${s.statusAtual}</td>
      </tr>
    `
      )
      .join("");
  }

  // Cards de Documentos Estruturantes
  const docsGrid = document.getElementById("estruturantes-docs-grid");
  if (docsGrid) {
    docsGrid.innerHTML = D.documentos
      .map(
        (doc) => `
      <div class="glass-card p-4 flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="badge badge-info">${doc.categoria}</span>
            <span class="font-mono text-xs text-slate-400">${doc.paginas}</span>
          </div>
          <h4 class="text-sm font-bold text-white mb-1">${doc.titulo}</h4>
          <p class="text-xs text-slate-400 mb-3">${doc.destaque}</p>
        </div>
        <div class="flex items-center justify-between pt-3 border-t border-slate-800">
          <span class="font-mono text-[11px] text-slate-400">Prot: ${doc.protocolo}</span>
          <a href="${doc.caminho}" target="_blank" class="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold transition">
            Abrir Arquivo ↗
          </a>
        </div>
      </div>
    `
      )
      .join("");
  }

  // Galeria rápida de todas as 27 Pastas de OS
  const osDocsGrid = document.getElementById("os-docs-quick-grid");
  if (osDocsGrid) {
    osDocsGrid.innerHTML = D.ordensServico
      .map(
        (os) => `
      <div class="p-3 rounded-xl bg-slate-900/90 border border-slate-800 flex items-center justify-between gap-2 hover:border-sky-500/40 transition">
        <div class="min-w-0">
          <div class="flex items-center gap-1.5">
            <span class="font-mono font-bold text-xs text-sky-400">${os.id}</span>
            <span class="text-xs font-semibold text-white truncate">${os.siglaOrgao}</span>
          </div>
          <div class="text-[11px] text-slate-400 truncate" title="${os.titulo}">${os.titulo}</div>
          <div class="font-mono text-[10px] text-slate-500">Prot: ${os.protocolo}</div>
        </div>
        <div class="flex items-center gap-1 shrink-0">
          ${
            os.arquivos.osPdf
              ? `<a href="${os.arquivos.osPdf}" target="_blank" class="px-2 py-1 rounded bg-slate-800 hover:bg-sky-600 text-slate-200 hover:text-white text-[11px] font-mono">OS</a>`
              : `<span class="px-2 py-1 rounded bg-rose-950/60 text-rose-400 text-[10px] font-mono">S/OS</span>`
          }
          <a href="${os.arquivos.processoPdf}" target="_blank" class="px-2 py-1 rounded bg-slate-800 hover:bg-indigo-600 text-slate-200 hover:text-white text-[11px] font-mono">Proc.</a>
        </div>
      </div>
    `
      )
      .join("");
  }
}

// ============================================================================
// 7. FLUXO INSTRUÇÕES.MD (10 ETAPAS), CICLOS RMEC & RAZÃO CRONOLÓGICO
// ============================================================================
const INSTRUCOES_10_STEPS_META = [
  { step: 1, title: "1. Solicitação + Plano de Trabalho", desc: "Órgão solicita serviço com PT, escopo e cronograma", scope: "Por OS (OS_01..27)" },
  { step: 2, title: "2. SEIA ➔ CELEPAR (Custos)", desc: "SEIA encaminha protocolo à Celepar p/ levantar custos", scope: "Por OS (OS_01..27)" },
  { step: 3, title: "3. Retorno Custos CELEPAR", desc: "Celepar devolve Dimensionamento Inicial (USN + UST)", scope: "Por OS (OS_01..27)" },
  { step: 4, title: "4. Emissão da OS (SEIA)", desc: "SEIA emite Ordem de Serviço autorizando execução", scope: "Por OS (OS_01..27)" },
  { step: 5, title: "5. Confirmação de Execução", desc: "SEIA recebe confirmação de início / bloqueio de prod.", scope: "Por OS (OS_01..27)" },
  { step: 6, title: "6. RMEC Mensal & Atesto SEIA", desc: "Celepar envia RMECs no 25.609.621-8 e SEIA atesta", scope: "Mensal (25.609.621-8)" },
  { step: 7, title: "7. NF + Atesto ➔ Envio ao NAS", desc: "Juntada da NFS-e no 24.574.062-0 e envio ao NAS", scope: "Mensal (24.574.062-0)" },
  { step: 8, title: "8. NAS lança GMS ➔ Envia NFS", desc: "NAS registra medição no GMS e remete ao NFS", scope: "Mensal (24.574.062-0)" },
  { step: 9, title: "9. NFS Paga (NL/OB) ➔ NAS", desc: "NFS liquida (NL), paga (OB) no SIAFIC e devolve", scope: "Mensal (24.574.062-0)" },
  { step: 10, title: "10. Arquivamento & Novo Ciclo", desc: "NAS arquiva comprovante e inicia ciclo seguinte", scope: "Recorrente (36 meses)" }
];

function renderCronologiaView() {
  const D = window.CONTRACT_DATA;
  const events = D.linhaTempoCronologica || [];
  const ciclos = D.ciclosRMEC || [];
  const wfMap = D.fluxoInstrucoesOS || {};

  // 1. Renderizar Stepper das 10 Etapas
  const stepsGrid = document.getElementById("instrucoes-10-steps-grid");
  if (stepsGrid) {
    stepsGrid.innerHTML = INSTRUCOES_10_STEPS_META.map((m) => {
      const count = events.filter((e) => Number(e.step_number) === m.step).length;
      const isMonthly = m.step >= 6;
      return `
        <button onclick="filterCronologiaStep('${m.step}')" class="text-left p-3 rounded-xl bg-slate-950/90 hover:bg-slate-900 border ${
          isMonthly ? "border-purple-500/30 hover:border-purple-400" : "border-sky-500/30 hover:border-sky-400"
        } transition group">
          <div class="flex items-center justify-between mb-1">
            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
              isMonthly ? "bg-purple-500/20 text-purple-300" : "bg-sky-500/20 text-sky-300"
            }">ETAPA ${m.step}</span>
            <span class="font-mono text-[11px] text-emerald-400 font-bold">${count} eventos</span>
          </div>
          <div class="text-xs font-bold text-white group-hover:text-sky-300 transition">${m.title}</div>
          <div class="text-[11px] text-slate-400 mt-0.5 leading-snug">${m.desc}</div>
          <div class="text-[10px] font-mono text-slate-500 mt-1.5">${m.scope}</div>
        </button>
      `;
    }).join("");
  }

  // 2. Renderizar Tabela dos 8 Ciclos Mensais (Processo 25.609.621-8 -> Processo 24.574.062-0)
  const rmecTbody = document.getElementById("rmec-cycles-tbody");
  if (rmecTbody) {
    rmecTbody.innerHTML = ciclos
      .map((c, idx) => {
        const isPaid = c.status_ciclo === "PAGO_E_ARQUIVADO";
        const hasGlosa = Boolean(c.glosa_ou_devolucao);
        const firstPageRMEC = parseInt((c.rmec_pages || "21").split("-")[0], 10) || 21;
        const firstPageNF = parseInt((c.nf_page_proc_mae || "747").replace(/[^0-9]/g, ""), 10) || 747;
        const firstPageOB = parseInt((c.nfs_pagamento_page || "760").split("-")[0], 10) || 760;

        return `
          <tr class="border-b border-slate-800/80 hover:bg-slate-900/60 transition text-xs">
            <td class="py-3 px-3">
              <div class="font-mono font-bold text-white">${c.competencia}</div>
              <span class="badge ${isPaid ? "badge-success" : "badge-warning"} mt-1 inline-block">${c.status_ciclo}</span>
            </td>
            <td class="py-3 px-3">
              <div class="font-mono text-purple-300 font-semibold">${c.oficio_celepar}</div>
              <div class="text-[11px] text-slate-400">Em ${c.rmec_submission_date.split("-").reverse().join("/")}</div>
              <a href="../Processo_25.609.621-8_1.pdf#page=${firstPageRMEC}" target="_blank" class="inline-block mt-1 px-2 py-0.5 rounded bg-purple-950/60 border border-purple-500/40 text-purple-200 font-mono text-[10px] hover:bg-purple-800">
                📄 Fls. ${c.rmec_pages} (25.609.621-8) ↗
              </a>
            </td>
            <td class="py-3 px-3 font-mono">
              <div class="text-white font-bold">${fmtBRL(c.total_rmec_brl)}</div>
              <div class="text-[11px] text-sky-300">${fmtNum(c.total_usn)} USN</div>
              <div class="text-[11px] text-indigo-300">${fmtNum(c.total_ust)} UST</div>
            </td>
            <td class="py-3 px-3">
              ${
                c.seia_atesto_date
                  ? `<div class="font-mono text-emerald-400 font-semibold">✅ Atestado em ${c.seia_atesto_date.split("-").reverse().join("/")}</div>
                     <a href="../Processo_25.609.621-8_1.pdf#page=${c.seia_atesto_page}" target="_blank" class="inline-block mt-1 px-2 py-0.5 rounded bg-emerald-950/50 border border-emerald-500/40 text-emerald-300 font-mono text-[10px] hover:bg-emerald-800">
                       📄 Atesto SEIA Fl. ${c.seia_atesto_page} ↗
                     </a>`
                  : `<div class="font-mono text-amber-300 font-semibold">⏳ Aguardando Atesto SEIA</div>
                     <div class="text-[11px] text-slate-400">Submetido na Fl. 766</div>`
              }
              ${
                hasGlosa
                  ? `<div class="mt-1.5 p-1.5 rounded bg-rose-950/50 border border-rose-500/40 text-[10px] text-rose-200 leading-snug">
                       ⚠️ <strong>Fiscalização SEIA:</strong> ${c.glosa_ou_devolucao}
                     </div>`
                  : ""
              }
            </td>
            <td class="py-3 px-3 font-mono">
              ${
                c.nf_numero !== "AGUARDANDO_ATESTO"
                  ? `<div class="text-white font-bold">NFS-e ${c.nf_numero}</div>
                     <div class="text-[11px] text-slate-400">${c.nf_emissao_date.split("-").reverse().join("/")}</div>
                     <a href="../Processo_24.574.062-0_1.pdf#page=${firstPageNF}" target="_blank" class="inline-block mt-1 px-2 py-0.5 rounded bg-slate-800 text-sky-300 text-[10px] hover:bg-slate-700">
                       📄 Proc. Mãe Fl. ${c.nf_page_proc_mae} ↗
                     </a>`
                  : `<span class="text-slate-500">Aguarda Etapa 6</span>`
              }
            </td>
            <td class="py-3 px-3">
              ${
                c.nas_gms_date
                  ? `<div class="font-mono text-sky-300 font-semibold">${c.nas_gms_date.split("-").reverse().join("/")}</div>
                     <div class="text-[11px] text-slate-400">Lançado GMS 47396/2025 (Fl. ${c.nas_gms_page})</div>`
                  : `<span class="text-slate-500 font-mono">—</span>`
              }
            </td>
            <td class="py-3 px-3">
              ${
                c.nfs_pagamento_date
                  ? `<div class="font-mono text-emerald-400 font-bold">Pago em ${c.nfs_pagamento_date.split("-").reverse().join("/")}</div>
                     <div class="text-[10px] font-mono text-slate-300">${c.nl_numeros}</div>
                     <div class="text-[10px] font-mono text-slate-400">${c.ob_numeros}</div>
                     <a href="../Processo_24.574.062-0_1.pdf#page=${firstPageOB}" target="_blank" class="inline-block mt-1 px-2 py-0.5 rounded bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 font-mono text-[10px]">
                       📄 Fls. ${c.nfs_pagamento_page} ↗
                     </a>`
                  : `<span class="text-amber-300 font-mono text-[11px]">Em tramitação</span>`
              }
            </td>
            <td class="py-3 px-3 text-right">
              <button onclick="toggleRMECBreakdown(${idx})" class="px-2.5 py-1.5 rounded-lg bg-purple-600/30 hover:bg-purple-600 border border-purple-500/40 text-purple-200 hover:text-white text-xs font-mono font-semibold transition">
                Ver ${(c.os_breakdown || []).length} OSs ▼
              </button>
            </td>
          </tr>
          <tr id="rmec-breakdown-row-${idx}" class="hidden bg-slate-950/95 border-b border-slate-800">
            <td colspan="8" class="p-4">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-bold text-purple-300 font-mono uppercase">Detalhamento de Consumo por Ordem de Serviço — Competência ${c.competencia} (Processo 25.609.621-8_1.pdf, fls. ${c.rmec_pages})</span>
                <span class="text-xs font-mono text-slate-400">Soma do Mês: <strong class="text-white">${fmtBRL(c.total_rmec_brl)}</strong></span>
              </div>
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                ${(c.os_breakdown || [])
                  .map(
                    (b) => `
                  <div class="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col justify-between text-xs">
                    <div>
                      <div class="flex items-center justify-between">
                        <button onclick="openOSDrawer('${b.os}')" class="font-mono font-bold text-sky-400 hover:underline">${b.os} (${b.orgao})</button>
                        <a href="../Processo_25.609.621-8_1.pdf#page=${b.rmec_page}" target="_blank" class="px-2 py-0.5 rounded bg-purple-950/60 border border-purple-500/30 text-purple-300 font-mono text-[10px] hover:bg-purple-800">
                          RMEC Fl. ${b.rmec_page} ↗
                        </a>
                      </div>
                      <div class="text-[11px] text-slate-300 font-medium mt-0.5">${b.projeto}</div>
                      ${b.obs ? `<div class="text-[10px] text-amber-300 mt-1">${b.obs}</div>` : ""}
                    </div>
                    <div class="flex items-center justify-between mt-2 pt-1.5 border-t border-slate-800 font-mono text-[11px]">
                      <span class="text-slate-400">${fmtNum(b.usn)} USN | ${fmtNum(b.ust)} UST</span>
                      <span class="font-bold ${b.total > 0 ? "text-emerald-400" : "text-slate-500"}">${fmtBRL(b.total)}</span>
                    </div>
                  </div>
                `
                  )
                  .join("")}
              </div>
            </td>
          </tr>
        `;
      })
      .join("");
  }

  // 3. Renderizar Tabela das Etapas 1 a 5 por OS (27 OSs)
  filterSteps1To5Table("");

  // 4. Povoar filtro de OSs na Linha do Tempo Cronológica e renderizar
  const osSelect = document.getElementById("crono-filter-os");
  if (osSelect && osSelect.options.length <= 1) {
    osSelect.innerHTML =
      `<option value="TODAS">Todas as OSs / Ciclo Global (136)</option>` +
      `<option value="CICLO_MENSAL">Apenas Ciclos Mensais RMEC/NF/GMS/OB</option>` +
      D.ordensServico.map((o) => `<option value="${o.id}">${o.id} — ${o.siglaOrgao} (${o.titulo})</option>`).join("");
  }
  renderChronologicalTimeline();
}

function toggleRMECBreakdown(idx) {
  const row = document.getElementById(`rmec-breakdown-row-${idx}`);
  if (row) row.classList.toggle("hidden");
}

function filterSteps1To5Table(query) {
  const D = window.CONTRACT_DATA;
  const wfMap = D.fluxoInstrucoesOS || {};
  const tbody = document.getElementById("os-steps-1to5-tbody");
  if (!tbody) return;

  const q = (query || "").toLowerCase().trim();
  const filteredOS = D.ordensServico.filter((os) => {
    if (!q) return true;
    return (
      os.id.toLowerCase().includes(q) ||
      os.siglaOrgao.toLowerCase().includes(q) ||
      os.titulo.toLowerCase().includes(q) ||
      os.protocolo.toLowerCase().includes(q)
    );
  });

  const fmtDateBR = (iso) => (iso ? iso.split("-").reverse().join("/") : "—");
  const statusBadge = (st) => {
    if (st === "CONCLUIDO") return `<span class="text-emerald-400 font-mono text-[10px] font-bold">✅ OK</span>`;
    if (st.includes("SEM_") || st.includes("ERRO") || st.includes("RISCO"))
      return `<span class="text-rose-400 font-mono text-[10px] font-bold">⚠️ ${st}</span>`;
    return `<span class="text-amber-300 font-mono text-[10px] font-bold">⏳ ${st}</span>`;
  };

  tbody.innerHTML = filteredOS
    .map((os) => {
      const wf = wfMap[os.id] || {};
      return `
        <tr class="border-b border-slate-800/70 hover:bg-slate-900/60 text-xs">
          <td class="py-2.5 px-3">
            <button onclick="openOSDrawer('${os.id}')" class="font-mono font-bold text-sky-400 hover:underline">${os.id}</button>
            <div class="text-[11px] font-semibold text-white">${os.siglaOrgao} — ${os.titulo}</div>
            <div class="font-mono text-[10px] text-slate-400">Prot: ${os.protocolo}</div>
          </td>
          <td class="py-2.5 px-3">
            <div class="flex items-center justify-between">${statusBadge(wf.s1_status || "")} <span class="font-mono text-[10px] text-slate-400">${fmtDateBR(wf.s1_date)} (${wf.s1_page})</span></div>
            <div class="text-[11px] text-slate-300 mt-0.5">${wf.s1_note || ""}</div>
          </td>
          <td class="py-2.5 px-3">
            <div class="flex items-center justify-between">${statusBadge(wf.s2_status || "")} <span class="font-mono text-[10px] text-slate-400">${fmtDateBR(wf.s2_date)} (${wf.s2_page})</span></div>
            <div class="text-[11px] text-slate-300 mt-0.5">${wf.s2_note || ""}</div>
          </td>
          <td class="py-2.5 px-3">
            <div class="flex items-center justify-between">${statusBadge(wf.s3_status || "")} <span class="font-mono text-[10px] text-slate-400">${fmtDateBR(wf.s3_date)} (${wf.s3_page})</span></div>
            <div class="text-[11px] text-slate-300 mt-0.5">${wf.s3_note || ""}</div>
          </td>
          <td class="py-2.5 px-3">
            <div class="flex items-center justify-between">${statusBadge(wf.s4_status || "")} <span class="font-mono text-[10px] text-slate-400">${fmtDateBR(wf.s4_date)} (${wf.s4_page})</span></div>
            <div class="text-[11px] text-slate-300 mt-0.5">${wf.s4_note || ""}</div>
          </td>
          <td class="py-2.5 px-3">
            <div class="flex items-center justify-between">${statusBadge(wf.s5_status || "")} <span class="font-mono text-[10px] text-slate-400">${fmtDateBR(wf.s5_date)} (${wf.s5_page})</span></div>
            <div class="text-[11px] text-slate-300 mt-0.5">${wf.s5_note || ""}</div>
          </td>
          <td class="py-2.5 px-3 text-right">
            <a href="${os.arquivos.processoPdf}" target="_blank" class="px-2 py-1 rounded bg-slate-800 hover:bg-indigo-600 text-slate-200 text-[10px] font-mono">Proc. ↗</a>
          </td>
        </tr>
      `;
    })
    .join("");
}

function filterCronologiaStep(stepVal) {
  const sel = document.getElementById("crono-filter-step");
  if (sel) {
    sel.value = String(stepVal);
    renderChronologicalTimeline();
    sel.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function renderChronologicalTimeline() {
  const D = window.CONTRACT_DATA;
  const allEvents = [...(D.linhaTempoCronologica || [])];
  const stepFilter = document.getElementById("crono-filter-step")?.value || "TODAS";
  const osFilter = document.getElementById("crono-filter-os")?.value || "TODAS";
  const sortDir = document.getElementById("crono-sort-dir")?.value || "ASC";
  const searchQ = (document.getElementById("crono-filter-search")?.value || "").toLowerCase().trim();

  const filtered = allEvents.filter((ev) => {
    if (stepFilter !== "TODAS" && String(ev.step_number) !== String(stepFilter)) return false;
    if (osFilter !== "TODAS" && ev.os_id !== osFilter) return false;
    if (searchQ) {
      const hay = `${ev.event_date} ${ev.title} ${ev.description} ${ev.os_id} ${ev.protocolo} ${ev.step_name}`.toLowerCase();
      if (!hay.includes(searchQ)) return false;
    }
    return true;
  });

  filtered.sort((a, b) => {
    const cmp = a.event_date.localeCompare(b.event_date) || a.step_number - b.step_number;
    return sortDir === "ASC" ? cmp : -cmp;
  });

  const counterEl = document.getElementById("crono-summary-counter");
  if (counterEl) {
    counterEl.innerHTML = `Exibindo <strong class="text-white">${filtered.length}</strong> de <strong class="text-white">${allEvents.length}</strong> eventos cronológicos auditados • Ordenação: <strong class="text-emerald-400">${
      sortDir === "ASC" ? "Cronológica Estrita (Mais Antigo ➔ Mais Recente)" : "Cronológica Reversa (Mais Recente ➔ Mais Antigo)"
    }</strong>`;
  }

  const listEl = document.getElementById("chronological-timeline-list");
  if (!listEl) return;

  listEl.innerHTML = filtered
    .map((ev) => {
      const dateBR = ev.event_date.split("-").reverse().join("/");
      const isMonthly = Number(ev.step_number) >= 6;
      const stColor =
        ev.status === "CONCLUIDO" || ev.status === "ATESTO_EMITIDO"
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
          : ev.status.includes("GLOSA") || ev.status.includes("SEM_") || ev.status.includes("ERRO") || ev.status.includes("RISCO")
          ? "border-rose-500/40 bg-rose-500/10 text-rose-300"
          : "border-amber-500/40 bg-amber-500/10 text-amber-300";

      const firstPage = parseInt(String(ev.page_ref || "1").replace(/[^0-9]/g, ""), 10) || 1;
      const pdfHref = ev.doc_path ? `../${ev.doc_path}#page=${firstPage}` : "#";

      return `
        <div class="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-slate-700 transition flex flex-wrap items-start justify-between gap-3">
          <div class="flex items-start gap-3 max-w-4xl">
            <div class="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-center shrink-0 min-w-[92px]">
              <div class="font-mono font-bold text-xs text-sky-400">${dateBR}</div>
              <div class="font-mono text-[10px] ${isMonthly ? "text-purple-300" : "text-slate-400"}">Etapa ${ev.step_number}/10</div>
            </div>
            <div>
              <div class="flex flex-wrap items-center gap-2 mb-1">
                <span class="px-2 py-0.5 rounded bg-slate-800 font-mono text-[10px] font-bold text-white">${ev.os_id}</span>
                <span class="text-[11px] font-mono text-slate-400">Prot: ${ev.protocolo}</span>
                <span class="px-2 py-0.5 rounded border text-[10px] font-mono font-semibold ${stColor}">${ev.status}</span>
                ${ev.valor_brl > 0 ? `<span class="font-mono text-xs font-bold text-emerald-400">${fmtBRL(ev.valor_brl)}</span>` : ""}
              </div>
              <h4 class="text-xs font-bold text-white">${ev.title}</h4>
              <p class="text-xs text-slate-300 mt-0.5 leading-relaxed">${ev.description}</p>
            </div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <a href="${pdfHref}" target="_blank" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-sky-600 text-slate-200 hover:text-white font-mono text-[11px] transition">
              📄 ${ev.page_ref || "Abrir PDF"} ↗
            </a>
          </div>
        </div>
      `;
    })
    .join("");
}

// ============================================================================
// 8. BANCO VETORIAL IA & MOTOR DE INGESTÃO INCREMENTAL (DELTA APPEND-ONLY)
// ============================================================================
function renderVetorialView() {
  const D = window.CONTRACT_DATA;
  const vStat = D.vectorDBStatus || {
    totalPdfsTracked: 29,
    totalPagesIndexed: 3308,
    totalChronologicalEvents: 136,
    estimatedTokensSavedOnUpdate: 2811800,
    watermarks: []
  };

  renderVectorKPIs(vStat);
  renderWatermarksTable(vStat.watermarks || []);

  // Tentar carregar status ao vivo da API Python (/api/status) e rodar busca inicial
  fetch("/api/status")
    .then((r) => r.json())
    .then((data) => {
      if (data && data.ok) {
        renderVectorKPIs({
          totalPdfsTracked: data.total_pdfs,
          totalPagesIndexed: data.total_pages_indexed,
          totalChronologicalEvents: data.total_chronological_events,
          estimatedTokensSavedOnUpdate: data.estimated_tokens_saved_on_resync
        });
        renderWatermarksTable(data.watermarks || []);
      }
    })
    .catch(() => {});

  runVectorSearch();
}

function renderVectorKPIs(vStat) {
  const grid = document.getElementById("vector-db-kpi-grid");
  if (!grid) return;

  grid.innerHTML = `
    <div class="glass-card p-4 border-l-4 border-l-emerald-500">
      <span class="text-[11px] font-mono uppercase text-slate-400">Páginas Indexadas no Vector DB</span>
      <div class="text-2xl font-bold font-mono text-white mt-1">${fmtInt(vStat.totalPagesIndexed)} págs.</div>
      <div class="text-[11px] text-emerald-400 mt-1">29 PDFs (890 Proc. Mãe + 766 RMEC + 1.652 OSs)</div>
    </div>
    <div class="glass-card p-4 border-l-4 border-l-sky-500">
      <span class="text-[11px] font-mono uppercase text-slate-400">Economia de Tokens por Sync Delta</span>
      <div class="text-2xl font-bold font-mono text-sky-400 mt-1">${fmtInt(vStat.estimatedTokensSavedOnUpdate)} tokens</div>
      <div class="text-[11px] text-slate-300 mt-1">100% de cache hit nas páginas 1..N já ingeridas</div>
    </div>
    <div class="glass-card p-4 border-l-4 border-l-purple-500">
      <span class="text-[11px] font-mono uppercase text-slate-400">Eventos Cronológicos (10 Etapas)</span>
      <div class="text-2xl font-bold font-mono text-purple-300 mt-1">${fmtInt(vStat.totalChronologicalEvents)} marcos</div>
      <div class="text-[11px] text-slate-300 mt-1">Indexados por B-Tree (YYYY-MM-DD + Etapa)</div>
    </div>
    <div class="glass-card p-4 border-l-4 border-l-amber-500">
      <span class="text-[11px] font-mono uppercase text-slate-400">Motor de Ingestão Incremental</span>
      <div class="text-lg font-bold font-mono text-amber-300 mt-1">SHA-256 Page Watermark</div>
      <div class="text-[11px] text-slate-300 mt-1">Lê apenas páginas novas (N+1..M) em PDFs atualizados</div>
    </div>
  `;
}

function renderWatermarksTable(watermarks) {
  const tbody = document.getElementById("watermarks-table-tbody");
  if (!tbody) return;

  tbody.innerHTML = watermarks
    .map(
      (w) => `
      <tr class="border-b border-slate-800/70 hover:bg-slate-900/60 text-xs font-mono">
        <td class="py-2 px-3 font-bold text-sky-400">${w.doc_id}</td>
        <td class="py-2 px-3 text-slate-200"><a href="../${w.rel_path}" target="_blank" class="hover:underline text-sky-300">${w.rel_path} ↗</a></td>
        <td class="py-2 px-3 text-slate-400">${w.doc_type}</td>
        <td class="py-2 px-3 text-emerald-400 font-bold">Pág. 1 até ${w.last_ingested_page}</td>
        <td class="py-2 px-3 text-slate-400 text-[11px]">${(w.first_page_sha256 || "").slice(0, 16)}...</td>
        <td class="py-2 px-3 text-purple-300 text-[11px]">${(w.last_page_sha256 || "").slice(0, 16)}...</td>
        <td class="py-2 px-3 text-sky-300">${fmtInt((w.last_ingested_page || 0) * 850)} tokens</td>
        <td class="py-2 px-3 text-right"><span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px]">CACHED (1..${w.last_ingested_page})</span></td>
      </tr>
    `
    )
    .join("");
}

function triggerDeltaSync() {
  const btn = document.getElementById("btn-run-delta-sync");
  const banner = document.getElementById("delta-sync-live-banner");
  const badge = document.getElementById("delta-sync-last-badge");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> Verificando Watermarks SHA-256 dos 29 PDFs...`;
  }

  fetch("/api/ingest-delta", { method: "POST" })
    .then((r) => r.json())
    .then((data) => {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<span>🔄</span> Executar Sincronização Delta Agora`;
      }
      if (data && data.ok && data.summary) {
        const s = data.summary;
        if (badge) {
          badge.innerHTML = `Último Sync: ${s.total_new_pages_ingested} págs novas | ${fmtInt(s.total_cached_pages_skipped)} em cache (${fmtInt(
            s.estimated_tokens_saved
          )} tokens economizados)`;
        }
        if (banner) {
          banner.classList.remove("hidden");
          banner.innerHTML = `
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div class="text-xs font-bold text-emerald-300 uppercase font-mono">✅ Relatório de Ingestão Incremental (Delta Append-Only) Concluído</div>
                <p class="text-xs text-slate-200 mt-1">
                  Foram inspecionados <strong>${s.documents_checked} arquivos PDF</strong>:
                  <strong class="text-emerald-400">${s.total_new_pages_ingested} páginas novas</strong> processadas com IA/Embeddings e
                  <strong class="text-sky-300">${fmtInt(s.total_cached_pages_skipped)} páginas anteriores puladas</strong> via validação de Hash SHA-256 da página N,
                  economizando <strong class="text-emerald-300 font-mono">${fmtInt(s.estimated_tokens_saved)} tokens de IA</strong>!
                </p>
              </div>
              <button onclick="document.getElementById('delta-sync-live-banner').classList.add('hidden')" class="px-2.5 py-1 rounded bg-slate-800 text-slate-300 text-xs">Fechar</button>
            </div>
          `;
        }
        renderVetorialView();
      }
    })
    .catch(() => {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<span>🔄</span> Executar Sincronização Delta Agora`;
      }
    });
}

function setVectorQuery(q) {
  const input = document.getElementById("vector-search-input");
  if (input) {
    input.value = q;
    runVectorSearch();
  }
}

function runVectorSearch() {
  const q = document.getElementById("vector-search-input")?.value || "glosa devolução RMEC março";
  const osFilter = document.getElementById("vector-search-os-filter")?.value || "";
  const container = document.getElementById("vector-search-results");
  if (!container) return;

  container.innerHTML = `<div class="p-4 text-xs font-mono text-slate-400">Consultando embeddings vetoriais em <code>db/contrato_9291.sqlite</code>...</div>`;

  fetch(`/api/vector-search?q=${encodeURIComponent(q)}&os=${encodeURIComponent(osFilter)}&limit=12`)
    .then((r) => r.json())
    .then((data) => {
      if (!data || !data.ok || !data.results || data.results.length === 0) {
        container.innerHTML = `<div class="p-4 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-400">Nenhum trecho encontrado para a consulta.</div>`;
        return;
      }

      container.innerHTML = data.results
        .map((r, i) => {
          const ent = r.entities || {};
          const brlTags = (ent.brl_values || []).slice(0, 4).map((v) => `<span class="px-1.5 py-0.5 rounded bg-emerald-950/60 border border-emerald-500/30 text-emerald-300 font-mono text-[10px]">R$ ${v}</span>`).join("");
          const dateTags = (ent.dates || []).slice(0, 3).map((d) => `<span class="px-1.5 py-0.5 rounded bg-slate-800 text-sky-300 font-mono text-[10px]">📅 ${d}</span>`).join("");
          const stepBadge = ent.detected_step ? `<span class="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono text-[10px] font-bold">Etapa ${ent.detected_step}</span>` : "";

          return `
            <div class="p-3.5 rounded-xl bg-slate-900/95 border border-slate-800 hover:border-sky-500/40 transition">
              <div class="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono text-[11px] font-bold">#${i + 1} • Score ${(r.similarity_score * 100).toFixed(1)}%</span>
                  <span class="font-mono text-xs font-bold text-white">${r.doc_id}</span>
                  <span class="font-mono text-xs text-emerald-400">Página ${r.page_number}</span>
                  ${stepBadge}
                  <span class="font-mono text-[10px] text-slate-500">SHA256: ${(r.page_sha256 || "").slice(0, 10)}</span>
                </div>
                <a href="../${r.rel_path}#page=${r.page_number}" target="_blank" class="px-2.5 py-1 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-mono text-[11px] font-semibold transition">
                  📄 Abrir PDF na Pág. ${r.page_number} ↗
                </a>
              </div>
              <div class="text-xs text-slate-200 font-medium leading-relaxed bg-slate-950/80 p-2.5 rounded-lg border border-slate-800/80 mb-2">
                <strong class="text-sky-400 font-mono text-[10px] uppercase mr-1">[Resumo IA em Cache]:</strong> ${r.ai_summary}
              </div>
              <div class="flex flex-wrap items-center gap-1.5">
                ${brlTags}
                ${dateTags}
              </div>
            </div>
          `;
        })
        .join("");
    })
    .catch(() => {
      container.innerHTML = `<div class="p-4 rounded-xl bg-slate-900 border border-slate-800 text-xs text-amber-300">Servidor Python API offline ou inacessível. Inicie <code>python server.py</code> na porta 8092 para habilitar a busca vetorial dinâmica.</div>`;
    });
}

// Exportação de Relatório Executivo (Impressão / PDF)
function exportAuditReport() {
  window.print();
}

// Expor funções necessárias no escopo global para handlers inline HTML
window.switchTab = switchTab;
window.filterConciliacao = filterConciliacao;
window.openOSDrawer = openOSDrawer;
window.closeOSDrawer = closeOSDrawer;
window.filterAuditoria = filterAuditoria;
window.exportAuditReport = exportAuditReport;
window.filterCronologiaStep = filterCronologiaStep;
window.toggleRMECBreakdown = toggleRMECBreakdown;
window.filterSteps1To5Table = filterSteps1To5Table;
window.renderChronologicalTimeline = renderChronologicalTimeline;
window.triggerDeltaSync = triggerDeltaSync;
window.setVectorQuery = setVectorQuery;
window.runVectorSearch = runVectorSearch;

