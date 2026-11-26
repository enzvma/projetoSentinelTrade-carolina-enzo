// Interface do SentinelTrade. Fala só com o BFF (/bff/...): nunca vê o token de acesso.
// Todo texto vindo do servidor entra na página por textContent (nunca innerHTML).
"use strict";

const estado = { csrf: "", perfil: "", painel: null, ordemAberta: null, chaveOrdem: null, chaveAlteracao: null, timer: null };
const $ = (id) => document.getElementById(id);
const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const hora = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const dataHora = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "medium" });
const PERFIS = { INVESTIDOR: "Investidor", ADMINISTRADOR: "Administrador", ANALISTA_RISCO: "Analista de risco", AUDITOR: "Auditor" };
const PASSOS = ["CRIADA", "VALIDADA", "ENVIADA", "EXECUTADA"];
const NOMES = { CRIADA: "Criada", VALIDADA: "Validada", ENVIADA: "Na corretora", PARCIALMENTE_EXECUTADA: "Executada em parte",
  EXECUTADA: "Executada", REJEITADA: "Rejeitada", CANCELADA: "Cancelada" };

// ---- utilitários --------------------------------------------------------------------------
function el(tag, props = {}, ...filhos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k === "texto") n.textContent = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const f of filhos) if (f !== null && f !== undefined) n.append(f);
  return n;
}
const dinheiro = (v) => (v === null || v === undefined ? "–" : moeda.format(Number(v)));
const decimal = (texto) => String(texto || "").trim().replace(/\./g, "").replace(",", ".");
const chave = () => crypto.randomUUID();

function avisar(texto, tipo = "") {
  const a = el("div", { class: `aviso ${tipo}`, texto });
  $("avisos").append(a);
  setTimeout(() => a.remove(), tipo === "erro" ? 7000 : 4500);
}

async function bff(metodo, caminho, corpo) {
  const opcoes = { method: metodo, headers: { "X-CSRF-Token": estado.csrf }, credentials: "same-origin" };
  if (corpo !== undefined) {
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo);
  }
  let r;
  try {
    r = await fetch(caminho, opcoes);
  } catch {
    throw new Error("Sem conexão com o servidor. Confira se o BFF está em execução.");
  }
  const dados = await r.json().catch(() => ({}));
  if (r.status === 401 && estado.perfil) { sair(false); }
  if (!r.ok) throw new Error(dados.mensagem || "Não foi possível concluir a operação.");
  return dados;
}

async function comBotao(form, acao) {
  const botao = form.querySelector("button[type=submit]");
  botao.disabled = true;
  try { await acao(); } catch (e) { avisar(e.message, "erro"); } finally { botao.disabled = false; }
}

function linhaVazia(tbody, colunas, texto) {
  tbody.replaceChildren(el("tr", { class: "vazio" }, el("td", { colspan: String(colunas), texto })));
}

// ---- sessão e entrada --------------------------------------------------------------------
async function iniciar() {
  const s = await bff("GET", "/bff/sessao");
  estado.csrf = s.csrf;
  if (s.autenticado) entrar(s); else mostrarEntrada();
}

function mostrarEntrada() {
  for (const sec of document.querySelectorAll("main > section")) sec.hidden = true;
  $("tela-entrar").hidden = false;
  $("form-login").hidden = false;
  $("form-mfa").hidden = true;
  $("usuario").hidden = true;
  $("pregao").hidden = true;
  $("form-login").email.focus();
}

function entrar(s) {
  estado.perfil = s.perfil;
  $("tela-entrar").hidden = true;
  $("usuario").hidden = false;
  $("usuario-nome").textContent = s.nome;
  $("usuario-perfil").textContent = PERFIS[s.perfil] || s.perfil;
  $(`tela-${s.perfil}`).hidden = false;
  if (s.perfil === "ADMINISTRADOR" || s.perfil === "ANALISTA_RISCO") $("tela-GESTAO").hidden = false;
  atualizar();
  clearInterval(estado.timer);
  estado.timer = setInterval(() => { if (!document.hidden) atualizar(); }, 3000);
}

async function sair(avisarServidor = true) {
  clearInterval(estado.timer);
  if (avisarServidor) await bff("POST", "/bff/sair").catch(() => {});
  estado.perfil = "";
  estado.painel = null;
  if ($("detalhe").open) $("detalhe").close();
  await iniciar();
}

$("form-login").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = ev.target;
  comBotao(f, async () => {
    await bff("POST", "/bff/login", { email: f.email.value.trim(), senha: f.senha.value });
    f.senha.value = "";
    f.hidden = true;
    $("form-mfa").hidden = false;
    $("form-mfa").codigo.value = "";
    $("form-mfa").codigo.focus();
  });
});

$("form-mfa").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = ev.target;
  comBotao(f, async () => {
    const s = await bff("POST", "/bff/mfa", { codigo: f.codigo.value.trim() });
    f.codigo.value = "";
    entrar(s);
  });
});
$("voltar-login").addEventListener("click", mostrarEntrada);
$("sair").addEventListener("click", () => sair());

// ---- painel ------------------------------------------------------------------------------
async function atualizar() {
  try {
    const p = await bff("GET", "/bff/painel");
    estado.painel = p;
    mostrarPregao(p.mercado);
    if (p.perfil === "INVESTIDOR") desenharInvestidor(p);
    if (p.perfil === "ADMINISTRADOR") desenharAdmin(p);
    if (p.perfil === "ADMINISTRADOR" || p.perfil === "ANALISTA_RISCO") desenharGestao(p);
    if (p.perfil === "AUDITOR") desenharAuditor(p);
    if ($("detalhe").open && estado.ordemAberta) abrirOrdem(estado.ordemAberta, false);
  } catch (e) {
    if (estado.perfil) avisar(e.message, "erro");
  }
}

function mostrarPregao(m) {
  const p = m.parametros;
  const aberto = m.aberto;
  $("pregao").hidden = false;
  $("pregao").classList.toggle("aberto", aberto);
  $("pregao").textContent = aberto ? `Pregão aberto até ${p.PREGAO_FECHAMENTO}` : `Pregão fechado (abre às ${p.PREGAO_ABERTURA})`;
}

function situacao(o) {
  const feitos = { CRIADA: 1, VALIDADA: 2, ENVIADA: 3, PARCIALMENTE_EXECUTADA: 3, EXECUTADA: 4, REJEITADA: 4, CANCELADA: 4 }[o.estado];
  const mini = el("span", { class: "mini", "aria-hidden": "true" });
  for (let i = 0; i < 4; i++) mini.append(el("i", { class: i < feitos ? "feito" : "" }));
  return el("span", { class: `situacao e-${o.estado}` }, mini, el("span", { class: "situacao-txt", texto: o.estado_texto }));
}

function linhaOrdem(o, comConta) {
  return el("tr", { tabindex: "0", onclick: () => abrirOrdem(o.id), onkeydown: (e) => { if (e.key === "Enter") abrirOrdem(o.id); } },
    el("td", { texto: `#${o.id}` }),
    comConta ? el("td", { texto: `#${o.conta_id}` }) : null,
    el("td", { texto: o.ticker }),
    el("td", { class: `lado-txt-${o.lado}`, texto: o.lado === "COMPRA" ? "Compra" : "Venda" }),
    el("td", { class: "num", texto: `${o.quantidade_executada} de ${o.quantidade}` }),
    el("td", { class: "num", texto: o.preco ? dinheiro(o.preco) : "A mercado" }),
    el("td", {}, situacao(o)),
    el("td", { texto: hora.format(new Date(o.atualizada_em)) }));
}

function desenharInvestidor(p) {
  $("saldo-disponivel").textContent = dinheiro(p.saldo.disponivel);
  $("saldo-bloqueado").textContent = dinheiro(p.saldo.bloqueado);
  $("saldo-total").textContent = dinheiro(p.saldo.total);

  const sel = $("form-ordem").ticker;
  const atual = sel.value;
  const negociaveis = p.cotacoes.filter((c) => c.negociavel);
  if (sel.options.length !== negociaveis.length) {
    sel.replaceChildren(...negociaveis.map((c) => el("option", { value: c.ticker, texto: `${c.ticker} – ${c.nome}` })));
    if (atual) sel.value = atual;
  }

  $("cotacoes").replaceChildren(...p.cotacoes.map((c) => {
    const v = c.variacao_percentual === null ? null : Number(c.variacao_percentual);
    return el("tr", { tabindex: "0", onclick: () => escolherAtivo(c), onkeydown: (e) => { if (e.key === "Enter") escolherAtivo(c); } },
      el("td", {}, c.ticker, el("span", { class: "ativo-nome", texto: c.negociavel ? c.nome : "Suspenso para negociação" })),
      el("td", { class: "num" }, dinheiro(c.preco), c.desatualizada ? el("span", { class: "ativo-nome desatualizada", texto: "desatualizada" }) : null),
      el("td", { class: `num ${v > 0 ? "alta" : v < 0 ? "baixa" : ""}`, texto: v === null ? "–" : `${v > 0 ? "+" : ""}${v.toFixed(2).replace(".", ",")}%` }));
  }));

  if (p.ordens.length) $("ordens").replaceChildren(...p.ordens.map((o) => linhaOrdem(o, false)));
  else linhaVazia($("ordens"), 7, "Nenhuma ordem ainda. Use o formulário Nova ordem para começar.");

  if (p.carteira.length) {
    $("carteira").replaceChildren(...p.carteira.map((c) => el("tr", {},
      el("td", {}, c.ticker, el("span", { class: "ativo-nome", texto: c.nome })),
      el("td", { class: "num", texto: c.quantidade_bloqueada ? `${c.quantidade_disponivel} (+${c.quantidade_bloqueada} em ordens)` : String(c.quantidade_disponivel) }),
      el("td", { class: "num", texto: dinheiro(c.preco_medio) }),
      el("td", { class: "num", texto: dinheiro(c.preco_atual) }),
      el("td", { class: "num", texto: dinheiro(c.valor_estimado) }))));
  } else linhaVazia($("carteira"), 5, "Sua carteira está vazia. As compras executadas aparecem aqui.");
  estimar();
}

// ---- nova ordem --------------------------------------------------------------------------
const formOrdem = $("form-ordem");

function escolherAtivo(c) {
  if (!c.negociavel) return avisar(`${c.ticker} está suspenso para negociação.`, "erro");
  formOrdem.ticker.value = c.ticker;
  if (formOrdem.tipo.value === "LIMITADA" && c.preco) formOrdem.preco.value = Number(c.preco).toFixed(2).replace(".", ",");
  estimar();
  formOrdem.quantidade.focus();
}

function estimar() {
  const p = estado.painel;
  if (!p || p.perfil !== "INVESTIDOR") return;
  const lado = formOrdem.lado.value;
  formOrdem.dataset.lado = lado;
  const limitada = formOrdem.tipo.value === "LIMITADA";
  $("campo-preco").hidden = !limitada;
  $("botao-ordem").textContent = lado === "COMPRA" ? "Enviar ordem de compra" : "Enviar ordem de venda";
  const cot = p.cotacoes.find((c) => c.ticker === formOrdem.ticker.value);
  const qtd = Number(formOrdem.quantidade.value);
  const preco = limitada ? Number(decimal(formOrdem.preco.value)) : Number(cot && cot.preco);
  if (!qtd || !preco) { $("estimativa").textContent = ""; return; }
  const valor = qtd * preco;
  const taxa = Math.ceil(valor * Number(p.mercado.parametros.TAXA_OPERACAO_BPS)) / 10000;
  const prefixo = limitada ? "" : "aprox. ";
  $("estimativa").textContent = lado === "COMPRA"
    ? `Total ${prefixo}${dinheiro(valor + taxa)} (${dinheiro(valor)} + taxa ${dinheiro(taxa)})`
    : `Você recebe ${prefixo}${dinheiro(valor - taxa)} (${dinheiro(valor)} − taxa ${dinheiro(taxa)})`;
}
formOrdem.addEventListener("input", () => { estado.chaveOrdem = null; estimar(); });

formOrdem.addEventListener("submit", (ev) => {
  ev.preventDefault();
  comBotao(formOrdem, async () => {
    // A chave é gerada uma vez por ordem: se a rede falhar e a pessoa clicar de novo, a API reconhece a repetição.
    estado.chaveOrdem = estado.chaveOrdem || chave();
    const corpo = { ticker: formOrdem.ticker.value, lado: formOrdem.lado.value, tipo: formOrdem.tipo.value,
      quantidade: Number(formOrdem.quantidade.value), chave_idempotencia: estado.chaveOrdem };
    if (corpo.tipo === "LIMITADA") corpo.preco = decimal(formOrdem.preco.value);
    const o = await bff("POST", "/bff/ordens", corpo);
    estado.chaveOrdem = null;
    avisar(o.mensagem, o.estado === "REJEITADA" ? "erro" : "ok");
    atualizar();
  });
});

// ---- detalhe da ordem ---------------------------------------------------------------------
async function abrirOrdem(id, abrir = true) {
  let o;
  try { o = await bff("GET", `/bff/ordens/${id}`); } catch (e) { return avisar(e.message, "erro"); }
  if (abrir && estado.ordemAberta !== id) { estado.chaveAlteracao = null; $("form-alterar").reset(); }
  estado.ordemAberta = id;
  $("detalhe-titulo").textContent = `Ordem #${o.id}: ${o.lado === "COMPRA" ? "compra" : "venda"} de ${o.ticker}`;
  const origem = o.ordem_origem_id ? `, substitui a ordem #${o.ordem_origem_id}` : "";
  $("detalhe-resumo").textContent = `${o.quantidade} unidades, ${o.preco ? `limitada a ${dinheiro(o.preco)}` : "a mercado"}, ${o.quantidade_executada} executadas${origem}.`;

  // Trilho: o caminho que a ordem percorreu na máquina de estados.
  const quando = {};
  for (const h of o.historico) quando[h.estado_novo] = h.data_hora;
  let passos = PASSOS.slice();
  if (o.estado === "REJEITADA" || o.estado === "CANCELADA") {
    const ultimo = Math.max(0, ...PASSOS.map((p, i) => (quando[p] ? i : 0)));
    passos = PASSOS.slice(0, ultimo + 1).concat(o.estado);
  } else if (o.estado === "PARCIALMENTE_EXECUTADA") {
    passos = ["CRIADA", "VALIDADA", "ENVIADA", "PARCIALMENTE_EXECUTADA", "EXECUTADA"];
  }
  const trilho = $("trilho");
  trilho.style.setProperty("--passos", String(passos.length));
  trilho.dataset.fim = o.estado;
  const indiceAtual = passos.indexOf(o.estado);
  trilho.replaceChildren(...passos.map((p, i) => el("li", { class: `${i <= indiceAtual ? "feito" : ""} ${i === indiceAtual ? "atual" : ""}` },
    NOMES[p], el("span", { class: "hora", texto: quando[p] ? hora.format(new Date(quando[p])) : " " }))));

  $("detalhe-motivo").hidden = !o.motivo_texto;
  $("detalhe-motivo").textContent = o.motivo_texto || "";
  $("historico").replaceChildren(...o.historico.map((h) => el("li", {},
    el("span", { texto: `${h.estado_texto} (por ${h.origem_texto})` }), el("span", { texto: dataHora.format(new Date(h.data_hora)) }))));

  const dono = estado.perfil === "INVESTIDOR";
  $("acoes").hidden = !dono || !(o.pode_cancelar || o.pode_alterar);
  $("cancelar-ordem").hidden = !o.pode_cancelar;
  $("form-alterar").hidden = !o.pode_alterar;
  $("alterar-preco").hidden = o.tipo !== "LIMITADA";
  if (abrir && !$("detalhe").open) $("detalhe").showModal();
}

$("fechar-detalhe").addEventListener("click", () => $("detalhe").close());
$("detalhe").addEventListener("close", () => { estado.ordemAberta = null; });

$("cancelar-ordem").addEventListener("click", async (ev) => {
  const botao = ev.target;
  botao.disabled = true;
  try {
    const r = await bff("POST", `/bff/ordens/${estado.ordemAberta}/cancelar`);
    avisar(r.mensagem, "ok");
    atualizar();
  } catch (e) { avisar(e.message, "erro"); } finally { botao.disabled = false; }
});

$("form-alterar").addEventListener("input", () => { estado.chaveAlteracao = null; });
$("form-alterar").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = ev.target;
  comBotao(f, async () => {
    estado.chaveAlteracao = estado.chaveAlteracao || chave();
    const corpo = { chave_idempotencia: estado.chaveAlteracao };
    if (f.quantidade.value) corpo.quantidade = Number(f.quantidade.value);
    if (!$("alterar-preco").hidden && f.preco.value) corpo.preco = decimal(f.preco.value);
    const nova = await bff("POST", `/bff/ordens/${estado.ordemAberta}/alterar`, corpo);
    estado.chaveAlteracao = null;
    avisar(nova.mensagem, "ok");
    f.reset();
    abrirOrdem(nova.id);
    atualizar();
  });
});

// ---- administrador -----------------------------------------------------------------------
function desenharAdmin(p) {
  const f = $("form-pregao");
  if (!f.contains(document.activeElement)) {
    for (const [k, v] of Object.entries(p.mercado.parametros)) if (f.elements[k]) f.elements[k].value = v;
  }
  $("ativos").replaceChildren(...p.cotacoes.map((c) => el("tr", {},
    el("td", {}, c.ticker, el("span", { class: "ativo-nome", texto: c.nome })),
    el("td", { class: "num", texto: dinheiro(c.preco) }),
    el("td", {},
      el("span", { class: `chave ${c.negociavel ? "" : "off"}`, texto: c.negociavel ? "Liberado" : "Suspenso" }),
      el("button", { class: "botao-texto", type: "button", texto: c.negociavel ? "Suspender" : "Liberar",
        onclick: (e) => alternarAtivo(e.target, c) })))));
}

async function alternarAtivo(botao, c) {
  botao.disabled = true;
  try {
    const r = await bff("POST", `/bff/admin/ativos/${c.ticker}`, { negociavel: !c.negociavel });
    avisar(r.mensagem, "ok");
    atualizar();
  } catch (e) { avisar(e.message, "erro"); botao.disabled = false; }
}

$("form-pregao").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = ev.target;
  comBotao(f, async () => {
    const atuais = estado.painel.mercado.parametros;
    // Abertura antes de fechamento é validado no servidor; a ordem dos envios evita estados intermediários inválidos.
    const chaves = ["PREGAO_FUSO", "PREGAO_DIAS", "FAIXA_PRECO_PCT", "TAXA_OPERACAO_BPS", "COTACAO_IDADE_MAX_S"];
    const novaAbertura = f.PREGAO_ABERTURA.value;
    chaves.push(...(novaAbertura < atuais.PREGAO_ABERTURA ? ["PREGAO_ABERTURA", "PREGAO_FECHAMENTO"] : ["PREGAO_FECHAMENTO", "PREGAO_ABERTURA"]));
    let alterados = 0;
    for (const k of chaves) {
      const valor = String(f.elements[k].value).trim();
      if (valor === atuais[k]) continue;
      await bff("PUT", `/bff/admin/parametros/${k}`, { valor });
      alterados++;
    }
    avisar(alterados ? "Parâmetros salvos." : "Nada mudou nos parâmetros.", "ok");
    atualizar();
  });
});

$("form-usuario").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = ev.target;
  comBotao(f, async () => {
    const r = await bff("POST", "/bff/admin/usuarios", { nome: f.nome.value.trim(), email: f.email.value.trim(),
      senha: f.senha.value, perfil: f.perfil.value, saldo_inicial: decimal(f.saldo_inicial.value || "0") });
    f.reset();
    $("uri-mfa-texto").textContent = r.otpauth_uri;
    $("uri-mfa").hidden = false;
    avisar(r.mensagem, "ok");
  });
});
$("copiar-uri").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText($("uri-mfa-texto").textContent); avisar("Chave copiada.", "ok"); }
  catch { avisar("Não foi possível copiar. Selecione o texto e copie manualmente.", "erro"); }
});

$("form-credito").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = ev.target;
  comBotao(f, async () => {
    const r = await bff("POST", `/bff/admin/contas/${Number(f.conta_id.value)}/creditos`, { valor: decimal(f.valor.value) });
    f.reset();
    avisar(r.mensagem, "ok");
  });
});

// ---- gestão: administrador e analista de risco -------------------------------------------------
function desenharGestao(p) {
  const filtro = $("filtro-ordens").value;
  const ordens = p.ordens.filter((o) => !filtro || (filtro === "abertas" ? o.pode_cancelar : o.estado === filtro));
  if (ordens.length) $("ordens-gestao").replaceChildren(...ordens.map((o) => linhaOrdem(o, true)));
  else linhaVazia($("ordens-gestao"), 8, "Nenhuma ordem com esse filtro.");

  const contagem = {};
  for (const o of p.ordens) if (o.estado === "REJEITADA" && o.motivo_texto) contagem[o.motivo_texto] = (contagem[o.motivo_texto] || 0) + 1;
  const itens = Object.entries(contagem).sort((a, b) => b[1] - a[1]);
  $("rejeicoes").replaceChildren(...(itens.length
    ? itens.map(([motivo, n]) => el("li", {}, el("span", { texto: motivo }), el("strong", { texto: String(n) })))
    : [el("li", {}, el("span", { texto: "Nenhuma rejeição entre as ordens recentes." }))]));
}
$("filtro-ordens").addEventListener("change", () => estado.painel && desenharGestao(estado.painel));

$("form-limite").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = ev.target;
  comBotao(f, async () => {
    const r = await bff("PUT", `/bff/risco/contas/${Number(f.conta_id.value)}/limites`,
      { valor_maximo_ordem: decimal(f.valor_maximo_ordem.value), exposicao_maxima: decimal(f.exposicao_maxima.value) });
    avisar(r.mensagem, "ok");
  });
});

// ---- auditor -----------------------------------------------------------------------------
function desenharAuditor(p) {
  if (!p.auditoria.length) return linhaVazia($("auditoria"), 7, "A trilha está vazia.");
  $("auditoria").replaceChildren(...p.auditoria.map((r) => el("tr", {},
    el("td", { texto: `#${r.id}` }),
    el("td", { texto: dataHora.format(new Date(r.data_hora)) }),
    el("td", { texto: r.ator }),
    el("td", { texto: r.acao }),
    el("td", { texto: r.entidade_id ? `${r.entidade} #${r.entidade_id}` : r.entidade }),
    el("td", { class: r.resultado === "SUCESSO" ? "alta" : "baixa", texto: r.resultado }),
    el("td", { class: "hash", title: r.hash, texto: `${r.hash.slice(0, 10)}…` }))));
}

$("verificar").addEventListener("click", async (ev) => {
  ev.target.disabled = true;
  try {
    const r = await bff("GET", "/bff/auditoria/verificacao");
    $("resultado-verificacao").textContent = r.mensagem;
    $("resultado-verificacao").className = `resultado ${r.integra ? "ok" : "falha"}`;
  } catch (e) { avisar(e.message, "erro"); } finally { ev.target.disabled = false; }
});

iniciar().catch((e) => avisar(e.message, "erro"));
