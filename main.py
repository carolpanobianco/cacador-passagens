"""Caçador de Passagens — procura promoções de passagens aéreas e avisa você.

Uso:
  python main.py                 # uma rodada completa (busca, compara, avisa, gera dashboard.html)
  python main.py --demo          # testa com dados de exemplo, sem chaves
  python main.py --descobrir-chat   # mostra seu TELEGRAM_CHAT_ID
  python main.py --sem-alerta    # roda mas não manda Telegram/e-mail
"""
import argparse
import os
import random
import sys
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

from cacador import alertas, analise, fontes, painel
from cacador.historico import Historico
from cacador.modelos import Oferta

AQUI = Path(__file__).parent


def url_pagina():
    """Endereço do dashboard no GitHub Pages (PAGINA_URL no .env, ou deduzido do repositório)."""
    if os.getenv("PAGINA_URL"):
        return os.getenv("PAGINA_URL")
    repo = os.getenv("GITHUB_REPOSITORY")  # "dono/nome", existe quando roda no GitHub
    if repo and "/" in repo:
        dono, nome = repo.split("/", 1)
        return f"https://{dono.lower()}.github.io/{nome}/"
    return ""


def status_fontes(cfg, ofertas, erros, demo=False):
    def st(nome, chave_env, prefixo):
        n = sum(1 for o in ofertas if o.fonte == nome)
        falhas = [e for e in erros if e.startswith(prefixo)]
        if demo:
            return {"nome": nome, "status": "ok", "detalhe": f"{n} preços (exemplo)"}
        if chave_env and not os.getenv(chave_env):
            return {"nome": nome, "status": "na", "detalhe": "falta cadastrar a chave"}
        if falhas and not n:
            return {"nome": nome, "status": "erro", "detalhe": f"{len(falhas)} falha(s)"}
        return {"nome": nome, "status": "ok", "detalhe": f"{n} preços" + (f", {len(falhas)} falha(s)" if falhas else "")}
    lst = [st("Google Flights", "SERPAPI_KEY", "Google"), st("Aviasales", "TRAVELPAYOUTS_TOKEN", "Aviasales")]
    for b in cfg.get("blogs", []):
        n = sum(1 for o in ofertas if o.fonte == b["nome"])
        fora = any(e.startswith(b["nome"]) for e in erros)
        lst.append({"nome": b["nome"], "status": "erro" if fora else "ok",
                    "detalhe": "fora do ar" if fora else f"{n} post(s) sobre suas rotas"})
    return lst


def buscar(cfg, hist, erros):
    rotas, regras = cfg["rotas"], cfg.get("regras", {})
    moeda = cfg.get("moeda", "BRL")
    tp, serp = os.getenv("TRAVELPAYOUTS_TOKEN"), os.getenv("SERPAPI_KEY")
    if not tp and not serp:
        erros.append("Sem TRAVELPAYOUTS_TOKEN nem SERPAPI_KEY no .env — só os blogs foram lidos.")
    todas = []

    for rota in rotas:
        print(f"\n▶ {rota['nome']}")
        # 1) Aviasales varre os meses e acha as datas mais baratas
        candidatos = []
        if tp:
            for origem in rota["origens"]:
                for mes in rota["meses"]:
                    try:
                        achadas = fontes.aviasales(rota, origem, mes, tp, moeda)
                        candidatos += achadas
                        print(f"  Aviasales {origem} {mes}: {len(achadas)} preços")
                    except Exception as e:
                        erros.append(f"Aviasales {rota['nome']} {origem} {mes}: {e}")
        todas += candidatos

        # 2) Google Flights confirma as N melhores datas (economiza a cota grátis)
        if serp:
            datas = []
            for o in sorted(candidatos, key=lambda o: o.preco):
                k = (o.origem, o.ida, o.volta)
                if k not in datas:
                    datas.append(k)
                if len(datas) >= regras.get("confirmar_no_google", 3):
                    break
            if not datas:  # sem Aviasales: testa uma data padrão de cada mês
                for mes in rota["meses"][:regras.get("confirmar_no_google", 3)]:
                    ida = date.fromisoformat(mes + "-15")
                    datas.append((rota["origens"][0], ida, ida + timedelta(days=rota.get("noites_min", 7))))
            for origem, ida, volta in datas:
                try:
                    achadas, insights = fontes.google_flights(rota, origem, ida, volta, serp, moeda)
                    todas += achadas
                    hist.salvar_tipico(rota["nome"], insights.get("typical_price_range"))
                    menor = min((o.preco for o in achadas), default=None)
                    print(f"  Google {origem} {ida}→{volta}: menor {alertas.brl(menor) if menor else '—'}"
                          f"  (nível: {insights.get('price_level', '?')})")
                except Exception as e:
                    erros.append(f"Google Flights {rota['nome']} {origem} {ida}: {e}")

    # 3) Blogs de promoção
    if cfg.get("blogs"):
        posts = fontes.blogs(cfg["blogs"], rotas, erros)
        print(f"\n▶ Blogs: {len(posts)} posts sobre suas rotas")
        todas += posts
    return todas


def demo(cfg):
    """Dados inventados pra ver o programa funcionando sem chave nenhuma."""
    random.seed(7)
    ofertas = []
    hoje = date.today()
    for rota in cfg["rotas"]:
        base = rota.get("preco_normal") or 3000
        for _ in range(40):
            ida = hoje + timedelta(days=random.randint(30, 180))
            volta = ida + timedelta(days=random.randint(rota.get("noites_min", 5), rota.get("noites_max", 14)))
            ofertas.append(Oferta(rota["nome"], random.choice(rota["origens"]), rota["destino"], ida, volta,
                                  round(base * random.uniform(0.8, 1.35)), random.choice(["Aviasales", "Google Flights"]),
                                  random.choice(["Azul", "LATAM", "American", "Copa", "GOL"]), random.randint(0, 2),
                                  preco_cache=False))
    ida = hoje + timedelta(days=75)
    ofertas.append(Oferta("Orlando", "VCP", "MCO", ida, ida + timedelta(days=9), 1000, "Google Flights",
                          "Azul", 0))
    ofertas.append(Oferta("Orlando", "GRU", "MCO", ida + timedelta(days=20), ida + timedelta(days=30), 1690,
                          "Aviasales", "LATAM", 1, preco_cache=True))
    ofertas.append(Oferta("Miami", "?", "MIA", None, None, 1449, "Melhores Destinos",
                          link="https://www.melhoresdestinos.com.br/",
                          titulo="Exemplo: voos para Miami a partir de R$ 1.449 ida e volta"))
    return ofertas


def demo_historico(cfg, hist):
    """60 dias de histórico inventado pro gráfico do modo demonstração."""
    random.seed(3)
    agora = datetime.now()
    for rota in cfg["rotas"]:
        base = rota.get("preco_normal") or 3000
        nivel = base * 1.05
        for d in range(60, 0, -1):
            nivel = max(base * 0.75, min(base * 1.3, nivel + random.uniform(-0.05, 0.05) * base))
            ida = date.today() + timedelta(days=60)
            hist.salvar([Oferta(rota["nome"], rota["origens"][0], rota["destino"], ida, ida + timedelta(days=8),
                                round(nivel), "Google Flights")], quando=agora - timedelta(days=d))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--sem-alerta", action="store_true")
    ap.add_argument("--descobrir-chat", action="store_true")
    ap.add_argument("--abrir", action="store_true", help="abre o dashboard no navegador no fim")
    args = ap.parse_args()

    load_dotenv(AQUI / ".env")
    if args.descobrir_chat:
        return alertas.descobrir_chat_id()

    cfg = yaml.safe_load(open(AQUI / "config.yaml", encoding="utf-8"))
    hist = Historico(str(AQUI / ("demo.db" if args.demo else "historico.db")))
    erros = []

    if args.demo:
        hist.db.execute("DELETE FROM precos")
        demo_historico(cfg, hist)
    ofertas = demo(cfg) if args.demo else buscar(cfg, hist, erros)
    hist.salvar(ofertas)

    promos = analise.classificar(ofertas, cfg["rotas"], cfg.get("regras", {}), hist)
    normais = {r["nome"]: analise.preco_normal(r, hist) for r in cfg["rotas"]}

    print(f"\n★ {len(promos)} promoção(ões)")
    novas = []
    queda = cfg.get("regras", {}).get("realertar_se_cair", 0.05)
    for p in promos:
        print("\n" + alertas.texto(p))
        if not hist.ja_alertado(p.oferta.chave(), p.oferta.preco, queda):
            novas.append(p)

    if novas and not (args.sem_alerta or args.demo):
        msg = "\n\n".join(alertas.texto(p) for p in novas)
        if url_pagina():
            msg += f"\n\n📊 Dashboard completo: {url_pagina()}"
        enviado = False
        if cfg["alertas"].get("telegram"):
            enviado |= alertas.telegram(msg)
        if cfg["alertas"].get("email"):
            enviado |= alertas.email(f"✈️ {len(novas)} promoção(ões) de passagem", msg)
        if enviado:
            for p in novas:
                hist.marcar_alertado(p.oferta.chave(), p.oferta.preco)

    saida = AQUI / "dashboard.html"
    painel.gerar(saida, painel.dados(cfg, promos, ofertas, normais, hist,
                                     status_fontes(cfg, ofertas, erros, args.demo), erros, demo=args.demo))
    for e in erros:
        print("  ! " + e)
    print(f"\nDashboard: {saida}")
    if args.abrir:
        webbrowser.open(saida.resolve().as_uri())


if __name__ == "__main__":
    sys.exit(main())
