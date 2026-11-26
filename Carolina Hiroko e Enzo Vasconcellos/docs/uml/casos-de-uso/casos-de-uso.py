"""Fonte editável do diagrama de casos de uso do SentinelTrade.

Para alterar o diagrama, edite NOMES (casos de uso), PAC_A (pacotes), ACT (atores),
ASSOC (associações ator-caso de uso), INCLUDE e EXTEND, e gere a imagem de novo:

    pip install matplotlib
    python docs/uml/casos-de-uso/casos-de-uso.py

A imagem é gravada em docs/uml/casos-de-uso/casos-de-uso.png.
"""
import math, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch

W, H, GAP = 4.4, 1.15, 1.35
XA, XB, XC, XL, XR = 9.0, 17.2, 24.6, 1.8, 31.2

NOMES = {
 "01": "Autenticar-se com MFA", "02": "Validar segundo fator",
 "03": "Gerenciar usuários\ne investidores", "04": "Gerenciar ativos", "05": "Gerenciar limites de risco",
 "06": "Consultar saldo", "07": "Consultar carteira", "08": "Consultar cotação",
 "20": "Consultar status da ordem", "21": "Consultar histórico\nde operações",
 "10": "Enviar ordem de compra", "11": "Enviar ordem de venda", "12": "Alterar ordem", "13": "Cancelar ordem",
 "22": "Consultar trilha\nde auditoria",
 "09": "Receber cotações", "14": "Validar ordem", "15": "Verificar saldo\nou posição",
 "16": "Transmitir ordem\nà corretora", "17": "Ativar modo restrito", "18": "Enviar notificação",
 "19": "Registrar auditoria",
}
PAC_A = [("Acesso", "#dbeafe", ["01"]),
         ("Administração", "#dcfce7", ["03", "04", "05"]),
         ("Consultas", "#ffedd5", ["06", "07", "08", "20", "21"]),
         ("Negociação", "#ede9fe", ["10", "11", "12", "13"]),
         ("Auditoria (consulta)", "#e5e7eb", ["22"])]

pos, boxes, y = {}, [], 0.0
for nome, cor, ids in PAC_A:
    top = y; y -= 1.0
    for k in ids:
        pos[k] = (XA, y); y -= GAP
    y += GAP - 0.85
    boxes.append((nome, cor, XA, top + 0.25, y)); y -= 0.55

Y = lambda k: pos[k][1]
pos["02"] = (XB, Y("01"))
pos["09"] = (XB, Y("08"))
pos["14"] = (XB, Y("10") + 0.4)
pos["15"] = (XC, Y("10") + 0.4)
pos["16"] = (XB, Y("12") - 0.3)
pos["17"] = (XC, Y("12") + 0.95)
pos["18"] = (XC, Y("13") - 0.9)
pos["19"] = (XB, Y("22") - 1.4)
NUC = [("Autenticação", "#dbeafe", ["02"]), ("Cotações", "#ffedd5", ["09"]),
       ("Validação", "#fef9c3", ["14", "15"]), ("Transmissão", "#fef9c3", ["16"]),
       ("Resiliência", "#fce7f3", ["17"]), ("Notificação", "#dbeafe", ["18"]),
       ("Auditoria (registro)", "#e5e7eb", ["19"])]
for nome, cor, ids in NUC:
    xs = [pos[k][0] for k in ids]; ys = [pos[k][1] for k in ids]
    boxes.append((nome, cor, (min(xs), max(xs)), max(ys) + 1.1, min(ys) - 0.75))

ACT = {"ADM": (XL, Y("04"), "Administrador", False),
       "RSK": (XL, (Y("05") + Y("06")) / 2 - 0.3, "Analista de Risco", False),
       "INV": (XL, Y("10") + 0.6, "Investidor", False),
       "AUD": (XL, Y("22"), "Auditor", False),
       "QP": (XR, Y("09"), "Provedor de\nCotações", True),
       "EXC": (XR, Y("16"), "Corretora/Bolsa\nSimulada", True),
       "NTF": (XR, Y("18") - 1.15, "Serviço de\nNotificação", True),
       "SAU": (XR, Y("19") - 1.6, "Serviço de\nAuditoria", True)}
ASSOC = {"INV": ["01", "06", "07", "08", "20", "21", "10", "11", "12", "13"],
         "ADM": ["01", "03", "04", "05"], "RSK": ["01", "05", "20"], "AUD": ["01", "22"],
         "QP": ["09"], "EXC": ["16"], "NTF": ["18"], "SAU": ["19"]}
INCLUDE = [("01", "02"), ("10", "14"), ("11", "14"), ("12", "14"), ("14", "15"),
           ("10", "16"), ("11", "16"), ("12", "16"), ("13", "16"), ("16", "18"), ("13", "18"),
           ("10", "19"), ("11", "19"), ("13", "19"), ("16", "19")]
EXTEND = [("17", "16")]

ymin = min(b[4] for b in boxes) - 3.4
fig, ax = plt.subplots(figsize=(17, 18.5))
ax.set_xlim(-0.6, 34); ax.set_ylim(ymin, 3.4); ax.axis("off"); ax.set_aspect("equal")
ax.add_patch(FancyBboxPatch((5.9, ymin + 1.3), 21.8, 3.0 - (ymin + 1.3), boxstyle="round,pad=0.05,rounding_size=0.3",
                            fc="white", ec="#111", lw=2.0, zorder=0))
ax.text(16.8, 2.25, "SentinelTrade", ha="center", fontsize=18, fontweight="bold")
for nome, cor, x, ytop, ybot in boxes:
    x0, x1 = (x, x) if not isinstance(x, tuple) else x
    ax.add_patch(FancyBboxPatch((x0 - W / 2 - 0.45, ybot), (x1 - x0) + W + 0.9, ytop - ybot,
                                boxstyle="round,pad=0.02,rounding_size=0.2", fc=cor, ec="#666", lw=1.0, zorder=1))
    ax.text(x0 - W / 2 - 0.3, ytop - 0.12, nome, fontsize=8.5, fontweight="bold", va="top", color="#333", zorder=2)

def edge_pt(cx, cy, tx, ty):
    dx, dy = tx - cx, ty - cy
    t = 1 / math.sqrt((dx / (W / 2)) ** 2 + (dy / (H / 2)) ** 2)
    return cx + dx * t, cy + dy * t

for a, ucs in ASSOC.items():
    x, y0, _, ext = ACT[a]
    for k in ucs:
        sx, sy = x + (-0.7 if ext else 0.7), y0 + 0.3
        px, py = edge_pt(*pos[k], sx, sy)
        ax.plot([sx, px], [sy, py], color="#222", lw=1.0, zorder=3)

def rel(s, d, label):
    p0, p1 = edge_pt(*pos[s], *pos[d]), edge_pt(*pos[d], *pos[s])
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="->,head_length=6,head_width=3.5", linestyle=(0, (5, 3)),
                                 color="#0f4c81", lw=1.1, zorder=4, shrinkA=0, shrinkB=0))
    f = 0.62
    ax.text(p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f, label, fontsize=6.8, color="#0f4c81",
            ha="center", va="center", zorder=5, bbox=dict(fc="white", ec="none", pad=0.4, alpha=0.9))
for s, d in INCLUDE: rel(s, d, "«include»")
for s, d in EXTEND: rel(s, d, "«extend»")

for k, (x, y0) in pos.items():
    ax.add_patch(Ellipse((x, y0), W, H, fc="white", ec="#222", lw=1.3, zorder=6))
    ax.text(x, y0, f"UC-{k}\n{NOMES[k]}", ha="center", va="center", fontsize=7.4, zorder=7, linespacing=1.12)

for a, (x, y0, label, ext) in ACT.items():
    ax.add_patch(plt.Circle((x, y0 + 0.55), 0.22, fc="white", ec="#111", lw=1.4, zorder=7))
    for (xa, ya, xb, yb) in [(x, y0 + .33, x, y0 - .15), (x - .4, y0 + .2, x + .4, y0 + .2),
                             (x, y0 - .15, x - .32, y0 - .65), (x, y0 - .15, x + .32, y0 - .65)]:
        ax.plot([xa, xb], [ya, yb], color="#111", lw=1.4, zorder=7)
    ax.text(x, y0 - 0.85, label, ha="center", va="top", fontsize=9.5, fontweight="bold", zorder=7)
    if ext:
        ax.text(x, y0 - 0.85 - 0.45 * (label.count("\n") + 1) - 0.05, "«sistema externo»", ha="center",
                va="top", fontsize=7.5, color="#0f4c81", zorder=7)

ax.text(pos["19"][0], ymin + 0.55,
        "UC-19 Registrar auditoria também é incluído por UC-01, UC-03, UC-04, UC-05 e UC-12 (omitido para legibilidade).\n"
        "UC-17 Ativar modo restrito estende UC-16 quando a corretora ou o provedor de cotações está indisponível.",
        ha="center", va="center", fontsize=7.8, zorder=8,
        bbox=dict(boxstyle="round,pad=0.4", fc="#fffbe6", ec="#999"))
fig.savefig(os.path.join(os.path.dirname(os.path.abspath(__file__)), "casos-de-uso.png"), dpi=110, bbox_inches="tight", facecolor="white")
