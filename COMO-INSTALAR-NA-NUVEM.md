# Link sempre atualizado — instalação na nuvem

Depois de instalado, o Caçador roda sozinho no GitHub às **8h e às 20h**, com seu computador desligado, e atualiza o dashboard num endereço fixo, tipo:

**`https://SEU-USUARIO.github.io/cacador-passagens/`**

Você salva esse link no iPad e pronto. Quando aparecer promoção, chega também no Telegram, já com o link do dashboard.

É grátis. Faz uma vez só, leva uns 15 minutos, e é mais fácil no computador.

---

## 1. Pegar as chaves (grátis)

| Chave | Onde pegar |
|---|---|
| `SERPAPI_KEY` | serpapi.com → **Register** → no painel, copie a **Your Private API Key** |
| `TRAVELPAYOUTS_TOKEN` | travelpayouts.com → cadastro → **Ferramentas › API** (Tools › API) → copie o **token** |
| `TELEGRAM_TOKEN` | No Telegram, procure **@BotFather** → mande `/newbot` → escolha um nome → ele responde com o token |
| `TELEGRAM_CHAT_ID` | Mande um "oi" pro seu bot novo. Depois abra no navegador `https://api.telegram.org/botSEU_TOKEN/getUpdates` (troque SEU_TOKEN pelo token acima). Procure `"chat":{"id":` — o número logo depois é o seu chat id |

Guarde as quatro num bloco de notas.

## 2. Criar o repositório

1. Entre em **github.com** (crie conta se não tiver) → botão **+** no canto de cima → **New repository**.
2. Nome: `cacador-passagens`.
3. Marque **Public**. *(Por quê: a página grátis do GitHub só funciona em repositório público. Suas chaves NÃO ficam visíveis — elas vão num cofre separado no passo 4. O que fica público é o código, as rotas que você vigia e os preços encontrados. A página não aparece no Google.)*
4. Clique **Create repository**.

## 3. Subir os arquivos

1. Descompacte o `cacador-passagens.zip`.
2. Na página do repositório, clique **uploading an existing file**.
3. Abra a pasta descompactada, **selecione tudo que está dentro dela** e arraste pra página. Clique **Commit changes**.
4. Agora o arquivo que o GitHub esconde: clique **Add file › Create new file**.
   - No nome, digite exatamente: `.github/workflows/cacador.yml`
   - Abra o arquivo `workflow-para-colar.yml` (está na pasta), copie tudo e cole no editor.
   - **Commit changes**.

## 4. Guardar as chaves no cofre

Repositório → **Settings › Secrets and variables › Actions › New repository secret**.
Crie um por vez, com estes nomes exatos, colando o valor do passo 1:

- `SERPAPI_KEY`
- `TRAVELPAYOUTS_TOKEN`
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`

## 5. Ligar a página

Repositório → **Settings › Pages** → em **Source**, escolha **GitHub Actions**. Só isso.

## 6. Rodar a primeira vez

Repositório → aba **Actions** → (se pedir, clique **I understand… enable workflows**) → **Caçador de Passagens** à esquerda → **Run workflow** → **Run workflow**.

Em ~2 minutos fica verde ✅. Clique na rodada: o link do dashboard aparece no quadro **cacar**, embaixo de *github-pages*. Também está em **Settings › Pages**.

## 7. No iPad

Abra o link no Safari → botão **Compartilhar** → **Adicionar à Tela de Início**. Vira um ícone de app (“Passagens”), sempre com os dados da última rodada.

---

### Se algo der errado

- **Rodada vermelha ❌ no passo "Publica o dashboard"**: falta o passo 5 (Settings › Pages › Source = GitHub Actions). Ligue e rode de novo.
- **Dashboard abre mas diz "sem chave no .env"** em alguma fonte: o nome do segredo no passo 4 está diferente. Confira letra por letra.
- **Não chega Telegram**: normal se não tiver promoção. O bot só fala quando acha algo abaixo do limite. Pra testar o bot, mande `/start` pra ele e confira o chat id.
- **Mudar rotas, preço normal ou limites**: no GitHub, abra `config.yaml` → ícone do lápis → edite → **Commit changes**. Vale a partir da próxima rodada.
- **Rodar mais vezes por dia**: dá, mas passa da cota grátis do Google (250 buscas/mês). Veja o LEIA-ME.
- **GitHub pausa agendamentos** de repositório sem nenhuma atividade por 60 dias. Como o próprio Caçador salva o histórico a cada rodada, isso não deve acontecer; se acontecer, o GitHub manda e-mail com um botão pra reativar.
