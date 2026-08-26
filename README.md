# RN em Movimento 2.0 — Ranking do Desafio

Site estático (HTML/CSS/JS) que mostra o ranking **acumulado** do desafio do clube
[RN EM MOVIMENTO 2.0](https://www.strava.com/clubs/2297640) no Strava (17/08 → 17/09),
somando os leaderboards semanais.

- **Pódios** top 3: distância, atividades e elevação
- **Tabela geral** com todos os atletas (busca + ordenação por coluna)
- **Filtro por semana** ou acumulado do desafio inteiro

## Como funciona

O Strava só mostra a semana atual e a anterior no leaderboard do clube.
Por isso o script `scripts/update_leaderboard.py` roda **pelo menos 1x por semana**,
captura as duas semanas via API e guarda tudo em `data/weeks.json` — que é o arquivo
que a página lê. O site em si é 100% estático (funciona no GitHub Pages).

```
index.html          página do ranking
css/style.css       identidade visual RN Tintas
js/app.js           agregação, pódios, tabela, filtros
data/weeks.json     snapshots semanais (commitado no repo)
scripts/update_leaderboard.py   captura via API do Strava
scripts/.env        credenciais (NUNCA commitar — já está no .gitignore)
```

## Passo a passo — configurar o token do Strava (uma vez só)

### 1. Criar o app na sua conta Strava

1. Acesse <https://www.strava.com/settings/api> (logado na conta que é membro do clube)
2. Preencha:
   - **Application Name**: `RN em Movimento`
   - **Category**: Visualizer
   - **Website**: `https://rntintas-tech.github.io` (ou qualquer URL)
   - **Authorization Callback Domain**: `localhost`
3. Salve. A página mostra **Client ID** e **Client Secret**.

### 2. Salvar as credenciais

Crie o arquivo `scripts/.env` com:

```
STRAVA_CLIENT_ID=seu_client_id
STRAVA_CLIENT_SECRET=seu_client_secret
```

### 3. Autorizar (gera o refresh token)

```bash
python scripts/update_leaderboard.py --auth
```

O script imprime uma URL → abra no navegador → **Autorizar**.
O navegador vai redirecionar para `localhost/...` (página que não abre — normal).
Copie o valor de `code=` da barra de endereços e cole no terminal.
O refresh token fica salvo em `scripts/.env` e **nunca mais precisa repetir isso**.

### 4. Atualizar os dados

```bash
python scripts/update_leaderboard.py
```

Captura a semana atual + a anterior e atualiza `data/weeks.json`.
Rode **pelo menos uma vez por semana** (ideal: domingo à noite ou segunda cedo,
antes que a "semana anterior" suma do Strava). Depois é só commitar e dar push:

```bash
git add data/weeks.json && git commit -m "atualiza ranking" && git push
```

## Publicar no GitHub Pages (org rntintas-tech)

```bash
cd rn-em-movimento
git init && git add -A && git commit -m "RN em Movimento 2.0 - ranking"
gh repo create rntintas-tech/rn-em-movimento --public --source=. --push
gh api repos/rntintas-tech/rn-em-movimento/pages -X POST \
  -f "source[branch]=main" -f "source[path]=/"
```

Site: `https://rntintas-tech.github.io/rn-em-movimento/`

> **Nota**: `data/weeks.json` contém dados de exemplo até a primeira execução do script.

## Aviso sobre o endpoint

O endpoint `GET /api/v3/clubs/{id}/leaderboard` da API oficial retorna **403**
(o Strava não expõe leaderboard de clube na API pública). A captura funcional é
feita via browser **logado** no Strava, chamando
`https://www.strava.com/clubs/{id}/leaderboard?week_offset={0|1}` com
`Accept: application/json` + `X-Requested-With: XMLHttpRequest` — o mesmo JSON
que alimenta o site. Os snapshots ficam versionados em `data/weeks.json`, então
nada se perde entre capturas.
