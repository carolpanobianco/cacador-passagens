"""Monta o dashboard.html: junta os dados da rodada + histórico e injeta no modelo."""
import json
from datetime import datetime
from pathlib import Path

from . import links as L

MODELO = Path(__file__).with_name("dashboard.html")
CABECA = ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
          '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
          '<meta name="robots" content="noindex,nofollow">'          # não aparece no Google
          '<meta name="theme-color" content="#0b1220">'
          '<meta name="apple-mobile-web-app-capable" content="yes">'  # "Adicionar à Tela de Início" no iPad
          '<meta name="apple-mobile-web-app-title" content="Passagens">'
          '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
          '<link rel="apple-touch-icon" href="icone.png"><link rel="icon" href="icone.png">'
          '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}</style>'
          '</head><body>')


def _links(o):
    ls = L.todos(o.origem, o.destino, o.ida, o.volta)
    if o.link:
        ls = {o.fonte: o.link, **{k: v for k, v in ls.items() if k != o.fonte}}
    return ls


def _oferta(o):
    return {"rota": o.rota, "origem": o.origem, "destino": o.destino,
            "ida": o.ida.isoformat() if o.ida else None,
            "volta": o.volta.isoformat() if o.volta else None,
            "noites": o.noites, "preco": o.preco, "cia": o.cia, "escalas": o.escalas,
            "fonte": o.fonte, "cache": o.preco_cache, "titulo": o.titulo, "links": _links(o)}


def dados(cfg, promos, ofertas, normais, hist, status_fontes, avisos, demo=False):
    rotas = cfg["rotas"]
    voos = [o for o in ofertas if o.ida and o.preco > 0]

    # as 30 mais baratas de cada rota (sem repetir mesmo voo/datas)
    tabela = []
    for r in rotas:
        vistos, n = set(), 0
        for o in sorted((o for o in voos if o.rota == r["nome"]), key=lambda o: o.preco):
            k = (o.origem, o.ida, o.volta, o.cia)
            if k in vistos:
                continue
            vistos.add(k); tabela.append(_oferta(o)); n += 1
            if n >= 30:
                break

    por_mes = {}
    for r in rotas:
        meses = {}
        for o in voos:
            if o.rota == r["nome"]:
                m = o.ida.strftime("%Y-%m")
                meses[m] = min(meses.get(m, o.preco), o.preco)
        por_mes[r["nome"]] = sorted(meses.items())

    return {
        "gerado_em": datetime.now().isoformat(timespec="minutes"),
        "demo": demo,
        "regras": {"desconto_minimo": cfg.get("regras", {}).get("desconto_minimo", 0.4),
                   "desconto_imperdivel": cfg.get("regras", {}).get("desconto_imperdivel", 0.6)},
        "rotas": [{"nome": r["nome"], "origens": r["origens"], "destino": r["destino"],
                   "normal": normais[r["nome"]][0], "base": normais[r["nome"]][1]} for r in rotas],
        "promocoes": [{**_oferta(p.oferta), "nivel": p.nivel, "desconto": round(p.desconto, 3),
                       "normal": p.preco_normal} for p in promos],
        "ofertas": tabela,
        "historico": {r["nome"]: hist.serie(r["nome"]) for r in rotas},
        "por_mes": por_mes,
        "posts": [_oferta(o) for o in ofertas if o.titulo][:30],
        "fontes": status_fontes,
        "avisos": avisos[:15],
    }


def html(d) -> str:
    js = json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
    return MODELO.read_text(encoding="utf-8").replace("/*__DADOS__*/null", js)


def gerar(caminho, d):
    Path(caminho).write_text(CABECA + html(d) + "</body></html>", encoding="utf-8")
