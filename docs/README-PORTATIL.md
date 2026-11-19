# Triscore portátil — Ubuntu 24.04 offline

Este pacote foi preparado para **Ubuntu 24.04 LTS x86_64**, com Python 3.12.
Ele contém a aplicação, o ambiente virtual pré-criado, as 29 wheels do alvo e os
pacotes `.deb` de fallback do Python. Não é necessário acessar a internet.

## Conteúdo

```text
TriScore.sh          launcher principal
iniciar.sh           alias de TriScore.sh
verificar.sh         verificação do ambiente
wheels/              29 wheels cp312/manylinux
.venv/               venv Python 3.12 pré-criada
debs/                python3.12, python3.12-venv e dependências
dados/               banco, backups, exports, uploads e logs
```

Se o Python 3.12/venv já estiver instalado no Ubuntu, basta executar:

```bash
./verificar.sh
./TriScore.sh
```

## Se faltar Python 3.12 ou venv

Com o notebook ainda offline, instale os `.deb` incluídos:

```bash
sudo ./instalar_debs.sh
```

Depois repita:

```bash
./verificar.sh
./TriScore.sh
```

O launcher também detecta a ausência do Python e mostra essa instrução.

## Uso

- O servidor escuta somente em `127.0.0.1`.
- A porta padrão é 8000; se estiver ocupada, o launcher escolhe outra.
- O navegador abre após o health check.
- Logs ficam em `dados/logs/`.
- O botão **Encerrar** ou `Ctrl+C` cria automaticamente um backup do banco em
  `dados/backups/`.

## Dados

Tudo fica fora do código, em `dados/`:

```text
dados/banco/triscore.db
dados/backups/
dados/exports/
dados/uploads/premiacao/
dados/logs/
dados/teste/
```

Para usar outra pasta, defina `TRISCORE_DATA_DIR` antes de iniciar:

```bash
TRISCORE_DATA_DIR=/mnt/pendrive/triscore ./TriScore.sh
```

## Atalho no GNOME

```bash
./instalar_atalho.sh
```

O atalho é criado em `~/Desktop/Triscore.desktop`. Se o GNOME pedir, clique com
o botão direito e escolha **Allow Launching**. Também é possível marcar por linha
de comando:

```bash
chmod +x ~/Desktop/Triscore.desktop
gio set ~/Desktop/Triscore.desktop metadata::trusted true
```

## Verificação e testes

```bash
./verificar.sh
.venv/bin/python scripts/smoke_launcher.py
.venv/bin/python scripts/smoke_test.py
.venv/bin/python -m pytest -q
```

O `verificar.sh` confere Ubuntu 24.04, x86_64, Python 3.12, venv, dependências,
wheels, geração de PDF, porta livre, escrita em `dados/` e o estado da internet
(apenas informativo).

## PDF

O Triscore usa **ReportLab + Pillow**. Não usa WeasyPrint, Pango ou Cairo, então
não há dependências gráficas de sistema para gerar PDF.
