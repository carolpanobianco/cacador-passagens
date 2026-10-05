"""Fontes de preço.

- Aviasales (Travelpayouts): varre meses inteiros de graça — acha as datas mais baratas.
- Google Flights (SerpApi): confirma o preço real nas melhores datas. Cobre Azul, LATAM,
  GOL, American, Copa, Delta, United etc. e já diz qual é a faixa "típica" da rota.
- Blogs de promoção (RSS): Melhores Destinos… pega promoções
  relâmpago e erros tarifários que os buscadores às vezes nem mostram.
"""
import re
import time
from datetime import date, datetime

import requests

from .links import link_google_flights
from .modelos import Oferta

TIMEOUT = 30

CIAS = {"AD": "Azul", "LA": "LATAM", "JJ": "LATAM", "G3": "GOL", "AA": "American", "UA": "United",
        "DL": "Delta", "CM": "Copa", "AV": "Avianca", "DM": "Arajet", "H2": "Sky", "AR": "Aerolíneas",
        "B6": "JetBlue", "NK": "Spirit", "F9": "Frontier", "TP": "TAP", "IB": "Iberia", "AF": "Air France",
        "KL": "KLM", "LH": "Lufthansa", "BA": "British", "EK": "Emirates", "QR": "Qatar", "TK": "Turkish"}


def _data(txt):
    if not txt:
        return None
    try:
        return datetime.fromisoformat(str(txt)[:10]).date()
    except ValueError:
        return None


# ---------------------------------------------------------------- Aviasales
def aviasales(rota: dict, origem: str, destino: str, mes: str, token: str, moeda="brl") -> list[Oferta]:
    """Passagens ida e volta mais baratas que viajantes acharam nas últimas 48h, pra um mês de ida."""
    params = {
        "origin": origem, "destination": destino, "departure_at": mes,
        "one_way": "false", "sorting": "price", "unique": "false",
        "currency": moeda.lower(), "market": "br", "limit": 1000, "page": 1,
    }
    for tentativa in range(3):
        r = requests.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates",
                         params=params, headers={"X-Access-Token": token}, timeout=TIMEOUT)
        if r.status_code == 429:          # limite por minuto: espera e tenta de novo
            time.sleep(10 * (tentativa + 1))
            continue
        break
    if r.status_code == 401:
        raise RuntimeError("Token do Travelpayouts inválido")
    r.raise_for_status()
    nmin, nmax = rota.get("noites", [1, 60])
    ofertas = []
    for d in r.json().get("data", []):
        ida, volta = _data(d.get("departure_at")), _data(d.get("return_at"))
        o = Oferta(
            rota=rota["nome"], origem=d.get("origin_airport") or origem,
            destino=d.get("destination_airport") or destino,
            ida=ida, volta=volta, preco=float(d["price"]), fonte="Aviasales",
            cia=CIAS.get(d.get("airline", ""), d.get("airline", "")),
            escalas=(d.get("transfers") or 0) + (d.get("return_transfers") or 0),
            link="https://www.aviasales.com" + d["link"] if d.get("link") else "",
            preco_cache=True,
        )
        if o.origem not in ("GRU", "VCP"):   # garante saída só de Guarulhos ou Viracopos
            continue
        n = o.noites
        if n is not None and nmin <= n <= nmax:
            ofertas.append(o)
    return ofertas


# ---------------------------------------------------------- Google Flights
def google_flights(rota: dict, origens: list[str], ida: date, volta: date, chave: str,
                   moeda="BRL") -> tuple[list[Oferta], dict]:
    """Uma busca cobre GRU e VCP juntos. Retorna (ofertas, price_insights com a faixa típica)."""
    chegada = rota.get("google") or ",".join(rota["destinos"])
    r = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google_flights", "departure_id": ",".join(origens),
            "arrival_id": chegada, "outbound_date": ida.isoformat(),
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
        or link_google_flights(origens[0], chegada.split(",")[0], ida, volta)
    ofertas = []
    for voo in (js.get("best_flights") or []) + (js.get("other_flights") or []):
        trechos = voo.get("flights", [])
        if not voo.get("price") or not trechos:
            continue
        cias = sorted({t.get("airline", "") for t in trechos if t.get("airline")})
        ofertas.append(Oferta(
            rota=rota["nome"],
            origem=(trechos[0].get("departure_airport") or {}).get("id", origens[0]),
            destino=(trechos[-1].get("arrival_airport") or {}).get("id", chegada.split(",")[0]),
            ida=ida, volta=volta, preco=float(voo["price"]), fonte="Google Flights",
            cia=" + ".join(cias), escalas=max(len(trechos) - 1, 0), link=link,
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
                if any(re.search(r"(?<!\w)" + re.escape(p.lower()) + r"(?!\w)", baixo) for p in rota.get("palavras_blog", [])):
                    preco = extrair_preco(texto)
                    ofertas.append(Oferta(
                        rota=rota["nome"], origem="?", destino=rota["destinos"][0], ida=None,
                        volta=None, preco=preco or 0.0, fonte=feed["nome"],
                        link=item.get("link", ""), titulo=titulo,
                        extra={"publicado": item.get("published", ""), "sem_preco": preco is None},
                    ))
    return ofertas
