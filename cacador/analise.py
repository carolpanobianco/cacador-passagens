"""Decide o que é promoção.

'Preço normal' de cada rota, nesta ordem de prioridade:
  1. o valor que você colocou no config (preco_normal)
  2. a mediana do histórico dos últimos 60 dias (depois de 3 dias coletando)
  3. o meio da faixa 'típica' que o próprio Google Flights informa
  4. a estimativa inicial do config (referencia)
Promoção = preço <= normal × (1 - desconto_minimo).
"""
from .modelos import Oferta, Promocao


def preco_normal(rota: dict, hist) -> tuple[float | None, str]:
    if rota.get("preco_normal"):
        return float(rota["preco_normal"]), "config"
    m = hist.mediana(rota["nome"])
    if m:
        return m, "histórico"
    t = hist.tipico(rota["nome"])
    if t:
        return (t[0] + t[1]) / 2, "Google"
    if rota.get("referencia"):
        return float(rota["referencia"]), "estimativa"
    return None, ""


def classificar(ofertas: list[Oferta], rotas: list[dict], regras: dict, hist) -> list[Promocao]:
    por_rota = {r["nome"]: r for r in rotas}
    normais = {n: preco_normal(r, hist) for n, r in por_rota.items()}
    d_min = regras.get("desconto_minimo", 0.4)
    d_top = regras.get("desconto_imperdivel", 0.6)

    promos = []
    for o in ofertas:
        normal, base = normais.get(o.rota, (None, ""))
        if not normal or o.preco <= 0:
            continue
        desconto = 1 - o.preco / normal
        if desconto >= d_min:
            nivel = "IMPERDÍVEL" if desconto >= d_top else "PROMOÇÃO"
            promos.append(Promocao(o, normal, base, nivel))

    # mantém só a melhor por (rota, origem, ida, volta) — evita 10 alertas do mesmo voo
    melhores = {}
    for p in promos:
        k = (p.oferta.rota, p.oferta.origem, p.oferta.ida, p.oferta.volta, p.oferta.titulo)
        if k not in melhores or p.oferta.preco < melhores[k].oferta.preco:
            melhores[k] = p
    return sorted(melhores.values(), key=lambda p: -p.desconto)
