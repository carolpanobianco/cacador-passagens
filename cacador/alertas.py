"""Avisos no Telegram e/ou e-mail."""
import os
import smtplib
from email.mime.text import MIMEText

import requests

from . import links
from .modelos import Promocao


def brl(v: float) -> str:
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def texto(p: Promocao) -> str:
    o = p.oferta
    emoji = "🚨" if p.nivel == "IMPERDÍVEL" else "✈️"
    linhas = [f"{emoji} {p.nivel} — {o.rota}"]
    if o.titulo:
        linhas.append(o.titulo)
    else:
        linhas.append(f"{o.origem} → {o.destino}  |  {o.ida:%d/%m/%Y} a {o.volta:%d/%m/%Y} ({o.noites} noites)")
    linhas.append(f"{brl(o.preco)} ida e volta  (normal ~{brl(p.preco_normal)}, {p.desconto:.0%} mais barato)")
    det = [x for x in (o.cia, f"{o.escalas} escala(s)" if o.escalas is not None else "") if x]
    if det:
        linhas.append(" · ".join(det))
    linhas.append(f"Fonte: {o.fonte}" + (" (preço visto recentemente — confira)" if o.preco_cache else ""))
    if o.link:
        linhas.append(o.link)
    extras = links.todos(o.origem, o.destino, o.ida, o.volta)
    if extras:
        linhas.append("Conferir: " + " | ".join(f"{k}: {v}" for k, v in extras.items()
                                                 if k in ("Skyscanner", "Azul", "Google Flights")))
    return "\n".join(linhas)


def telegram(msg: str) -> bool:
    tok, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        print("  (Telegram não configurado — pulei)")
        return False
    r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      json={"chat_id": chat, "text": msg[:4000], "disable_web_page_preview": True},
                      timeout=20)
    if not r.ok:
        print(f"  ! Telegram: {r.text[:200]}")
    return r.ok


def email(assunto: str, corpo: str) -> bool:
    rem, senha, dest = (os.getenv(k) for k in ("EMAIL_REMETENTE", "EMAIL_SENHA_APP", "EMAIL_DESTINO"))
    if not (rem and senha and dest):
        print("  (E-mail não configurado — pulei)")
        return False
    m = MIMEText(corpo, "plain", "utf-8")
    m["Subject"], m["From"], m["To"] = assunto, rem, dest
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(rem, senha)
        s.send_message(m)
    return True


def descobrir_chat_id():
    tok = os.getenv("TELEGRAM_TOKEN")
    if not tok:
        print("Coloque TELEGRAM_TOKEN no .env primeiro.")
        return
    r = requests.get(f"https://api.telegram.org/bot{tok}/getUpdates", timeout=20).json()
    chats = {u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name", "")
             for u in r.get("result", []) if "message" in u}
    if not chats:
        print("Nenhuma mensagem encontrada. Mande um 'oi' pro seu bot no Telegram e rode de novo.")
    for cid, nome in chats.items():
        print(f"TELEGRAM_CHAT_ID={cid}   ({nome})")
