"""Links prontos pra conferir/comprar em cada site, já com rota e datas preenchidas."""
from datetime import date
from urllib.parse import quote


def link_google_flights(o, d, ida: date, volta: date) -> str:
    q = f"Voos de {o} para {d} em {ida.isoformat()} volta {volta.isoformat()}"
    return f"https://www.google.com/travel/flights?q={quote(q)}&curr=BRL&hl=pt-BR&gl=BR"


def link_skyscanner(o, d, ida: date, volta: date) -> str:
    return (f"https://www.skyscanner.com.br/transporte/passagens-aereas/"
            f"{o.lower()}/{d.lower()}/{ida:%y%m%d}/{volta:%y%m%d}/")


def link_kayak(o, d, ida: date, volta: date) -> str:
    return f"https://www.kayak.com.br/flights/{o}-{d}/{ida.isoformat()}/{volta.isoformat()}"


def link_decolar(o, d, ida: date, volta: date) -> str:
    return (f"https://www.decolar.com/shop/flights/results/roundtrip/"
            f"{o}/{d}/{ida.isoformat()}/{volta.isoformat()}/1/0/0")


def link_azul(o, d, ida: date, volta: date) -> str:
    return (f"https://www.voeazul.com.br/br/pt/home/selecao-voo?"
            f"c[0].ds={o}&c[0].std={ida:%m/%d/%Y}&c[0].as={d}"
            f"&c[1].ds={d}&c[1].std={volta:%m/%d/%Y}&c[1].as={o}"
            f"&p[0].t=ADT&p[0].c=1&cc=BRL")


def todos(o, d, ida, volta) -> dict:
    if not (ida and volta and o and o != "?"):
        return {}
    return {
        "Google Flights": link_google_flights(o, d, ida, volta),
        "Skyscanner": link_skyscanner(o, d, ida, volta),
        "Kayak": link_kayak(o, d, ida, volta),
        "Decolar": link_decolar(o, d, ida, volta),
        "Azul": link_azul(o, d, ida, volta),
    }
