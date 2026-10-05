"""Caçador de Passagens — procura promoções de passagens aéreas e avisa você.

Uso:
  python main.py                 # uma rodada completa (busca, compara, avisa, gera dashboard.html)
  python main.py --demo          # testa com dados de exemplo, sem chaves
  python main.py --descobrir-chat   # mostra seu TELEGRAM_CHAT_ID
  python main.py --sem-alerta    # roda mas não manda Telegram/e-mail
"""
import argparse
import os
from concurrent.futures import ThreadPoolExecutor
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


def preparar(cfg):
    """Completa cada rota com o que vale pra todas: origens e os próximos N meses (janela que vai rolando)."""
    hoje = date.today()
    n = cfg.get("meses_a_frente", 9)
    meses = []
    a, m = hoje.year, hoje.month
    for _ in range(n):
        m += 1
        if m > 12:
            a, m = a + 1, 1
        meses.append(f"{a}-{m:02d}")
    for r in cfg["rotas"]:
        r.setdefault("origens", cfg.get("origens", ["GRU", "VCP"]))
        r.setdefault("meses", meses)
        r.setdefault("noites", [4, 15])
        if isinstance(r.get("destinos"), str):
            r["destinos"] = [r["destinos"]]
    return cfg


def buscar(cfg, hist, erros):
    rotas, regras = cfg["rotas"], cfg.get("regras", {})
    moeda = cfg.get("moeda", "BRL")
    tp, serp = os.getenv("TRAVELPAYOUTS_TOKEN"), os.getenv("SERPAPI_KEY")
    if not tp and not serp:
        erros.append("Sem TRAVELPAYOUTS_TOKEN nem SERPAPI_KEY — só os blogs foram lidos.")
    todas = []
    por_rota = {r["nome"]: [] for r in rotas}

    # 1) Aviasales: varre todos os meses, de GRU e VCP, pra todos os destinos (grátis)
    if tp:
        tarefas = [(r, o, d, m) for r in rotas for o in r["origens"] for d in r["destinos"] for m in r["meses"]]
        print(f"▶ Aviasales: {len(tarefas)} consultas")

        def uma(t):
            r, o, d, m = t
            try:
                return r["nome"], fontes.aviasales(r, o, d, m, tp, moeda), None
            except Exception as e:
                return r["nome"], [], f"Aviasales {r['nome']} {o}→{d} {m}: {e}"

        with ThreadPoolExecutor(max_workers=4) as ex:
            for nome, achadas, erro in ex.map(uma, tarefas):
                por_rota[nome] += achadas
                if erro:
                    erros.append(erro)
        for r in rotas:
            menor = min((o.preco for o in por_rota[r["nome"]]), default=None)
            print(f"  {r['nome']:28} {len(por_rota[r['nome']]):4} preços   menor {alertas.brl(menor) if menor else '—'}")
            todas += por_rota[r["nome"]]

    # 2) Google Flights: cota grátis é curta, então confere só as rotas que mais importam nesta rodada:
    #    metade = as que o Aviasales apontou como mais abaixo do normal; o resto = as que estão há mais tempo sem conferir.
    if serp:
        cota = regras.get("google_por_rodada", 4)

        def desconto(r):
            normal, _ = analise.preco_normal(r, hist)
            menor = min((o.preco for o in por_rota[r["nome"]]), default=None)
            return (1 - menor / normal) if (normal and menor) else -1

        pelo_desconto = sorted(rotas, key=desconto, reverse=True)
        escolhidas = [r for r in pelo_desconto if desconto(r) > 0][: (cota + 1) // 2]
        for r in sorted(rotas, key=lambda r: hist.ultimo_google(r["nome"])):
            if len(escolhidas) >= cota:
                break
            if r not in escolhidas:
                escolhidas.append(r)

        print(f"\n▶ Google Flights: {', '.join(r['nome'] for r in escolhidas)}")
        for r in escolhidas:
            cand = sorted(por_rota[r["nome"]], key=lambda o: o.preco)
            if cand:
                ida, volta = cand[0].ida, cand[0].volta
            else:
                ida = date.fromisoformat(r["meses"][1] + "-15")
                volta = ida + timedelta(days=r["noites"][0] + 2)
            try:
                achadas, insights = fontes.google_flights(r, r["origens"], ida, volta, serp, moeda)
                todas += achadas
                hist.salvar_tipico(r["nome"], insights.get("typical_price_range"))
                menor = min((o.preco for o in achadas), default=None)
                print(f"  {r['nome']:28} {ida}→{volta}: menor {alertas.brl(menor) if menor else '—'}"
                      f"  (Google diz: {insights.get('price_level', '?')}, típico {insights.get('typical_price_range')})")
            except Exception as e:
                erros.append(f"Google Flights {r['nome']} {ida}: {e}")

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
    cias = ["Azul", "LATAM", "GOL", "American", "Copa", "United", "Avianca", "TAP", "Iberia"]
    for rota in cfg["rotas"]:
        base = rota.get("preco_normal") or rota.get("referencia") or 3000
        for mes in rota["meses"]:
            fator_mes = 1.35 if mes.endswith(("-12", "-01", "-07")) else 1.0
            for _ in range(6):
                ida = date.fromisoformat(mes + "-01") + timedelta(days=random.randint(0, 27))
                volta = ida + timedelta(days=random.randint(*rota["noites"]))
                ofertas.append(Oferta(rota["nome"], random.choice(rota["origens"]), random.choice(rota["destinos"]),
                                      ida, volta, round(base * fator_mes * random.uniform(0.72, 1.3)),
                                      random.choice(["Aviasales", "Google Flights"]), random.choice(cias),
                                      random.randint(0, 2)))
    def promo(nome, origem, dest, dias, noites, preco, fonte, cia, esc):
        ida = date.today() + timedelta(days=dias)
        ofertas.append(Oferta(nome, origem, dest, ida, ida + timedelta(days=noites), preco, fonte, cia, esc,
                              preco_cache=fonte == "Aviasales"))
    promo("Orlando", "VCP", "MCO", 75, 9, 1000, "Google Flights", "Azul", 0)
    promo("Roma", "GRU", "FCO", 140, 12, 2790, "Aviasales", "TAP", 1)
    promo("Salvador", "VCP", "SSA", 40, 5, 540, "Google Flights", "Azul", 0)
    promo("Santiago", "GRU", "SCL", 60, 6, 990, "Aviasales", "Sky", 0)
    ofertas.append(Oferta("Atenas", "?", "ATH", None, None, 3290, "Melhores Destinos",
                          link="https://www.melhoresdestinos.com.br/",
                          titulo="Exemplo: voos para Atenas a partir de R$ 3.290 ida e volta"))
    return ofertas


def demo_historico(cfg, hist):
    """60 dias de histórico inventado pro gráfico do modo demonstração."""
    random.seed(3)
    agora = datetime.now()
    for rota in cfg["rotas"]:
        base = rota.get("preco_normal") or rota.get("referencia") or 3000
        nivel = base * 1.05
        for d in range(60, 0, -1):
            nivel = max(base * 0.75, min(base * 1.3, nivel + random.uniform(-0.05, 0.05) * base))
            ida = date.today() + timedelta(days=60)
            hist.salvar([Oferta(rota["nome"], rota["origens"][0], rota["destinos"][0], ida, ida + timedelta(days=8),
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

    cfg = preparar(yaml.safe_load(open(AQUI / "config.yaml", encoding="utf-8")))
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
