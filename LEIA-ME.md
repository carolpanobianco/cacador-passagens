# ✈️ Caçador de Passagens

Vigia as rotas que você escolher, aprende quanto cada uma costuma custar e te avisa no Telegram quando aparece algo muito abaixo — tipo Orlando por R$ 1.000 quando o normal é R$ 3.000.

## De onde ele tira os preços

| Fonte | O que cobre | Custo |
|---|---|---|
| **Google Flights** (via SerpApi) | Azul, LATAM, GOL, American, Copa, Delta, United… e as OTAs. Também informa a faixa de preço "típica" da rota | Grátis até 250 buscas/mês |
| **Aviasales** (via Travelpayouts) | Varre meses inteiros e acha as datas mais baratas (preços que outros viajantes viram nas últimas 48h) | Grátis |
| **Melhores Destinos** | Promoções relâmpago e erros tarifários garimpados pelos blogs | Grátis, sem cadastro |

Skyscanner, Azul, Kayak e Decolar não têm API aberta e bloqueiam robôs, então cada promoção já vem com **links prontos pra esses sites, com rota e datas preenchidas** — um toque e você confere lá.

## Como ele decide que é promoção

1. Usa o `preco_normal` que você colocou no `config.yaml` (ex.: Orlando = 3000).
2. Se você deixar em branco, ele aprende sozinho com o histórico (mediana dos últimos 60 dias) ou usa a faixa típica do Google.
3. **40% abaixo do normal → PROMOÇÃO. 60% abaixo → IMPERDÍVEL** (possível erro tarifário — vale comprar rápido; em voos de/para os EUA as cias costumam permitir cancelar sem custo em até 24h).
4. Não repete o mesmo aviso, a não ser que o preço caia mais 5%.

Tudo isso é ajustável no `config.yaml`.

## Instalação (uma vez, ~10 minutos)

1. **Python 3.10+** instalado (python.org — no Windows marque "Add to PATH").
2. Copie `.env.example` para `.env`.
3. Pegue as chaves grátis e cole no `.env`:
   - **SerpApi**: serpapi.com → Sign up → copie a *API Key*
   - **Travelpayouts**: travelpayouts.com → cadastro → *Ferramentas > API* → copie o token
4. **Telegram** (pra receber no celular):
   - No Telegram, fale com **@BotFather** → `/newbot` → dê um nome → copie o token pro `.env`
   - Mande um "oi" pro seu bot novo
   - Rode `python main.py --descobrir-chat` e cole o número em `TELEGRAM_CHAT_ID`
5. Teste sem chave nenhuma: `python main.py --demo`

## Rodar

- **Windows:** duplo clique em `rodar.bat`
- **Mac:** `./rodar.sh`

Cada rodada atualiza o `dashboard.html`: promoções no topo, resumo em números, melhor mês pra viajar, histórico de preços de cada rota, tabela ordenável com links pros sites e o que os blogs postaram. Abre em qualquer navegador, inclusive no celular.

## Deixar rodando sozinho

**Opção A — na nuvem, de graça, com link fixo do dashboard (recomendado):** siga o **COMO-INSTALAR-NA-NUVEM.md**. Ele roda no GitHub às 8h e 20h com o computador desligado, publica o dashboard num endereço fixo (dá pra pôr na Tela de Início do iPad) e manda o Telegram com o link.

**Opção B — no seu PC:** Agendador de Tarefas do Windows → criar tarefa básica → diariamente, 8h e 20h → ação: `rodar.bat`.

## Cota grátis do Google

Já vem calibrado pra caber nos 250 grátis: 2 rotas × 2 datas conferidas × 2 rodadas/dia ≈ 240 buscas/mês. Se adicionar rotas ou rodar mais vezes, baixe `confirmar_no_google` para 1 ou assine o plano pago. O Aviasales e os blogs não têm limite prático.
