let etapaAtual = 1;
const TOTAL_ETAPAS = 3;

const SECOES_PADRAO = [
  "Introdução","Objetivos","Materiais e Reagentes",
  "Procedimentos","Resultados e Discussões","Conclusão"
];

let secoes = SECOES_PADRAO.map(t => ({ titulo: t, conteudo: "" }));
let draggingIdx = null;

document.addEventListener("DOMContentLoaded", () => {
  const anoInput = document.getElementById("ano");
  if (anoInput && !anoInput.value) anoInput.value = new Date().getFullYear();
  renderizarSecoes();
});

function salvarSecoesDoDOM() {
  secoes = secoes.map((s, i) => {
    const tEl = document.getElementById("secao-titulo-" + i);
    const cEl = document.getElementById("secao-conteudo-" + i);
    return { titulo: tEl ? tEl.value : s.titulo, conteudo: cEl ? cEl.value : s.conteudo };
  });
}

function proximaEtapa(num) {
  salvarSecoesDoDOM();
  if (num > etapaAtual && !validarEtapa(etapaAtual)) return;
  document.getElementById("etapa-" + etapaAtual).classList.add("oculto");
  document.getElementById("etapa-" + num).classList.remove("oculto");
  for (let i = 1; i <= TOTAL_ETAPAS; i++) {
    const step = document.querySelector(".progress-step[data-step='" + i + "']");
    if (!step) continue;
    step.classList.remove("active", "concluido");
    if (i < num) step.classList.add("concluido");
    else if (i === num) step.classList.add("active");
  }
  etapaAtual = num;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function validarEtapa(num) {
  if (num === 1) {
    const titulo = document.getElementById("titulo").value.trim();
    const autor  = document.getElementById("autor").value.trim();
    if (!titulo) { mostrarToast("Preencha o título do trabalho", "erro"); focar("titulo"); return false; }
    if (!autor)  { mostrarToast("Preencha pelo menos um autor", "erro");  focar("autor");  return false; }
  }
  return true;
}

function focar(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.focus();
  el.scrollIntoView({ behavior: "smooth", block: "center" });
}

function renderizarSecoes() {
  const container = document.getElementById("secoes-container");
  if (!container) return;
  let html = "";
  for (let i = 0; i < secoes.length; i++) {
    const s = secoes[i];
    const titEsc  = (s.titulo   || "").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
    const contEsc = (s.conteudo || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
    const statusClass = s.conteudo.trim() ? "tem-conteudo" : "sem-conteudo";
    const statusTxt   = s.conteudo.trim() ? "✓ Será incluída no PDF" : "○ Em branco — não será incluída";
    html +=
      '<div class="secao-card" id="secao-card-' + i + '" draggable="true"' +
      ' ondragstart="dragStart(' + i + ')" ondragover="dragOver(event,' + i + ')"' +
      ' ondrop="dragDrop(event,' + i + ')" ondragend="dragEnd()">' +
      '<div class="secao-card-header">' +
      '<span class="drag-handle">⠿</span>' +
      '<input type="text" class="secao-titulo-input" id="secao-titulo-' + i + '"' +
      ' value="' + titEsc + '" placeholder="Nome da seção"' +
      ' oninput="atualizarTituloLive(' + i + ', this.value)" />' +
      '<button type="button" class="secao-remover" onclick="removerSecao(' + i + ')">✕</button>' +
      '</div>' +
      '<textarea class="secao-textarea" id="secao-conteudo-' + i + '" rows="6"' +
      ' placeholder="Digite o conteúdo. Separe parágrafos com linha em branco."' +
      ' oninput="atualizarConteudoLive(' + i + ', this.value)">' + contEsc + '</textarea>' +
      '<div class="secao-status ' + statusClass + '" id="secao-status-' + i + '">' + statusTxt + '</div>' +
      '</div>';
  }
  container.innerHTML = html;
}

function atualizarTituloLive(i, val)   { secoes[i].titulo   = val; }
function atualizarConteudoLive(i, val) {
  secoes[i].conteudo = val;
  const st = document.getElementById("secao-status-" + i);
  if (st) {
    st.className   = "secao-status " + (val.trim() ? "tem-conteudo" : "sem-conteudo");
    st.textContent = val.trim() ? "✓ Será incluída no PDF" : "○ Em branco — não será incluída";
  }
}

function adicionarSecao() {
  salvarSecoesDoDOM();
  secoes.push({ titulo: "Nova seção", conteudo: "" });
  renderizarSecoes();
  const idx = secoes.length - 1;
  setTimeout(() => {
    const input = document.getElementById("secao-titulo-" + idx);
    if (input) { input.focus(); input.select(); }
    const card = document.getElementById("secao-card-" + idx);
    if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });
  }, 80);
}

function removerSecao(i) {
  salvarSecoesDoDOM();
  if (secoes.length === 1) { mostrarToast("Mantenha pelo menos uma seção", "erro"); return; }
  secoes.splice(i, 1);
  renderizarSecoes();
}

function dragStart(i) { draggingIdx = i; }
function dragEnd()    { draggingIdx = null; document.querySelectorAll(".secao-card").forEach(c => c.classList.remove("drag-over")); }
function dragOver(e, i) {
  e.preventDefault();
  document.querySelectorAll(".secao-card").forEach(c => c.classList.remove("drag-over"));
  if (i !== draggingIdx) { const c = document.getElementById("secao-card-" + i); if (c) c.classList.add("drag-over"); }
}
function dragDrop(e, i) {
  e.preventDefault();
  if (draggingIdx === null || draggingIdx === i) return;
  salvarSecoesDoDOM();
  const item = secoes.splice(draggingIdx, 1)[0];
  secoes.splice(i, 0, item);
  renderizarSecoes();
}

async function uploadLogo(input) {
  const file = input.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("logo", file);
  try {
    const resp = await fetch("/upload-logo", { method: "POST", body: fd });
    const data = await resp.json();
    if (data.sucesso) {
      const reader = new FileReader();
      reader.onload = e => {
        document.getElementById("logo-img").src = e.target.result;
        document.getElementById("logo-placeholder").classList.add("oculto");
        document.getElementById("logo-preview").classList.remove("oculto");
      };
      reader.readAsDataURL(file);
      mostrarToast("Logo enviado!", "sucesso");
    } else { mostrarToast(data.erro || "Erro", "erro"); }
  } catch { mostrarToast("Erro de conexão", "erro"); }
  input.value = "";
}

async function removerLogo(e) {
  e.stopPropagation();
  try { await fetch("/remover-logo", { method: "POST" }); } catch {}
  document.getElementById("logo-placeholder").classList.remove("oculto");
  document.getElementById("logo-preview").classList.add("oculto");
  document.getElementById("logo-img").src = "";
}

let _barraTimer = null;

function _iniciarBarra() {
  const wrap  = document.getElementById("barra-progresso-wrap");
  const fill  = document.getElementById("barra-fill");
  const pct   = document.getElementById("barra-pct");
  const label = document.getElementById("barra-label");
  if (!wrap) return;
  wrap.classList.remove("oculto");
  fill.style.width = "0%";
  pct.textContent  = "0%";
  label.textContent = "Preparando...";

  const etapas = [
    { w: 20,  t: 300,  msg: "Estruturando o documento..." },
    { w: 45,  t: 800,  msg: "Aplicando formatação ABNT..." },
    { w: 70,  t: 1500, msg: "Gerando capa e seções..." },
    { w: 90,  t: 2400, msg: "Finalizando PDF..." },
    { w: 99,  t: 3200, msg: "Quase pronto..." },
  ];

  etapas.forEach(function(e) {
    _barraTimer = setTimeout(function() {
      fill.style.width  = e.w + "%";
      pct.textContent   = e.w + "%";
      label.textContent = e.msg;
    }, e.t);
  });
}

function _finalizarBarra() {
  clearTimeout(_barraTimer);
  const fill  = document.getElementById("barra-fill");
  const pct   = document.getElementById("barra-pct");
  const label = document.getElementById("barra-label");
  if (!fill) return;
  fill.style.width  = "100%";
  pct.textContent   = "100%";
  label.textContent = "PDF gerado!";
}

function _resetarBarra() {
  const wrap = document.getElementById("barra-progresso-wrap");
  const fill = document.getElementById("barra-fill");
  if (wrap) wrap.classList.add("oculto");
  if (fill) fill.style.width = "0%";
}

async function gerarPDF() {
  if (!PODE_GERAR) { mostrarToast("Você já usou sua geração gratuita", "erro"); return; }
  salvarSecoesDoDOM();

  const btnTexto   = document.getElementById("btn-texto");
  const btnLoading = document.getElementById("btn-loading");
  const btnGerar   = document.getElementById("btn-gerar");
  btnTexto.classList.add("oculto");
  btnLoading.classList.remove("oculto");
  btnGerar.disabled = true;
  _iniciarBarra();

  const dados = {
    titulo:         document.getElementById("titulo").value.trim(),
    autor:          document.getElementById("autor").value.trim(),
    instituicao:    document.getElementById("instituicao").value.trim(),
    campus:         document.getElementById("campus").value.trim(),
    curso:          document.getElementById("curso").value.trim(),
    disciplina:     document.getElementById("disciplina").value.trim(),
    turma:          document.getElementById("turma").value.trim(),
    orientador:     document.getElementById("orientador").value.trim(),
    tipo_trabalho:  document.getElementById("tipo_trabalho").value,
    cidade:         document.getElementById("cidade").value.trim(),
    mes:            document.getElementById("mes").value.trim(),
    ano:            document.getElementById("ano").value.trim(),
    resumo:         document.getElementById("resumo").value.trim(),
    palavras_chave: document.getElementById("palavras_chave").value.trim(),
    referencias:    document.getElementById("referencias").value.trim(),
    secoes:         secoes
  };

  try {
    const resp = await fetch("/gerar-pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados)
    });
    const data = await resp.json();

    if (resp.status === 401) { window.location.href = "/"; return; }
    if (resp.status === 403) { mostrarToast("Limite atingido. Faça upgrade!", "erro"); return; }
    if (!resp.ok || data.erro) { mostrarToast(data.erro || "Erro ao gerar PDF.", "erro"); _resetarBarra(); return; }

    _finalizarBarra();
    setTimeout(function() {
      document.getElementById("link-download").href = "/download/" + data.arquivo;
      document.getElementById("resultado").classList.remove("oculto");
      document.getElementById("resultado").scrollIntoView({ behavior: "smooth", block: "center" });
      mostrarToast("PDF gerado com sucesso!", "sucesso");
      btnGerar.disabled = true;
    }, 400);

  } catch {
    mostrarToast("Erro de conexão.", "erro");
    _resetarBarra();
  }
  finally {
    btnTexto.classList.remove("oculto");
    btnLoading.classList.add("oculto");
  }
}

let toastTimer = null;
function mostrarToast(msg, tipo) {
  tipo = tipo || "";
  let toast = document.getElementById("toast-global");
  if (!toast) { toast = document.createElement("div"); toast.id = "toast-global"; toast.className = "toast"; document.body.appendChild(toast); }
  toast.textContent = msg;
  toast.className = "toast " + tipo;
  setTimeout(() => toast.classList.add("show"), 10);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3200);
}
