# Handoff — Expansão dos cadastros de Equipes e Categorias

**Data:** 18/11/2026  
**Status:** pronto para implementação na próxima sessão  
**Marco:** 2 — Cadastros  
**Não avançar para:** súmula, classificação, PDFs ou premiação nesta etapa

## 1. Objetivo

Tornar os cadastros de **Atletas, Equipes e Categorias** claros, completos e acessíveis manualmente, e ampliar a importação de atletas por CSV para criar automaticamente equipes e categorias inexistentes.

Este marco corrige três problemas de uso identificados após a entrega do marco 1:

1. O cadastro manual de categorias já existe, mas está escondido no fim da página de Configuração.
2. Equipes ainda não possuem cadastro próprio; são apenas texto livre no atleta.
3. A importação CSV cria categorias automaticamente, mas ainda não possui uma entidade de equipe para associar.

## 2. Estado atual verificado

- O marco 1 está implementado e com **11 testes passando**.
- Atletas já possuem CRUD completo, busca por nome/equipe/peito e filtros por categoria e sexo.
- Categorias possuem criação, edição e exclusão em:
  - `POST /eventos/{event_id}/categorias`
  - `POST /eventos/{event_id}/categorias/{category_id}/editar`
  - `POST /eventos/{event_id}/categorias/{category_id}/excluir`
- O formulário de categorias está no final de `app/templates/events/config.html`.
- Cada categoria cria automaticamente os grupos de classificação Masculino e Feminino.
- O campo `athletes.team` é um texto livre, sem tabela de equipes, contagem ou CRUD.
- A importação CSV aceita a coluna opcional `equipe`, mas apenas copia o texto para o atleta.
- Categorias desconhecidas no CSV já são criadas automaticamente, sem faixa etária, após confirmação.
- A tabela `results` existe no schema, mas nenhuma tela ou lógica de resultados foi implementada.

### Funções que já estavam no plano original

Súmula, classificação, PDFs e premiação **não foram esquecidas**. Elas estão nos itens 3 e 4 do escopo original e na seção “Próximas etapas” do `README.md`. Ficaram deliberadamente para depois da aprovação do modelo de dados, cadastro e baterias.

Nesta próxima sessão, implementar somente o marco 2 descrito neste documento.

## 3. Decisões já fechadas

- O CSV de atletas será a única importação desta etapa e criará automaticamente:
  - categorias inexistentes;
  - equipes inexistentes.
- Também haverá cadastro manual independente para categorias e equipes.
- Equipes e categorias são **por prova**, não globais entre eventos.
- Equipe continua **opcional** para o atleta.
- Uma equipe pode existir sem atletas.
- Uma categoria pode existir sem atletas.
- Nomes de equipes e categorias são únicos por prova, sem diferenciar maiúsculas/minúsculas.
- Excluir equipe ou categoria em uso deve ser bloqueado com mensagem clara, não gerar exclusão em cascata de atletas.
- Não haverá upload CSV separado de equipes ou categorias nesta etapa.
- Súmula, classificação, relatórios e premiação ficam fora de escopo.

## 4. Modelo de dados

### 4.1 Nova tabela `teams`

```sql
CREATE TABLE teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (event_id, name COLLATE NOCASE),
    UNIQUE (id, event_id)
);
```

### 4.2 Alteração em `athletes`

Substituir `team TEXT` por:

```sql
team_id INTEGER,
FOREIGN KEY (team_id, event_id) REFERENCES teams(id, event_id) ON DELETE RESTRICT
```

`team_id` deve aceitar `NULL` para atleta sem equipe.

### 4.3 Migração obrigatória do banco existente

O banco atual está com `PRAGMA user_version = 1`. A próxima versão deve ser `2`.

Antes de qualquer alteração destrutiva:

1. Criar backup em `backups/` usando a API `sqlite3.Connection.backup`, com nome semelhante a `triscore-pre-v2-YYYYMMDD-HHMMSS.db`.
2. Preservar IDs de atletas, peitos, baterias, posições de largada e eventuais resultados futuros.
3. Migrar os textos não vazios de `athletes.team` para `teams`, agrupando por prova e nome sem diferenciar maiúsculas/minúsculas.
4. Associar cada atleta à equipe migrada por `team_id`.
5. Remover a coluna textual antiga por reconstrução da tabela `athletes`.
6. Recriar os índices de atletas.
7. Executar `PRAGMA foreign_key_check` antes de confirmar a migração.
8. Definir `PRAGMA user_version = 2`.

Cuidados com SQLite:

- Desligar `PRAGMA foreign_keys` somente durante a reconstrução e reativar ao final.
- Preservar os vínculos de `heat_entries.athlete_id` e `results.athlete_id` com os mesmos IDs.
- Evitar colisão de equipes com nomes iguais apenas por caixa. Exemplo de agrupamento:
  `GROUP BY event_id, name COLLATE NOCASE`.
- O schema de instalação nova já deve nascer com `teams` e `athletes.team_id`, sem executar reconstrução desnecessária.
- Não deixar `PRAGMA user_version` fixo em `1` dentro de `schema.sql`.

A migração precisa ter teste automatizado próprio, construindo um banco legado, migrando e conferindo:

- contagem de atletas preservada;
- peitos preservados;
- equipes distintas migradas;
- atletas sem equipe mantendo `team_id = NULL`;
- baterias e posições preservadas;
- `PRAGMA foreign_key_check` vazio.

## 5. Serviços e API

### 5.1 Serviço de equipes

Criar `app/services/teams.py` com funções equivalentes às de categorias:

- listar equipes da prova com contagem de atletas;
- criar equipe;
- editar nome;
- excluir somente se não houver atletas vinculados;
- buscar ou criar por nome normalizado durante a importação CSV;
- validar nome obrigatório, máximo de 120 caracteres e unicidade por prova.

Sugestão de assinaturas:

```python
list_teams(connection, event_id) -> list[dict]
get_team(connection, event_id, team_id) -> dict | None
create_team(connection, event_id, name) -> int
update_team(connection, event_id, team_id, name) -> None
delete_team(connection, event_id, team_id) -> tuple[bool, str | None]
get_or_create_team(connection, event_id, name) -> dict
```

### 5.2 Rotas de equipes

Criar `app/routers/teams.py`:

- `GET /eventos/{event_id}/equipes` — página de cadastro;
- `POST /eventos/{event_id}/equipes` — criar;
- `POST /eventos/{event_id}/equipes/{team_id}/editar` — renomear;
- `POST /eventos/{event_id}/equipes/{team_id}/excluir` — excluir.

Todas as escritas devem usar transação imediata e redirecionar com mensagem de sucesso/erro.

### 5.3 Rotas de categorias

Adicionar a rota de página que falta:

- `GET /eventos/{event_id}/categorias`

Manter as rotas POST existentes ou movê-las para um router próprio, desde que as URLs públicas sejam preservadas. Todos os redirecionamentos de categoria devem apontar para a nova página de categorias, não para a configuração da prova.

### 5.4 Ajustes em atletas

Em `app/services/athletes.py`:

- trocar criação/edição de `team` por `team_id`;
- validar que a equipe pertence à mesma prova;
- permitir equipe vazia;
- usar `JOIN`/`LEFT JOIN` com `teams` nas consultas;
- manter busca por nome da equipe;
- adicionar filtro opcional por equipe na listagem.

No formulário de atleta:

- trocar o campo de texto “Equipe” por `select` com opção “Sem equipe”;
- exibir link para o cadastro de equipes;
- exibir link para o cadastro de categorias quando não houver categoria;
- manter preenchimento dos demais campos em caso de erro.

## 6. Interface e navegação

### 6.1 Navegação principal

Adicionar acesso explícito no topo para:

`Atletas · Equipes · Categorias · Baterias · Configuração`

A navegação deve continuar responsiva e com rolagem horizontal no mobile. A tela de Configuração não deve ser o único caminho para categorias.

### 6.2 Página de categorias

Criar página dedicada com formulário de criação visível no topo, não escondido abaixo da lista.

Cada categoria deve exibir:

- nome;
- idade mínima e máxima opcionais;
- contagem masculina, feminina e total;
- ações de salvar e excluir.

Manter as regras atuais:

- nome único por prova;
- idades entre 0 e 120;
- idade mínima não pode superar a máxima;
- faixa etária não bloqueia atleta, apenas gera aviso;
- criação automática dos grupos Masculino e Feminino.

### 6.3 Página de equipes

Exibir:

- formulário de criação no topo;
- lista com nome e quantidade de atletas;
- edição inline do nome;
- exclusão com confirmação e bloqueio quando houver atletas.

### 6.4 Configuração da prova

Substituir a seção extensa de categorias por um resumo com contagem e botão “Gerenciar categorias”, ou remover a duplicação. Evitar duas telas com formulários concorrentes para a mesma entidade.

## 7. Importação CSV

### 7.1 Comportamento esperado

A importação existente de atletas deve continuar aceitando a coluna opcional `equipe` e passar a:

- reutilizar equipe existente pelo nome, sem diferenciar caixa;
- criar equipe nova na confirmação quando o nome não existir;
- criar categoria nova na confirmação quando o nome não existir;
- manter `team_id = NULL` quando a equipe vier vazia;
- normalizar espaços no nome da equipe;
- rejeitar equipe acima de 120 caracteres.

### 7.2 Prévia

Na tela de prévia:

- mostrar as equipes e categorias que serão criadas;
- diferenciar “será criada” de erro de linha;
- manter o relatório CSV de erros/avisos;
- não gravar categorias ou equipes antes da confirmação.

### 7.3 Confirmação

Dentro de uma única transação:

1. revalidar linhas;
2. criar categorias pendentes;
3. criar equipes pendentes;
4. inserir atletas vinculados aos IDs corretos;
5. ignorar linhas com erro;
6. excluir o lote temporário;
7. retornar totais de importados, categorias criadas e equipes criadas.

Evitar condição de corrida entre duas abas: a transação deve ser `BEGIN IMMEDIATE`, e a unicidade de nomes deve ser garantida pelo banco.

## 8. Seeds e dados de exemplo

Atualizar `scripts/seed_demo.py` para criar as equipes antes dos atletas e associar `team_id`.

Equipes já usadas na demonstração:

- Cardume;
- Pedal Sul;
- Vento Norte;
- Independente;
- Tri Clube Central;
- All Sports;
- Escola Ativa;
- Parque Run.

O banco de exemplo atual em `data/triscore.db` deve ser migrado e permanecer abrindo com:

- 2 provas;
- 25 atletas;
- 4 baterias;
- horários e posições intactos.

Não é necessário recriar o banco para a entrega; a migração deve preservá-lo. Se houver suspeita de divergência, o seed pode ser reexecutado em um banco de teste.

## 9. Testes obrigatórios

Manter os 11 testes atuais e adicionar, no mínimo:

1. migração v1 → v2 com preservação de atletas, baterias e posições;
2. criação manual de equipe e unicidade por prova;
3. edição de equipe refletida nos atletas vinculados;
4. bloqueio de exclusão de equipe com atletas;
5. exclusão de equipe sem atletas;
6. criação manual de categoria e unicidade;
7. página de categorias acessível e formulário presente;
8. exclusão de categoria em uso bloqueada;
9. atleta manual com equipe opcional;
10. filtro de atletas por equipe;
11. CSV criando equipe e categoria automaticamente;
12. CSV reutilizando equipe/categoria existentes com diferença de caixa;
13. CSV com equipe vazia gerando `team_id = NULL`;
14. CSV com equipe/categoria inválida mantendo erro e relatório;
15. confirmação CSV transacional e contagens retornadas.

Comandos:

```bash
source .venv/bin/activate
pytest -q
```

Também executar verificação mínima de lint/sintaxe disponível:

```bash
.venv/bin/ruff check app tests scripts run.py --select F,E9,B023,UP035
```

## 10. Critérios de aceite

A próxima sessão somente deve ser considerada concluída quando:

- for possível criar, renomear e excluir equipes pela interface;
- for possível criar, editar e excluir categorias por uma página dedicada e visível;
- o atleta permitir escolher equipe opcional por `select`;
- a lista de atletas exibir e filtrar pela equipe;
- o CSV criar automaticamente equipes e categorias inexistentes;
- a prévia informar o que será criado;
- nenhuma exclusão em uso apagar atletas;
- o banco de demonstração migrar sem perda de atletas, peitos, baterias, sequência ou posições;
- todos os testes antigos e novos passarem;
- o README for atualizado;
- nenhuma funcionalidade de súmula/classificação/PDF/premiação for implementada neste marco.

## 11. Arquivos prováveis

```text
app/schema.sql
app/database.py
app/main.py
app/services/teams.py                 (novo)
app/services/events.py
app/services/athletes.py
app/services/csv_import.py
app/routers/teams.py                  (novo)
app/routers/events.py
app/routers/athletes.py
app/templates/base.html
app/templates/events/config.html
app/templates/events/categories.html  (novo)
app/templates/teams/index.html        (novo)
app/templates/athletes/form.html
app/templates/athletes/list.html
app/templates/athletes/import_preview.html
app/templates/athletes/import.html
app/static/css/app.css
scripts/seed_demo.py
tests/conftest.py
tests/test_events_athletes.py
tests/test_csv_import.py
tests/test_teams_categories.py        (novo)
tests/test_migrations.py              (novo)
examples/atletas.csv
examples/atletas_com_erros.csv
README.md
HANDOFF.md
```

## 12. Roadmap posterior

Depois da aprovação do marco 2:

1. **Súmula e resultados:** tela de lançamento, tempos em centésimos, DNF/DSQ/DNS, resumo, edição, exclusão e backup automático.
2. **Classificação:** por Categoria + Sexo, juntando baterias, status especiais no fim, desempate configurável.
3. **PDFs:** cronograma, lista de largada e relatório final.
4. **Premiação:** modo `/premiacao`, temas, animações e PDF de plano B.

## 13. Prompt para a próxima sessão

Copie e envie:

> Leia `HANDOFF.md` e implemente integralmente o **Marco 2 — Expansão dos cadastros de Equipes e Categorias**. Preserve todas as funcionalidades e testes existentes, execute a migração v1 → v2 do banco de exemplo sem perder atletas, baterias ou posições de largada, atualize o README e valide com `pytest -q`. Não implemente súmula, classificação, PDFs ou premiação nesta etapa. Ao final, apresente o resultado e aguarde aprovação antes de iniciar o marco 3.

## 14. Ambiente

- Projeto: `/home/mion/Projetos/Triscore`
- Python do ambiente virtual: `.venv`
- Banco de demonstração: `data/triscore.db`
- Execução: `source .venv/bin/activate && python run.py`
- O servidor pode estar ativo em `http://127.0.0.1:8000`; se necessário:
  `kill $(cat /tmp/triscore-live.pid)`.
- Não há repositório Git inicializado nesta pasta.
