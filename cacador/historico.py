"""Histórico de preços (SQLite) — é com ele que o programa aprende o 'preço normal'."""
import sqlite3
import statistics
from datetime import datetime, timedelta

from .modelos import Oferta


class Historico:
    def __init__(self, caminho="historico.db"):
        self.db = sqlite3.connect(caminho)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS precos(
                quando TEXT, rota TEXT, origem TEXT, destino TEXT, ida TEXT, volta TEXT,
                preco REAL, fonte TEXT, cia TEXT, escalas INTEGER, link TEXT);
            CREATE INDEX IF NOT EXISTS ix_rota ON precos(rota, quando);
            CREATE TABLE IF NOT EXISTS alertas(chave TEXT PRIMARY KEY, preco REAL, quando TEXT);
            CREATE TABLE IF NOT EXISTS tipico(rota TEXT PRIMARY KEY, baixo REAL, alto REAL, quando TEXT);
        """)

    def salvar(self, ofertas: list[Oferta], quando: datetime | None = None):
        agora = (quando or datetime.now()).isoformat(timespec="seconds")
        self.db.executemany(
            "INSERT INTO precos VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(agora, o.rota, o.origem, o.destino, str(o.ida), str(o.volta), o.preco,
              o.fonte, o.cia, o.escalas, o.link) for o in ofertas if o.preco > 0 and o.ida],
        )
        self.db.commit()

    def mediana(self, rota: str, dias=60, minimo=15):
        """Mediana dos menores preços por rodada nos últimos N dias."""
        desde = (datetime.now() - timedelta(days=dias)).isoformat()
        linhas = self.db.execute(
            "SELECT preco FROM precos WHERE rota=? AND quando>=? AND fonte='Google Flights'",
            (rota, desde)).fetchall() or self.db.execute(
            "SELECT preco FROM precos WHERE rota=? AND quando>=?", (rota, desde)).fetchall()
        precos = [p for (p,) in linhas]
        return statistics.median(precos) if len(precos) >= minimo else None

    def salvar_tipico(self, rota, faixa):
        if faixa and len(faixa) == 2:
            self.db.execute("INSERT OR REPLACE INTO tipico VALUES (?,?,?,?)",
                            (rota, faixa[0], faixa[1], datetime.now().isoformat()))
            self.db.commit()

    def tipico(self, rota):
        r = self.db.execute("SELECT baixo, alto FROM tipico WHERE rota=?", (rota,)).fetchone()
        return r

    def ja_alertado(self, chave: str, preco: float, queda_min: float) -> bool:
        r = self.db.execute("SELECT preco FROM alertas WHERE chave=?", (chave,)).fetchone()
        return bool(r) and preco > r[0] * (1 - queda_min)

    def marcar_alertado(self, chave: str, preco: float):
        self.db.execute("INSERT OR REPLACE INTO alertas VALUES (?,?,?)",
                        (chave, preco, datetime.now().isoformat()))
        self.db.commit()

    def serie(self, rota: str, dias=90):
        """Menor preço por dia — pro gráfico do relatório."""
        desde = (datetime.now() - timedelta(days=dias)).isoformat()
        return self.db.execute(
            "SELECT substr(quando,1,10) d, MIN(preco) FROM precos WHERE rota=? AND quando>=? "
            "GROUP BY d ORDER BY d", (rota, desde)).fetchall()
