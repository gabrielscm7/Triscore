# Triscore no Ubuntu 24.04 — comandos

Guia rápido para instalar, iniciar, validar e encerrar o Triscore no Ubuntu.

## 1. Opção A — usar o pacote portátil (recomendado, sem internet)

Copie o arquivo `triscore-portatil-*.tar.gz` para o notebook Ubuntu. Depois:

```bash
cd ~
tar -xzf triscore-portatil-*.tar.gz
cd triscore-portatil-*
```

Verifique o ambiente:

```bash
./verificar.sh
```

Se aparecer `FALHA` por falta de Python 3.12/venv, instale os pacotes offline:

```bash
sudo ./instalar_debs.sh
./verificar.sh
```

Inicie o Triscore:

```bash
./TriScore.sh
```

O navegador abre em `http://127.0.0.1:8000` (ou outra porta livre).
Para encerrar, use o botão **Encerrar** na interface ou pressione `Ctrl+C`
no terminal. O banco é copiado automaticamente para `dados/backups/`.
Veja também a seção [Fechar o servidor](#6-fechar-o-servidor).

Modo teste:

```bash
./TriScore.sh --modo teste
```

## 2. Opção B — primeira instalação por git clone

Requer internet nesta etapa. O clone não inclui `wheels/`; portanto, o launcher
instala as dependências pelo índice do pip.

```bash
sudo apt update
sudo apt install -y git python3.12 python3.12-venv
cd ~
git clone https://github.com/gabrielscm7/Triscore.git
cd Triscore
./TriScore.sh
```

Na primeira execução, o launcher:

1. cria o ambiente em `.venv.tmp`;
2. instala `requirements.txt` pelo índice do pip;
3. valida os imports de `uvicorn`, `fastapi`, `jinja2`, `multipart`,
   `reportlab` e `PIL`;
4. só depois renomeia `.venv.tmp` para `.venv`.

Se a instalação ou a validação falhar, o temporário é apagado e nenhum `.venv`
parcial é deixado. Sem internet, a mensagem indicará a falha e o comando para
tentar novamente. Conecte-se à rede e execute `./TriScore.sh` outra vez. Para
instalação totalmente offline, use o pacote portátil com `wheels/`.

Para rodar também os testes e smoke tests, pare o servidor com `Ctrl+C` e
instale as dependências de desenvolvimento:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

## 3. Opção C — gerar o pacote portátil no Ubuntu

Requer Docker e internet na máquina de build.

```bash
sudo apt update
sudo apt install -y docker.io git
sudo usermod -aG docker "$USER"
```

Saia da sessão e entre novamente para aplicar o grupo Docker. Depois:

```bash
git clone https://github.com/gabrielscm7/Triscore.git
cd Triscore
./build.sh
```

O pacote será criado em:

```text
dist/triscore-portatil-*.tar.gz
dist/triscore-portatil-*.tar.gz.sha256
```

Teste a aceitação em Ubuntu limpo e sem rede:

```bash
./scripts/aceitacao_ubuntu.sh dist/triscore-portatil-*.tar.gz
```

## 4. Dados, backups e logs

Todos os dados ficam em `dados/`, fora do código:

```text
dados/banco/triscore.db
dados/backups/
dados/exports/
dados/uploads/premiacao/
dados/logs/
dados/teste/
```

Para usar outra pasta:

```bash
TRISCORE_DATA_DIR=/mnt/pendrive/triscore ./TriScore.sh
```

Para fazer backup manual:

1. Abra **Backup** no topo da interface.
2. Informe uma pasta existente, como um pendrive montado.
3. Clique em **Backup agora**.

Logs:

```bash
tail -f dados/logs/triscore-*.log
```

## 5. Atalho na área de trabalho

```bash
./instalar_atalho.sh
```

Se o GNOME pedir confirmação:

```bash
chmod +x ~/Desktop/Triscore.desktop
gio set ~/Desktop/Triscore.desktop metadata::trusted true
```

Ou clique com o botão direito no atalho e escolha **Allow Launching**.

O atalho inicia o servidor com `setsid` e `Terminal=false`, em uma sessão
desacoplada do terminal. Os logs continuam em `dados/logs/`.

## 6. Fechar o servidor

Use sempre uma destas opções:

- **Interface:** clique em **Encerrar**. É o método recomendado quando o app foi
  aberto pelo atalho da área de trabalho.
- **Terminal:** pressione `Ctrl+C` no terminal em que o `./TriScore.sh` está
  rodando.
- **Fechamento do terminal:** o launcher trata `SIGHUP` como `SIGINT`/`SIGTERM`,
  encerra o servidor e cria o backup automático.
- **Atalho da área de trabalho:** o servidor roda desacoplado. Fechar ou
  minimizar o navegador não encerra o servidor; use o botão **Encerrar**.

O backup de encerramento é gravado em:

```text
dados/backups/                 # ambiente real
dados/teste/backups/           # ambiente de teste
```

Se precisar encerrar pelo terminal, envie `SIGINT`, nunca `SIGKILL`, para
preservar o backup:

```bash
pgrep -af "$HOME/Triscore/run.py"
kill -INT PID_ENCONTRADO
```

## 7. Testes

Com o `.venv` instalado:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/smoke_launcher.py
```

## 8. Atualizar com git pull sem perder dados

Seus dados em `dados/` não são versionados e permanecem intactos durante o
`git pull`. Ainda assim, faça um backup antes e preserve alterações locais com
`git stash`.

1. Feche o servidor pelo botão **Encerrar** ou com `Ctrl+C`.
2. Faça uma cópia dos dados fora do repositório:

```bash
cd ~/Triscore
STAMP="$(date +%Y%m%d-%H%M%S)"
cp -a dados "$HOME/triscore-dados-antes-pull-$STAMP"
```

Também é possível usar **Backup > Backup agora** antes de fechar o app, caso
queira copiar banco e PDFs para outra pasta ou pendrive.

3. Confira as alterações locais e guarde-as em `git stash` apenas se existirem:

```bash
git status --short
if [[ -n "$(git status --porcelain)" ]]; then
  git stash push -u -m "antes-do-git-pull-$STAMP"
  STASHED=1
else
  STASHED=0
fi
```

O `-u` não inclui `dados/`, que é ignorado pelo Git.

4. Atualize sem criar um merge inesperado:

```bash
git pull --ff-only
```

5. Restaure as alterações locais somente se elas foram guardadas:

```bash
if [[ "${STASHED:-0}" -eq 1 ]]; then
  git stash pop
fi
```

6. Atualize as dependências e valide:

```bash
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python -m pip install -r requirements.txt
fi
./verificar.sh
```

Se o `.venv` estiver incompleto, `./TriScore.sh` avisa, recria o ambiente em
`.venv.tmp` e só o ativa depois de validar os imports.

7. Inicie novamente:

```bash
./TriScore.sh
```

## 9. Problemas comuns

### Python 3.12 não encontrado

No pacote portátil:

```bash
sudo ./instalar_debs.sh
./verificar.sh
```

No git clone:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv
```

### Módulo venv ausente

No pacote portátil:

```bash
sudo ./instalar_debs.sh
```

No git clone:

```bash
sudo apt install -y python3.12-venv
```

### Sem internet no git clone

O clone não inclui `wheels/`. Conecte-se à internet e execute novamente:

```bash
./TriScore.sh
```

A falha não deixa `.venv` parcial. Para operar sem internet desde a primeira
instalação, use o pacote portátil com `wheels/`.

### Porta 8000 ocupada

O launcher escolhe outra porta automaticamente. Para forçar uma porta:

```bash
./TriScore.sh --port 8123
```

### Navegador não abriu

Use a URL mostrada no terminal, por exemplo:

```text
http://127.0.0.1:8000
```

### PDF não gera

```bash
./verificar.sh
```

O Triscore usa ReportLab + Pillow. Não é necessário instalar Pango, Cairo ou WeasyPrint.

### Banco corrompido

Feche o app e restaure o backup mais recente:

```bash
cp dados/backups/triscore-encerramento-*.db dados/banco/triscore.db
```

### Dados do layout antigo

```bash
.venv/bin/python scripts/migrar_dados.py
cat dados/.migracao-legado.json
```

## 10. Observações importantes

- Não execute o launcher com `sudo`; use o seu usuário normal.
- Não abra duas instâncias sobre o mesmo banco.
- O servidor escuta apenas em `127.0.0.1`.
- O uso normal não precisa de internet depois que as dependências estão instaladas.
- Para dados oficiais, confirme que a faixa **MODO TESTE** não aparece.
- Pelo atalho, o servidor fica desacoplado do terminal; encerre pelo botão
  **Encerrar**.
