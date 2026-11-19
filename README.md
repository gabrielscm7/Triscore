# Triscore

Aplicação web **local-first** para operação de resultados de triatlo por um único operador. Não exige login, não acessa a internet e grava todos os dados no SQLite da própria máquina.

Esta entrega contempla **todas as etapas aprovadas do escopo original**:

- modelo de dados com suporte a várias provas;
- cadastro de provas, categorias e grupos de prova;
- página dedicada para criar, editar e excluir categorias;
- cadastro de equipes por prova, com contagem de atletas e edição inline;
- CRUD de atletas com número de peito automático e equipe opcional;
- filtros de atletas por categoria, equipe e sexo;
- importação de atletas por CSV com prévia, avisos e relatório de erros;
- criação automática de equipes e categorias inexistentes na confirmação do CSV;
- montador de baterias separadas e mistas;
- divisão automática em baterias A, B, C;
- ordenação de atletas por peito, nome ou sorteio;
- ajuste manual da ordem por arrastar e soltar;
- cronograma opcional por atleta e por bateria;
- súmula com lançamento e edição de tempos em centésimos;
- status especiais DNF, DSQ e DNS;
- resumo de resultados lançados e pendentes;
- backup automático antes de cada alteração na súmula;
- classificação por categoria, reunindo atletas de todas as baterias;
- pódios separados por sexo ou pódio único misto, configurável por categoria;
- status especiais e atletas sem resultado ao final de cada grupo;
- desempate configurável por peito, nome, ordem de cadastro ou empate real;
- aviso de empate dentro das três primeiras posições de um grupo;
- exportação em PDF de cronograma, lista de largada e relatório final;
- arquivos A4 com fontes locais, paginação e cabeçalhos de tabela repetidos;
- modo `/premiacao` com pódio em tela cheia, revelação animada e atalhos de teclado;
- pódio com suporte a empates reais e posições não ocupadas;
- editor de tema por prova com presets, cores personalizadas e validação de contraste;
- banner, imagem de fundo e fonte personalizada por upload local;
- três layouts de slide com prévia ao vivo no editor;
- textos editáveis por categoria, abertura e encerramento;
- PDF de contingência da premiação refletindo tema, layout e imagens;
- seed descartável com resultados fictícios para validação;
- auditoria offline de templates, CSS, JS e SVG;
- separação explícita entre ambiente real e ambiente de teste;
- backup manual do banco e dos PDFs para pendrive ou pasta escolhida;
- pacote portátil com wheels para instalação sem internet;
- roteiro de ensaio, checklist final e smoke test automatizado.

A prova é **contra o relógio, com largada individual**. O sistema não possui cronômetro automático: os tempos finais são lançados manualmente na súmula. A classificação é feita por categoria, com pódios separados ou mistos conforme a configuração de cada categoria.

## Requisitos

- **Ubuntu 24.04 LTS x86_64** para o pacote validado.
- Python **3.12** (o pacote portátil já inclui `.venv` e wheels cp312).
- Navegador atualizado.
- Nenhuma conexão com a internet durante a operação.
- ReportLab e Pillow para geração local dos PDFs e tratamento das imagens da premiação.

Todos os assets visuais, inclusive as fontes usadas na interface e nos PDFs, são locais.

## Instalação no Ubuntu (recomendada)

O pacote portátil é um `.tar.gz` que já contém `.venv`, `wheels/` e `debs/`:

```bash
tar -xzf triscore-portatil-*.tar.gz
cd triscore-portatil-*
./verificar.sh
./TriScore.sh
```

Se o Python 3.12/venv não estiver disponível no notebook:

```bash
sudo ./instalar_debs.sh
```

### Instalação a partir do código-fonte

```bash
cd Triscore
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./TriScore.sh
```

## Pasta de dados externa

Banco, backups, PDFs, uploads e logs ficam em `./dados`, ao lado do app:

```text
dados/
├── banco/triscore.db
├── backups/
├── exports/
├── uploads/premiacao/<nome-do-banco>/<event_id>/
├── logs/
└── teste/
    ├── banco/triscore-teste.db
    ├── backups/
    ├── exports/
    ├── uploads/premiacao/
    └── logs/
```

Para usar outra pasta:

```bash
TRISCORE_DATA_DIR=/caminho/seguro/triscore ./TriScore.sh
```

A variável `TRISCORE_DB` continua disponível para apontar um banco específico.
Na primeira execução pelo launcher, o layout antigo (`data/`, `backups/`,
`exports/` e `data/premiacao/`) é copiado para `dados/` sem remover os originais.
O manifesto fica em `dados/.migracao-legado.json`.

## Início rápido com dados de exemplo

Esta entrega já inclui o banco migrado para o schema v6 em `dados/banco/triscore.db` (o layout antigo é copiado automaticamente pelo launcher). As duas provas criadas pelo seed são:

- **Triatlo das Montanhas 2026**: 21 atletas, 4 categorias, equipes e 4 baterias já montadas, com cronograma e uma bateria mista.
- **Copa Cidade 2026**: uma segunda prova, com categorias, equipes e atletas, para demonstrar a troca de prova.
- Dois atletas da prova principal estão propositalmente fora da faixa etária para demonstrar o aviso não bloqueante.

Provas ou cadastros adicionais feitos localmente são preservados pela migração e não são recriados pelo seed.

Com o ambiente virtual ativo:

```bash
./TriScore.sh
```

O launcher inicia o servidor somente em `127.0.0.1`, escolhe outra porta se a 8000 estiver ocupada, aguarda o health check e abre o navegador. Os logs ficam em `dados/logs/`. O botão **Encerrar** na interface e o `Ctrl+C` encerram o servidor e criam um backup automático do banco.

Se o banco estiver vazio ou tiver sido apagado, recrie a demonstração com:

```bash
python scripts/seed_demo.py
```

### Dados descartáveis para validar a classificação

O script abaixo cria um banco separado com empates, DNF, DSQ, DNS, atleta sem resultado e uma categoria com pódio misto:

```bash
python scripts/seed_test_results.py --reset
./TriScore.sh --modo teste --no-browser
```

O banco de teste fica em `dados/teste/banco/triscore-teste.db` e pode ser apagado a qualquer momento. Use `--reset` para recriá-lo do zero. Backups, PDFs e arquivos de premiação do teste ficam dentro de `dados/teste/`. A interface mostra uma faixa vermelha **MODO TESTE** em todas as telas.

Para começar do zero, apague `dados/banco/triscore.db` (e os arquivos `-wal`/`-shm`, se existirem) e inicie a aplicação sem executar o seed.

## Preparação para o evento offline

### Auditoria offline

```bash
python scripts/audit_offline.py
```

O comando varre templates, CSS, JS e SVG atrás de URLs externas. A aplicação não
usa CDN, Google Fonts, bibliotecas de ícones remotas ou chamadas de rede. O único
`http://` encontrado no projeto é o namespace `xmlns` do SVG, que não gera
requisição. Um teste automatizado (`tests/test_offline_audit.py`) repete essa
verificação a cada execução do `pytest`.

### Ambientes separados

| Ambiente | Comando | Porta padrão | Banco | Backups | PDFs e mídia |
|---|---|---|---|---|---|
| Real | `./TriScore.sh` | 8000 | `dados/banco/triscore.db` | `dados/backups/` | `dados/exports/` e `dados/uploads/premiacao/` |
| Teste | `./TriScore.sh --modo teste` | 8100 | `dados/teste/banco/triscore-teste.db` | `dados/teste/backups/` | `dados/teste/exports/` e `dados/teste/uploads/premiacao/` |

- O ambiente de teste exibe a faixa **MODO TESTE** em todas as páginas, inclusive na premiação.
- O ambiente real não exibe a faixa.
- Sem `--confirmar-banco`, o iniciador recusa abrir um banco de teste como real e vice-versa.
- As portas padrão são diferentes e a busca automática fica em faixas separadas (`8000–8099` e `8100–8199`).
- O console mostra o banco, a pasta de backups e a pasta de PDFs antes de abrir o navegador.

Para trocar de ambiente, pare o servidor com `Ctrl+C` e use o comando do outro ambiente. Não abra duas instâncias sobre o mesmo banco.

### Backup manual

Na tela **Backup** (link no topo), informe uma pasta existente, como um pendrive
montado, e clique em **Backup agora**. A aplicação cria uma subpasta
`triscore-backup-<ambiente>-AAAAMMDD-HHMMSS` com:

- cópia consistente do banco SQLite feita com a API de backup do SQLite;
- todos os PDFs de `dados/exports/`;
- banners, fundos e fontes da premiação;
- `manifest.json` com data, ambiente e contagens.

O backup automático antes de cada alteração da súmula continua sendo gravado na
pasta de backups do ambiente. O botão é uma cópia adicional para outro destino.

### Pacote portátil e wheelhouse para Ubuntu 24.04

```bash
./build.sh
```

O `build.sh` usa Docker `ubuntu:24.04` para gerar o alvo correto:

- 29 wheels `cp312`/manylinux, sem fontes e sem wheels cp314;
- `.venv` Python 3.12 pré-criada com `--copies`;
- `debs/` com `python3.12-venv` e dependências para instalação offline;
- `BUILD-INFO.txt`, `SHA256SUMS` e o `.tar.gz` em `dist/`.

O build falha se alguma dependência exigir compilação. O `iniciar.bat` não é
gerado; o alvo é Ubuntu. Para conferir o empacotamento sem baixar wheels, use
`./build.sh --skip-wheels` apenas em desenvolvimento.

### Binário opcional com PyInstaller

```bash
./scripts/build_binario.sh
```

Gera um pacote onedir em `dist/triscore-binario-*`, construído em
`ubuntu:24.04` x86_64 com Python 3.12. Templates, static e schema são incluídos.
O binário usa `dados/` ao lado do executável e o launcher continua sendo o ponto
de entrada. Consulte `docs/BUILD.md`.

### Verificação do ambiente

```bash
./verificar.sh
```

Confere Ubuntu 24.04, arquitetura x86_64, Python 3.12, módulo venv,
dependências, wheelhouse, geração de PDF com ReportLab, porta livre, escrita em
`dados/` e o estado da internet (informativo). A saída é `OK` ou `FALHA` por item.

### Roteiro de ensaio e checklist

- [`docs/ROTEIRO_ENSAIO.md`](docs/ROTEIRO_ENSAIO.md) — passo a passo do fluxo completo, com checklist antes e depois de cada etapa.
- [`docs/CHECKLIST_FINAL.md`](docs/CHECKLIST_FINAL.md) — checklist de conferência final para levar ao evento.

### Smoke tests

```bash
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/smoke_launcher.py
```

O primeiro cria um banco temporário de teste, cadastra prova, categorias, equipe
e atletas fictícios, gera baterias, lança tempos com empate e DNF, confere a
classificação, gera os quatro PDFs, executa o backup manual e bloqueia conexões
externas.

O `smoke_launcher.py` sobe o servidor pelo `TriScore.sh`, chama `/health`, cria
uma prova, gera o PDF de cronograma, chama `POST /encerrar` e confirma o backup
de encerramento. É o teste de aceitação do pacote portátil.

## Operação em evento

### 1. Criar e configurar a prova

Em **Provas**, crie a prova e abra a configuração.

Na configuração:

- defina nome, data e local;
- informe o limite de atletas por bateria;
- ative o cronograma, se desejar imprimir horários previstos;
- defina horário inicial, intervalo entre atletas e intervalo entre baterias.

O cadastro de categorias fica na página **Categorias**, acessível pela navegação principal. A configuração mostra apenas um resumo e o botão **Gerenciar categorias**.

Cada categoria cria automaticamente os grupos internos **Masculino** e **Feminino**, usados no cadastro e nas baterias. Na classificação, a categoria pode usar **pódios separados** ou **pódio único misto**. A faixa etária serve somente para gerar avisos: nunca bloqueia o cadastro. Excluir uma categoria com atletas ou baterias é bloqueado.

### 2. Cadastrar equipes

Em **Equipes**, crie, renomeie ou exclua equipes da prova atual.

- A equipe é opcional para o atleta.
- Uma equipe pode existir sem atletas.
- O nome deve ser único na prova, sem diferenciar maiúsculas e minúsculas, e ter no máximo 120 caracteres.
- Renomear uma equipe atualiza automaticamente a exibição dos atletas vinculados.
- A exclusão é bloqueada quando a equipe possui atletas e nunca remove atletas em cascata.
- O mesmo nome pode ser usado em provas diferentes.

### 3. Cadastrar atletas

Em **Atletas**, use **Novo atleta** ou **Importar CSV**.

- O número de peito pode ser informado ou deixado em branco para geração automática.
- O peito deve ser único dentro da prova.
- A equipe é escolhida em um seletor com a opção **Sem equipe**.
- A listagem permite buscar por nome, equipe ou peito e filtrar por categoria, equipe e sexo.
- Idade fora da faixa da categoria aparece como aviso em amarelo.
- Alterar a categoria ou o sexo de um atleta que já está em uma bateria remove o atleta daquela bateria, com aviso.
- Excluir um atleta também reorganiza as posições da bateria em que ele estava.

### 4. Importar CSV

O CSV deve ter cabeçalho. São aceitos separadores `;`, `,` e tabulação, com codificação UTF-8 ou Windows-1252.

Cabeçalhos reconhecidos:

| Campo | Variações aceitas |
|---|---|
| Nome | `nome`, `atleta`, `nome_atleta`, `nome_completo` |
| Idade | `idade`, `anos` |
| Categoria | `categoria`, `grupo`, `faixa`, `faixa_etaria` |
| Sexo | `sexo`, `genero` |
| Equipe (opcional) | `equipe`, `time`, `clube`, `associacao`, `agremiacao` |
| Peito (opcional) | `peito`, `numero_peito`, `n_de_peito`, `numero` |

Sexo aceita `M`, `F`, `masculino` ou `feminino`.

Fluxo:

1. Envie o arquivo.
2. Confira a prévia linha a linha e as listas de equipes e categorias que serão criadas.
3. Baixe o relatório CSV de erros e avisos, se necessário.
4. Confirme para gravar as linhas válidas e com aviso.

Linhas com erro não são importadas e não criam equipes nem categorias. Na confirmação:

- equipes existentes são reutilizadas sem diferenciar maiúsculas e minúsculas;
- equipes novas são criadas com o nome normalizado;
- categorias desconhecidas são criadas sem faixa etária;
- equipe vazia mantém o atleta com **Sem equipe**;
- equipes com mais de 120 caracteres são rejeitadas na linha e aparecem no relatório.

Toda a confirmação ocorre em uma única transação. O resumo final informa atletas importados, linhas ignoradas e quantas categorias e equipes foram criadas.

Exemplos:

- `examples/atletas.csv` — arquivo válido, com reutilização de equipe por diferença de caixa e um atleta sem equipe;
- `examples/atletas_com_erros.csv` — demonstra idade inválida, sexo inválido, categoria ausente, peito duplicado, equipe acima de 120 caracteres e avisos.

### 5. Montar baterias

Em **Baterias**, os cartões superiores mostram a contagem total e disponível de cada grupo Masculino, Feminino e Misto.

Use **Gerar baterias**:

- escolha categoria e modalidade;
- escolha a ordenação inicial;
- o limite configurado divide o grupo em A, B, C etc.;
- somente atletas ainda não alocados entram na geração.

Se já existirem baterias para a mesma categoria e modalidade, o sistema não duplica a geração. Use **Nova bateria vazia** e mova atletas manualmente, ou exclua as baterias existentes para gerar novamente.

**Bateria mista** reúne atletas masculinos e femininos da mesma categoria. Ela não cria um grupo único de classificação: o masculino e o feminino continuam sendo grupos separados.

### 6. Ordem de largada

- Arraste o marcador no cabeçalho de uma bateria para alterar a sequência da prova.
- Arraste um atleta para outra bateria para movê-lo.
- Solte um atleta na área **Não alocados** para retirá-lo da largada.
- Arraste um atleta dentro da bateria para ajustar a posição exata.
- Use o seletor do rodapé da bateria para reordenar por peito, nome ou sorteio.

A ordem é salva imediatamente. A interface recarrega após cada movimentação para recalcular contagens e horários.

Restrições aplicadas:

- uma bateria não aceita atleta de outra categoria;
- uma bateria não mista não aceita o sexo oposto;
- uma bateria cheia não recebe outro atleta;
- cada atleta pode estar em apenas uma bateria.

### 7. Cronograma

O cronograma é opcional. Quando ativo:

```text
horário previsto do atleta = início da bateria + posição × intervalo entre atletas
início da próxima bateria = última largada prevista + intervalo entre baterias
```

Baterias vazias não consomem horário. Os horários aparecem na tela; a exportação em PDF será implementada na etapa de relatórios.

### 8. Súmula e resultados

Em **Súmula**, lance o resultado de cada atleta diretamente na lista, que segue a ordem de bateria e posição de largada.

Tempos aceitos:

- `mm:ss` — por exemplo, `42:10`;
- `hh:mm:ss` — por exemplo, `1:02:03`;
- `mm:ss.cc` ou `hh:mm:ss.cc` — por exemplo, `42:10.50` ou `1:02:03.45`.

Os centésimos são armazenados como inteiros no banco. Também é possível registrar os status especiais **DNF** (não finalizou), **DSQ** (desclassificado) e **DNS** (não largou). Esses status não aceitam tempo.

Salvar novamente no mesmo atleta edita o resultado existente. A ação **Excluir** remove apenas o lançamento, sem excluir o atleta. O topo da página resume quantos resultados foram lançados, quais são válidos, quantos são especiais e quantos estão pendentes.

Antes de cada gravação ou exclusão na súmula, a aplicação cria automaticamente um backup em `dados/backups/triscore-pre-sumula-YYYYMMDD-HHMMSS-ffffff.db` no ambiente real (ou `dados/teste/backups/` no ambiente de teste). O botão **Backup agora** faz uma cópia adicional do banco e dos PDFs para a pasta escolhida.

### 9. Classificação

Em **Classificação**, os atletas são reunidos por categoria, independentemente da bateria em que largaram.

Cada categoria define o formato do pódio:

- **Pódios separados**: grupos Masculino e Feminino;
- **Pódio único misto**: um único grupo, com atletas de ambos os sexos.

Regras de ordenação:

- Atletas com tempo válido são ordenados pelo menor tempo.
- Empates de tempo usam o critério configurado na própria página:
  - menor número de peito;
  - nome do atleta;
  - ordem de cadastro;
  - empate real, em que tempos idênticos dividem a mesma posição (`1º`, `2º`, `2º`, `4º`).
- O critério fica salvo na prova e é usado nas próximas aberturas da página.
- Apenas atletas com tempo válido recebem posição.
- Status DNF, DSQ e DNS aparecem ao final do grupo, seguidos pelos atletas ainda sem resultado.
- Cada grupo mostra quantos atletas foram classificados, quantos têm status especial e quantos estão pendentes.
- Um aviso é exibido quando há empate de tempo dentro das três primeiras posições do grupo, mesmo quando outro critério separa a ordem visual.

A classificação é derivada dos resultados da súmula; não há gravação de posições finais separada.

## 10. PDFs

Os PDFs são gerados localmente com ReportLab, em A4, usando as fontes Fira Sans e o logo locais. Não há acesso à internet durante a geração.

Botões de exportação:

- **Baterias**:
  - **Exportar cronograma PDF**;
  - **Lista de largada PDF**.
- **Classificação**:
  - **Exportar relatório final PDF**.

Conteúdo:

- **Cronograma**: ordem das baterias, categoria, grupo, quantidade de atletas, início previsto e última largada.
- **Lista de largada / súmula em branco**: uma seção por bateria, com posição, peito, nome, equipe e campo de tempo em branco.
- **Relatório final**: capa com logo e dados da prova, resumo de classificados, especiais e pendentes, classificação por grupo e página de observações.

Os arquivos são salvos no diretório `dados/exports/` da instância principal com o padrão:

```text
prova_tipo_data.pdf
```

Exemplo: `triatlo_das_montanhas_2026_relatorio_final_2026-11-18.pdf`.

As tabelas repetem o cabeçalho ao mudar de página, e todas as páginas numeradas recebem cabeçalho com o nome da prova e o tipo de relatório.

## 11. Premiação

O modo de apresentação fica em `/premiacao`, com seletor de provas, e em `/premiacao/{event_id}` para acesso direto. O link **Premiação** também aparece na navegação da prova e na página de Classificação.

- O pódio é derivado da classificação, sem gravar uma segunda lista de campeões.
- Pódios separados e pódios mistos são suportados conforme a configuração da categoria.
- Empates reais mostram todos os atletas empatados na mesma posição; posições sem atletas ficam vazias.
- DNF, DSQ, DNS e atletas sem resultado não entram no pódio.
- A sequência inclui **abertura**, categorias com pódio e **encerramento**.
- A revelação segue a ordem **3º → 2º → 1º**, com controles para reiniciar e trocar de slide.
- Atalhos: setas para trocar de slide, `Espaço` para revelar, `R` para reiniciar, `F` para tela cheia.
- A apresentação respeita `prefers-reduced-motion` e permite desativar animações.
- O conteúdo útil fica dentro de 90% da viewport, com fontes dimensionadas para projeção.

### Tema e acabamento visual

O tema é configurado pela engrenagem **Configurar tema**, dentro da própria apresentação, e fica salvo por prova na tabela `award_settings`.

- Presets: Clássico, Claro e Escuro.
- Tema personalizado com cores de fundo, texto e destaque.
- Validação hexadecimal e contraste mínimo de `4.5:1` para texto e `3:1` para destaque.
- Layouts: Clássico centralizado, Moderno com faixa lateral e Destaque com números grandes.
- Prévia ao vivo no editor para cores, layout, imagens e opacidade.
- Opções para exibir/ocultar o logo e ativar/desativar animações.

Uploads locais por prova:

- banner no topo dos slides;
- imagem de fundo com opacidade e escurecimento configuráveis;
- fonte de destaque WOFF2 ou TTF, com fallback para Fira Sans;
- imagens PNG, JPEG ou WebP de até 8 MB;
- fontes de até 3 MB.

Os arquivos ficam em `dados/uploads/premiacao/<nome-do-banco>/<event_id>/`. A substituição remove o arquivo antigo com segurança.

### Textos editáveis

- **Editar texto** altera o título e a frase de chamada do slide da categoria atual.
- Os textos são persistidos por categoria e grupo.
- Campos vazios restauram o texto padrão.
- Abertura e encerramento têm título e frase editáveis no painel de tema.

### PDF de plano B

O botão **PDF de premiação** gera `dados/exports/prova_premiacao_data.pdf` com capa, logo, banner, fundo, tema, layout escolhido, textos de abertura/encerramento e roteiro por grupo de pódio. O PDF inclui posições, peito, nome, equipe e tempo, com fallback para Fira Sans quando a fonte enviada for WOFF2.

## Dados e arquivos

| Caminho | Conteúdo |
|---|---|
| `dados/banco/triscore.db` | Banco SQLite principal |
| `dados/banco/triscore.db-wal` / `-shm` | Arquivos transitórios do SQLite |
| `dados/backups/` | Backups automáticos e de encerramento do ambiente real |
| `dados/exports/` | PDFs gerados pela instância real |
| `dados/uploads/premiacao/` | Banner, fundo e fonte enviados |
| `dados/logs/` | Logs do launcher e da aplicação |
| `dados/teste/` | Banco, backups, PDFs, uploads e logs do ambiente de teste |
| `dados/.migracao-legado.json` | Manifesto da migração do layout antigo |
| `examples/` | CSV de demonstração |
| `scripts/seed_demo.py` | Carga opcional de dados de exemplo |
| `scripts/seed_test_results.py` | Seed descartável com resultados fictícios |
| `scripts/migrar_dados.py` | Migração manual do layout antigo para `dados/` |
| `scripts/audit_offline.py` | Auditoria de URLs externas |
| `scripts/build_portable.py` | Geração do pacote portátil para Ubuntu 24.04 |
| `scripts/build_binario.sh` | Build opcional com PyInstaller onedir |
| `scripts/smoke_test.py` | Smoke test do fluxo funcional completo |
| `scripts/smoke_launcher.py` | Smoke test pelo launcher com health, PDF e encerramento |
| `TriScore.sh` | Launcher principal |
| `verificar.sh` | Verificação do ambiente Ubuntu/Python/PDF/porta/dados |
| `docs/` | Roteiro de ensaio, checklist final e build |

O banco usa chaves estrangeiras, transações e restrições de unicidade. Para fazer uma cópia manual segura com a aplicação fechada, copie o arquivo `.db`.

### Migração de schema

O schema atual é a versão **6**.

Ao abrir um banco versão 1, a aplicação executa em sequência:

1. backup `dados/backups/triscore-pre-v2-YYYYMMDD-HHMMSS-ffffff.db`;
2. migração dos textos de `athletes.team` para `teams`;
3. preservação de IDs, peitos, atletas, baterias, posições de largada, resultados e sequências;
4. validação de chaves estrangeiras e `PRAGMA user_version = 2`;
5. backup `triscore-pre-v3-...`, inclusão do desempate em `events` e `PRAGMA user_version = 3`;
6. migrações para as versões 4, 5 e 6, com backups `triscore-pre-v4-...`, `triscore-pre-v5-...` e `triscore-pre-v6-...`.

Ao abrir um banco versão 2, a aplicação cria `dados/backups/triscore-pre-v3-...`, adiciona o critério de desempate e define `PRAGMA user_version = 3`.

Ao abrir um banco versão 3, a aplicação cria `dados/backups/triscore-pre-v4-...`, reconstrói a tabela `events` para aceitar o desempate real, adiciona o modo de classificação às categorias, valida as chaves estrangeiras e define `PRAGMA user_version = 4`.

Ao abrir um banco versão 4, a aplicação cria `dados/backups/triscore-pre-v5-...`, adiciona a tabela `award_settings`, valida as chaves estrangeiras e define `PRAGMA user_version = 5`.

Ao abrir um banco versão 5, a aplicação cria `dados/backups/triscore-pre-v6-...`, adiciona layouts, imagens, fonte, textos de abertura/encerramento e a tabela `award_slide_texts`, valida as chaves estrangeiras e define `PRAGMA user_version = 6`.

As migrações usam `sqlite3.Connection.backup` e preservam eventos, categorias, equipes, atletas, baterias, posições, resultados e configurações. Instalações novas já nascem na versão 6, sem reconstrução. Versões futuras desconhecidas são recusadas. A súmula usa backups automáticos próprios antes de cada alteração de resultado.

## Testes

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

A suíte cobre cadastro de provas, atletas, equipes e categorias; unicidade por prova; equipe opcional e filtro por equipe; validações; importação e relatório CSV com criação automática e rollback transacional; migrações v1 → v2 → v3 → v4 → v5 → v6 com preservação de dados; divisão de baterias, grupos mistos, movimentação, reordenação, cronograma e exclusões com reorganização; parsing e formatação de tempos, lançamento e edição de resultados, status especiais, resumo da súmula e backups automáticos; classificação por categoria, pódio separado ou misto, ordem de status, empate real, aviso de empate no pódio e os quatro critérios de desempate; geração dos PDFs, nomes de arquivo, A4, logo da capa e repetição de cabeçalhos; premiação com empates, categorias sem pódio, temas persistidos, validação de contraste, layouts, banner, fundo, fonte, textos editáveis, abertura/encerramento, PDF de plano B, uploads válidos/inválidos, substituição, remoção e persistência dos arquivos; o seed descartável de resultados; a auditoria offline; a separação dos ambientes real/teste; o backup manual; e o smoke test do fluxo completo com bloqueio de rede externa.

## Estrutura

```text
Triscore/
├── TriScore.sh               # launcher Linux/Ubuntu
├── iniciar.sh                # alias do launcher
├── TriScore.desktop          # atalho GNOME
├── instalar_atalho.sh        # cria atalho confiável em ~/Desktop
├── verificar.sh              # checagem de ambiente
├── build.sh                  # gera .tar.gz portátil
├── run.py                    # servidor local, porta, health e encerramento
├── app/
│   ├── paths.py              # caminhos externos e suporte a PyInstaller
│   ├── data_migration.py     # migração do layout antigo para dados/
│   ├── main.py               # aplicação FastAPI
│   ├── database.py           # conexão, transações e inicialização
│   ├── schema.sql            # modelo SQLite
│   ├── routers/              # provas, cadastros, baterias, súmula, classificação, PDFs, premiação e sistema
│   ├── services/             # regras de negócio, resultados, classificação, PDFs e premiação
│   ├── templates/            # páginas Jinja2
│   └── static/               # CSS, JS, fontes e logo
├── examples/                 # arquivos CSV de exemplo
├── scripts/                  # seeds, migração, build, auditoria e smoke tests
├── tests/                    # testes automatizados
├── docs/                     # roteiro, checklist e build
├── dados/                    # dados externos (gerado; não versionar)
└── dist/                     # pacotes portáteis e binários gerados
```

## Atalho na área de trabalho (GNOME)

O arquivo `TriScore.desktop` acompanha o projeto/pacote. Para instalar um atalho
confiável em `~/Desktop`:

```bash
./instalar_atalho.sh
```

Se o GNOME exibir o aviso de atalho não confiável, clique com o botão direito no
arquivo e escolha **Allow Launching**, ou execute:

```bash
chmod +x ~/Desktop/Triscore.desktop
gio set ~/Desktop/Triscore.desktop metadata::trusted true
```

## Solução de problemas

| Sintoma | Ação |
|---|---|
| `Python 3.12 nao encontrado` | `sudo ./instalar_debs.sh` |
| `Modulo venv ausente` | `sudo ./instalar_debs.sh` e rode `./TriScore.sh` novamente |
| `.venv` inválido ou Python diferente de 3.12 | Apague apenas `.venv/` e rode o launcher; ele recria a partir de `wheels/` |
| Porta ocupada | O launcher escolhe 8001–8099 automaticamente; se necessário, `--port 8123` |
| Navegador não abre | Acesse a URL mostrada no terminal e no log |
| Atalho não abre | Marque como confiável no GNOME (seção acima) |
| PDF não gera | Rode `./verificar.sh`; ReportLab/Pillow vêm das wheels, sem Pango/Cairo |
| Banco corrompido | Feche o app e restaure o `.db` mais recente de `dados/backups/` |
| Dados antigos | Rode `python3 scripts/migrar_dados.py` e confira `dados/.migracao-legado.json` |
| Logs | `dados/logs/triscore-*.log` e `dados/logs/launcher-*.log` |

## Validação do pacote

O build portátil é feito em `ubuntu:24.04` x86_64 com Python 3.12. O arquivo
`BUILD-INFO.txt` registra a versão real do Ubuntu, arquitetura, Python, glibc,
PyInstaller (quando aplicável) e contagem de wheels. A aceitação é executada em
contêiner `ubuntu:24.04` limpo, com `--network none`, extraindo o `.tar.gz` e
rodando `verificar.sh`, o launcher, o smoke test e o encerramento. O resultado
real dessa execução fica registrado abaixo e em `docs/CHECKLIST_FINAL.md`.

### Resultado do build e da aceitação

Preenchido automaticamente na execução de validação desta entrega:

Execução de 19/11/2026:

```text
Imagem: ubuntu:24.04 (sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8)
Build: Ubuntu 24.04.5 LTS x86_64, Python 3.12.3, glibc 2.39
Wheels: 29 (cp312/manylinux, sem fontes, sem cp314)
Venv: Python 3.12.3
Tar.gz: triscore-portatil-*.tar.gz (63 MB)
SHA256: consultar o .tar.gz.sha256 gerado ao lado
Rede da aceitação: --network none
Verificação: RESULTADO OK (0 falhas)
Smoke launcher: porta 8100, health 200, PDF 58.880 bytes,
  POST /encerrar 200, processo código 0,
  backup triscore-teste-encerramento-*.db
Ctrl+C: backup de encerramento confirmado
Porta ocupada: 8100 ocupada -> launcher usou 8101
Binário PyInstaller: --help OK, health 200, Ctrl+C com backup OK
```

Para repetir:

```bash
./build.sh
./scripts/aceitacao_ubuntu.sh dist/triscore-portatil-*.tar.gz
```

## Segurança e operação offline

- O servidor escuta exclusivamente em `127.0.0.1`.
- Não há login, telemetria, CDN, fontes externas ou chamadas de rede.
- Use `python scripts/audit_offline.py` antes do evento para repetir a varredura.
- O ambiente de teste é isolado por faixa **MODO TESTE**, porta e pastas próprias.
- Não exponha a porta usada para a rede local ou internet.
- Use sempre uma única instância da aplicação sobre o mesmo banco.

## Escopo concluído

O escopo funcional original foi concluído: cadastros, importação, baterias, cronograma, súmula, classificação, relatórios PDF e premiação.

A tabela `results` armazena os tempos finais em centésimos e os status especiais. A classificação e o pódio são calculados em tempo real a partir desses resultados; não há cronometragem automática nem gravação separada de posições finais.

O [`HANDOFF.md`](HANDOFF.md) registra o histórico do Marco 2, já concluído.
