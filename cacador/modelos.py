from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Oferta:
    rota: str                 # nome da rota no config (ex.: "Orlando")
    origem: str
    destino: str
    ida: Optional[date]
    volta: Optional[date]
    preco: float              # ida e volta, por pessoa, R$
    fonte: str                # "Google Flights", "Aviasales", "Melhores Destinos"...
    cia: str = ""
    escalas: Optional[int] = None
    link: str = ""
    titulo: str = ""          # usado pelos blogs
    preco_cache: bool = False # True = preço visto por outro usuário recentemente; confirmar antes de comprar
    extra: dict = field(default_factory=dict)

    @property
    def noites(self) -> Optional[int]:
        if self.ida and self.volta:
            return (self.volta - self.ida).days
        return None

    def chave(self) -> str:
        return f"{self.rota}|{self.origem}|{self.destino}|{self.ida}|{self.volta}|{self.fonte}"


@dataclass
class Promocao:
    oferta: Oferta
    preco_normal: float
    base_do_normal: str       # "config", "histórico", "Google"
    nivel: str                # "PROMOÇÃO" ou "IMPERDÍVEL"

    @property
    def desconto(self) -> float:
        return 1 - self.oferta.preco / self.preco_normal
