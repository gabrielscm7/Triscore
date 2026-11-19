# Build para Ubuntu 24.04

## Alvo

- Ubuntu 24.04 LTS
- x86_64
- Python 3.12
- glibc 2.39

O build do pacote portátil e do binário é feito dentro do contêiner
`ubuntu:24.04`. Isso evita wheels cp314 ou binários ligados à glibc do host de
desenvolvimento.

## Pacote portátil

```bash
./build.sh
```

Saídas:

```text
dist/triscore-portatil-<timestamp>/
dist/triscore-portatil-<timestamp>.tar.gz
dist/triscore-portatil-<timestamp>.tar.gz.sha256
```

O pacote inclui:

- `.venv/` criada com `python3.12 -m venv --copies`;
- `wheels/` com 29 wheels cp312/manylinux;
- `debs/` com `python3.12-venv` e dependências;
- `TriScore.sh`, `iniciar.sh`, `TriScore.desktop`, `instalar_atalho.sh`,
  `verificar.sh`;
- `BUILD-INFO.txt`, `SHA256SUMS` e documentação.

O script falha se aparecer `.tar.gz`, `.zip`, wheel cp314 ou wheel fora de
manylinux.

## Binário PyInstaller

```bash
./scripts/build_binario.sh
```

Saídas:

```text
dist/triscore-binario-<timestamp>/TriScore/
dist/triscore-binario-<timestamp>.tar.gz
```

Inclui templates, static e schema. O binário usa `TRISCORE_DATA_DIR` ou `dados/`
ao lado do launcher. A versão do PyInstaller é fixada em
`requirements-build.txt`; a versão efetiva é gravada em `BUILD-INFO.txt`.

## Reprodutibilidade

- Versões travadas em `requirements-lock.txt`.
- Wheels baixadas com `--only-binary=:all:` para cp312.
- Tar com `--sort=name`, `--owner=0`, `--group=0`, `--numeric-owner`.
- `SOURCE_DATE_EPOCH` pode ser definido para fixar o mtime do tar.
- PyInstaller não gera binários byte-a-byte idênticos; para máxima
  reprodutibilidade use a mesma imagem Ubuntu e as mesmas versões fixadas.

## Registro do build

O `BUILD-INFO.txt` do pacote exibe, no mínimo:

```text
target_os=Ubuntu 24.04 LTS
build_os=Ubuntu 24.04.x LTS
build_arch=x86_64
build_python=Python 3.12.x
build_glibc=... 2.39
wheels=29
venv_python=Python 3.12.x
```

## Resultado deste build

```text
Imagem: ubuntu:24.04
Ubuntu: 24.04.5 LTS
Arquitetura: x86_64
Python: 3.12.3
glibc: 2.39
PyInstaller: 6.16.0
Pacote portátil: triscore-portatil-*.tar.gz
Binário: dist/triscore-binario-20261119-181815/TriScore/TriScore
Teste do binário: --help OK; saúde 200; Ctrl+C com backup OK
```
