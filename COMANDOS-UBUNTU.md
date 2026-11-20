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

Modo teste:

```bash
./TriScore.sh --modo teste
```

## 2. Opção B — clonar do GitHub e usar o código-fonte

Requer internet nesta etapa.

```bash
sudo apt update
sudo apt install -y git python3.12 python3.12-venv
cd ~
git clone https://github.com/gabrielscm7/Triscore.git
cd Triscore
```

Crie o ambiente e instale as dependências:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Para rodar também os testes e smoke tests:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

Valide:

```bash
./verificar.sh
```

Inicie:

```bash
./TriScore.sh
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

## 6. Testes

Com o `.venv` instalado:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/smoke_launcher.py
```

## 7. Atualizar o projeto clonado do GitHub

Seus dados em `dados/` não são versionados e permanecem intactos.

```bash
cd ~/Triscore
git pull
.venv/bin/python -m pip install -r requirements.txt
./verificar.sh
```

## 8. Problemas comuns

### Python 3.12 não encontrado

```bash
sudo ./instalar_debs.sh
./verificar.sh
```

### Módulo venv ausente

```bash
sudo ./instalar_debs.sh
```

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

## 9. Observações importantes

- Não execute o launcher com `sudo`; use o seu usuário normal.
- Não abra duas instâncias sobre o mesmo banco.
- O servidor escuta apenas em `127.0.0.1`.
- O uso normal não precisa de internet.
- Para dados oficiais, confirme que a faixa **MODO TESTE** não aparece.
