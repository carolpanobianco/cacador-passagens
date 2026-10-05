"""Fontes de preço.

- Aviasales (Travelpayouts): varre meses inteiros de graça — acha as datas mais baratas.
- Google Flights (SerpApi): confirma o preço real nas melhores datas. Cobre Azul, LATAM,
  GOL, American, Copa, Delta, United etc. e já diz qual é a faixa "típica" da rota.
- Blogs de promoção (RSS): Melhores Destinos, Passagens Imperdíveis… pega promoções
  relâmpago e erros tarifários que os buscadores às vezes nem mostram.
"""
import re
from datetime import date, datetime

import requests

from .links import link_google_flights
from .modelos import Oferta

TIMEOUT = 30


def _data(txt):
    if not txt:
        return None
    try:
        return datetime.fromisoformat(str(txt)[:10]).date()
    except ValueError:
        return None


# ---------------------------------------------------------------- Aviasales
def aviasales(rota: dict, origem: str, mes: str, token: str, moeda="brl") -> list[Oferta]:
    r = requests.get(
        "https://api.travelpayouts.com/aviasales/v3/prices_for_dates",
        params={
            "origin": origem, "destination": rota["destino"], "departure_at": mes,
            "one_way": "false", "sorting": "price", "unique": "false",
            "currency": moeda.lower(), "market": "br", "limit": 1000, "page": 1,
        },
        headers={"X-Access-Token": token}, timeout=TIMEOUT,
    )
    if r.status_code == 401:
        raise RuntimeError("Token do Travelpayouts inválido")
    r.raise_for_status()
    ofertas = []
    for d in r.json().get("data", []):
        ida, volta = _data(d.get("departure_at")), _data(d.get("return_at"))
        o = Oferta(
            rota=rota["nome"], origem=d.get("origin_airport") or origem,
            destino=d.get("destination_airport") or rota["destino"],
            ida=ida, volta=volta, preco=float(d["price"]), fonte="Aviasales",
            cia=d.get("airline", ""),
            escalas=(d.get("transfers") or 0) + (d.get("return_transfers") or 0),
            link="https://www.aviasales.com" + d["link"] if d.get("link") else "",
            preco_cache=True,
        )
        n = o.noites
        if n is not None and rota.get("noites_min", 0) <= n <= rota.get("noites_max", 99):
            ofertas.append(o)
    return ofertas


# ---------------------------------------------------------- Google Flights
def google_flights(rota: dict, origem: str, ida: date, volta: date, chave: str,
                   moeda="BRL") -> tuple[list[Oferta], dict]:
    """Retorna (ofertas, price_insights). price_insights traz typical_price_range."""
    r = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google_flights", "departure_id": origem,
            "arrival_id": rota["destino"], "outbound_date": ida.isoformat(),
            "return_date": volta.isoformat(), "type": "1", "currency": moeda,
            "hl": "pt-br", "gl": "br", "api_key": chave,
        },
        timeout=60,
    )
    r.raise_for_status()
    js = r.json()
    if js.get("error"):
        raise RuntimeError(js["error"])
    link = (js.get("search_metadata") or {}).get("google_flights_url") \
        or link_google_flights(origem, rota["destino"], ida, volta)
    ofertas = []
    for voo in (js.get("best_flights") or []) + (js.get("other_flights") or []):
        if not voo.get("price"):
            continue
        trechos = voo.get("flights", [])
        cias = sorted({t.get("airline", "") for t in trechos if t.get("airline")})
        ofertas.append(Oferta(
            rota=rota["nome"], origem=origem, destino=rota["destino"], ida=ida, volta=volta,
            preco=float(voo["price"]), fonte="Google Flights", cia=" + ".join(cias),
            escalas=max(len(trechos) - 1, 0), link=link,
        ))
    return ofertas, js.get("price_insights") or {}


# ------------------------------------------------------------------ Blogs
_PRECO = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+)", re.I)


def extrair_preco(texto: str):
    """Pega o MENOR valor em R$ do texto (blogs costumam dizer 'a partir de R$ 1.234')."""
    valores = []
    for m in _PRECO.findall(texto or ""):
        try:
            v = float(m.replace(".", "").replace(",", "."))
        except ValueError:
            continue
        if v >= 200:  # ignora taxas, "R$ 50 de desconto" etc.
            valores.append(v)
    return min(valores) if valores else None


def blogs(feeds: list[dict], rotas: list[dict], erros: list | None = None) -> list[Oferta]:
    import feedparser

    ofertas = []
    for feed in feeds:
        try:
            resp = requests.get(feed["feed"], timeout=TIMEOUT,
                                headers={"User-Agent": "Mozilla/5.0 cacador-passagens"})
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except Exception as e:  # um blog fora do ar não derruba o resto
            print(f"  ! {feed['nome']}: {e}")
            if erros is not None:
                erros.append(f"{feed['nome']}: site não respondeu")
            continue
        for item in parsed.entries[:60]:
            titulo = item.get("title", "")
            texto = f"{titulo} {item.get('summary', '')}"
            baixo = texto.lower()
            if not any(k in baixo for k in ("passage", "voo", "voos", "ida e volta", "aére")):
                continue
            if any(k in titulo.lower() for k in ("pacote", "hotel", "cruzeiro", "milhas", "pontos")):
                continue  # preço de pacote/milhas não se compara com passagem em dinheiro
            for rota in rotas:
                if any(p.lower() in baixo for p in rota.get("palavras_blog", [])):
                    preco = extrair_preco(texto)
                    ofertas.append(Oferta(
                        rota=rota["nome"], origem="?", destino=rota["destino"], ida=None,
                        volta=None, preco=preco or 0.0, fonte=feed["nome"],
                        link=item.get("link", ""), titulo=titulo,
                        extra={"publicado": item.get("published", ""), "sem_preco": preco is None},
                    ))
    return ofertas
