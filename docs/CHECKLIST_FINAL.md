# Checklist final — prontidão para o evento

Data do ensaio: ____/____/______  
Responsável: ______________________________  
Notebook / sistema: ______________________________

## 1. Offline

- [ ] `python scripts/audit_offline.py` retorna sucesso.
- [ ] Templates, CSS, JS e SVG não têm URLs externas (exceto o namespace SVG).
- [ ] Navegador abre todas as telas com a internet desligada.
- [ ] Fontes, logo e PDFs funcionam sem internet.
- [ ] Nenhuma requisição para CDN, Google Fonts, ícones ou scripts externos.

## 2. Ambientes separados

- [ ] Ambiente real usa porta **8000**, `data/triscore.db`, `backups/` e `exports/`.
- [ ] Ambiente de teste usa porta **8100**, `data/teste/triscore-teste.db`,
      `data/teste/backups/` e `data/teste/exports/`.
- [ ] Faixa **MODO TESTE** aparece em todas as telas do ambiente de teste,
      incluindo a premiação.
- [ ] Ambiente real **não** exibe a faixa de teste.
- [ ] O iniciador recusa abrir banco de teste como real sem `--confirmar-banco`.
- [ ] O iniciador recusa abrir banco real como teste sem `--confirmar-banco`.

## 3. Backup

- [ ] Backup automático da súmula é criado a cada gravação/exclusão.
- [ ] Tela **Backup** abre pelo menu superior.
- [ ] Botão **Backup agora** copia banco + PDFs + premiação para a pasta escolhida.
- [ ] `manifest.json` está presente e registra data, ambiente e contagens.
- [ ] Backup manual foi restaurado/aberto com sucesso em uma cópia.

## 4. Pacote portátil

- [ ] `python scripts/build_portable.py` gera a pasta `triscore-portatil-*`.
- [ ] A pasta contém `app/`, `run.py`, `wheels/`, `README-PORTATIL.md`,
      `iniciar.sh` e `iniciar.bat`.
- [ ] A instalação offline com `--no-index --find-links wheels` funciona.
- [ ] O pacote inicia sem internet em um ambiente limpo.
- [ ] O pacote não contém banco real, backups antigos ou PDFs da produção.

## 5. Roteiro e ensaio

- [ ] `docs/ROTEIRO_ENSAIO.md` foi lido pela equipe.
- [ ] Ensaio completo feito no ambiente de teste com dados fictícios.
- [ ] Cronograma e lista de largada foram impressos/gerados.
- [ ] Súmula, classificação, relatório final e premiação conferidos.
- [ ] Backup manual feito ao final do ensaio.
- [ ] Problemas encontrados foram corrigidos e o ensaio repetido.

## 6. Smoke test e testes automatizados

- [ ] `python scripts/smoke_test.py` termina com sucesso.
- [ ] O smoke test confirma a faixa **MODO TESTE**.
- [ ] O smoke test cria prova, categorias, equipe, atletas, baterias e resultados.
- [ ] O smoke test gera os quatro PDFs (cronograma, largada, relatório e premiação).
- [ ] O smoke test executa backup manual e confere banco + PDFs + manifesto.
- [ ] O smoke test bloqueia conexões externas.
- [ ] `python -m pytest -q` passa sem falhas.

## 7. Véspera do evento

- [ ] Notebook atualizado, carregado e com economia de energia desativada.
- [ ] Pacote portátil e pendrive de backup separados.
- [ ] Banco real escolhido e conferido (`data/triscore.db`).
- [ ] Prova, categorias, equipes e atletas já cadastrados no banco real.
- [ ] Baterias e lista de largada revisadas.
- [ ] Impressora, cabos, projetor e extensão testados.
- [ ] PDF de contingência da premiação gerado.

## 8. Dia do evento — antes da largada

- [ ] Abrir com `python run.py` (porta 8000).
- [ ] Confirmar que **não** há faixa **MODO TESTE**.
- [ ] Confirmar nome, data e local da prova.
- [ ] Conferir total de atletas e baterias.
- [ ] Fazer um **Backup agora** antes de qualquer lançamento.
- [ ] Abrir a súmula e deixar a tela pronta.

## 9. Dia do evento — durante

- [ ] Lançar tempos em dupla (digitação + conferência).
- [ ] Revisar DNF/DSQ/DNS imediatamente.
- [ ] Fazer backup manual a cada bloco de resultados.
- [ ] Acompanhar a classificação após cada bloco.
- [ ] Não usar o ambiente de teste para resultados oficiais.

## 10. Dia do evento — depois

- [ ] Conferir classificação final contra a súmula.
- [ ] Gerar relatório final e PDF de premiação.
- [ ] Executar backup manual final.
- [ ] Copiar o backup para um segundo destino.
- [ ] Encerrar o sistema com `Ctrl+C`.
- [ ] Arquivar pasta/backup com data e nome da prova.

## Assinatura

Ensaio concluído em ____/____/______ às ______:______.

Responsável: ______________________________

Observações:

____________________________________________________________________________

____________________________________________________________________________

## 11. Validação Ubuntu 24.04 offline

- [ ] Build gerado em `ubuntu:24.04` x86_64 com Python 3.12.
- [ ] `BUILD-INFO.txt` registra Ubuntu, arquitetura, Python e glibc.
- [ ] Wheelhouse com 29 wheels cp312, sem fontes e sem cp314.
- [ ] Pacote contém `.venv` pré-criada, `debs/` e `wheels/`.
- [ ] `iniciar.bat` ausente do pacote.
- [ ] `verificar.sh` retorna `RESULTADO: OK` em contêiner limpo, sem rede.
- [ ] Launcher sobe, health check responde e navegador é dispensável no modo `--no-browser`.
- [ ] Smoke test pelo launcher gera PDF e encerra.
- [ ] `POST /encerrar` cria backup em `dados/teste/backups/`.
- [ ] PDF usa ReportLab/Pillow; sem WeasyPrint/Pango/Cairo.
- [ ] Dados ficam em `dados/`, fora do código.

### Resultado registrado

```text
Data: 19/11/2026
Imagem Ubuntu: ubuntu:24.04 (sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8)
Build: Ubuntu 24.04.5 LTS
Arquitetura: x86_64
Python: 3.12.3 (glibc 2.39)
Wheels: 29 cp312/manylinux, sem fontes e sem cp314
Pacote: triscore-portatil-*.tar.gz (63 MB)
SHA256: consultar o .tar.gz.sha256 gerado ao lado
Rede: --network none
Verificação: RESULTADO OK (0 falhas)
Smoke launcher: health 200; PDF 58.880 bytes; /encerrar 200; processo código 0
Encerramento/backup: triscore-teste-encerramento-*.db
Ctrl+C/backup: confirmado
Porta ocupada: 8100 ocupada; launcher usou 8101
```
