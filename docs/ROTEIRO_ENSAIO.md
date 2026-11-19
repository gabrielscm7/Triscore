# Roteiro de ensaio da prova

Objetivo: ensaiar o fluxo completo do Triscore em ambiente **offline**, usando o
banco de teste, e repetir a mesma sequência no dia da prova no ambiente real.

> Regra de ouro: **use dados fictícios apenas no ambiente de teste**. Se a
> faixa vermelha **MODO TESTE** não estiver visível, pare e confira o ambiente
> antes de digitar qualquer resultado.

## 0. Preparação do notebook

**Antes**

- [ ] Notebook carregado e com o pacote portátil `triscore-portatil-*` copiado.
- [ ] Python 3.11+ instalado (`python --version` ou `py --version`).
- [ ] Pendrive ou pasta de backup disponível e com espaço livre.
- [ ] Impressora ou PDF de contingência disponível.
- [ ] Navegador atualizado (Chrome, Edge ou Firefox).

**Depois**

- [ ] `python scripts/audit_offline.py` retorna “Auditoria offline OK”.
- [ ] `python scripts/smoke_test.py` termina com “Smoke test concluído”.
- [ ] `python -m pytest -q` passa sem falhas.
- [ ] Nenhuma aba do navegador depende de internet para abrir o sistema.

## 1. Instalação offline

**Antes**

- [ ] Pasta do pacote aberta no terminal.
- [ ] Internet desconectada de propósito para o ensaio.

**Depois**

- [ ] `python -m venv .venv` criou o ambiente virtual.
- [ ] `python -m pip install --no-index --find-links wheels -r requirements-dev.txt`
      concluiu sem acessar a rede.
- [ ] `iniciar.sh` (Linux/macOS) ou `iniciar.bat` (Windows) abre o sistema.

## 2. Separar os ambientes

**Antes**

- [ ] Ninguém está usando o banco real.
- [ ] Você sabe qual banco será usado no ensaio: `data/teste/triscore-teste.db`.

**Depois**

- [ ] `python run.py --modo teste --no-browser` inicia na porta **8100**.
- [ ] A faixa **MODO TESTE** aparece no topo de todas as telas.
- [ ] O console mostra banco, backups e PDFs dentro de `data/teste/`.
- [ ] `python run.py` (sem `--modo teste`) inicia na porta **8000** e **não**
      mostra a faixa de teste.
- [ ] Tentar abrir o banco de teste como real é recusado sem
      `--confirmar-banco`.

## 3. Criar a prova

**Antes**

- [ ] Ambiente correto confirmado (teste no ensaio, real no evento).
- [ ] Nome, data e local da prova em mãos.

**Depois**

- [ ] A prova aparece em **Provas** com data e local corretos.
- [ ] A configuração foi salva.
- [ ] Limite de atletas por bateria confere com o planejamento.
- [ ] Cronograma está ativo ou desativado conforme a necessidade.

## 4. Categorias e equipes

**Antes**

- [ ] Lista oficial de categorias e faixas etárias separada.
- [ ] Lista de equipes/clubes separada.

**Depois**

- [ ] Cada categoria existe uma única vez.
- [ ] O modo de pódio (separado ou misto) está correto.
- [ ] As equipes aparecem em **Equipes** com os nomes oficiais.
- [ ] Nenhuma categoria ou equipe duplicada.

## 5. Atletas

**Antes**

- [ ] CSV conferido ou formulário manual aberto.
- [ ] Peitos definidos ou deixados em branco para geração automática.
- [ ] Arquivo `examples/atletas_com_erros.csv` usado apenas para testar erros.

**Depois**

- [ ] A prévia do CSV foi conferida linha a linha.
- [ ] O relatório de erros foi baixado, se houve linhas rejeitadas.
- [ ] O total de atletas importados confere com a lista oficial.
- [ ] Filtros por categoria, equipe e sexo retornam os atletas esperados.
- [ ] Avisos de idade fora da faixa foram revisados, sem bloquear cadastros.

## 6. Baterias e ordem de largada

**Antes**

- [ ] Limite por bateria definido.
- [ ] Critério inicial escolhido: peito, nome ou sorteio.

**Depois**

- [ ] Todos os atletas esperados foram distribuídos.
- [ ] Baterias mistas e separadas estão conforme a categoria.
- [ ] A ordem das baterias e dos atletas está correta.
- [ ] Nenhum atleta aparece em duas baterias.
- [ ] A lista de não alocados está vazia ou justificada.

## 7. Cronograma e lista de largada

**Antes**

- [ ] Horário inicial e intervalos conferidos.
- [ ] Impressora ou pasta de PDFs pronta.

**Depois**

- [ ] O cronograma na tela mostra horários coerentes.
- [ ] **Exportar cronograma PDF** gera um arquivo A4 válido.
- [ ] **Lista de largada PDF** contém uma seção por bateria e campo de tempo.
- [ ] Os PDFs abrem sem internet e têm a prova e a data corretas.

## 8. Súmula e resultados

**Antes**

- [ ] Súmula impressa ou aberta na tela.
- [ ] Operador sabe aceitar `mm:ss`, `hh:mm:ss` e centésimos.
- [ ] Status DNF, DSQ e DNS explicados para a equipe.

**Depois**

- [ ] Cada tempo lançado foi relido em voz alta por uma segunda pessoa.
- [ ] Status especiais não têm tempo associado.
- [ ] O topo da súmula mostra lançados, válidos, especiais e pendentes.
- [ ] Um backup automático foi criado em `triscore-pre-sumula-*.db` a cada
      gravação ou exclusão.

## 9. Classificação e relatório

**Antes**

- [ ] Todos os resultados esperados foram lançados.
- [ ] Critério de desempate definido pela organização.

**Depois**

- [ ] A classificação reúne atletas de todas as baterias.
- [ ] Pódios separados/mistos conferem com a configuração.
- [ ] Empates e status especiais aparecem conforme a regra escolhida.
- [ ] **Exportar relatório final PDF** gera capa, resumo e classificação.
- [ ] O relatório final foi conferido contra a súmula.

## 10. Premiação

**Antes**

- [ ] Slides de abertura, categorias e encerramento revisados.
- [ ] Banner, fundo e fonte já enviados, se forem usados.
- [ ] Projetor e tela cheia testados.

**Depois**

- [ ] A sequência de slides abre e navega com as setas e o `Espaço`.
- [ ] Empates aparecem no pódio; posições vazias não mostram atletas.
- [ ] O tema e os textos persistem após recarregar a página.
- [ ] **PDF de premiação** foi gerado como plano B.

## 11. Backup manual

**Antes**

- [ ] Pendrive conectado ou pasta de destino existente.
- [ ] Ninguém está alterando resultados durante a cópia.

**Depois**

- [ ] Tela **Backup** mostra o ambiente, banco e pastas corretos.
- [ ] **Backup agora** cria `triscore-backup-<ambiente>-AAAAMMDD-HHMMSS`.
- [ ] A cópia contém o banco SQLite, `exports/*.pdf`, arquivos de premiação e
      `manifest.json`.
- [ ] O backup foi aberto/verificado em outra máquina ou pasta.

## 12. Encerramento

**Antes**

- [ ] Resultados oficiais conferidos e assinados.
- [ ] Premiação concluída.

**Depois**

- [ ] Relatório final e PDF de premiação arquivados.
- [ ] Backup manual final copiado para dois destinos, se possível.
- [ ] O sistema foi encerrado com `Ctrl+C`.
- [ ] A pasta do evento foi organizada com data e nome da prova.

## Ensaio rápido com dados fictícios

Execute no ambiente de teste:

```bash
python scripts/seed_test_results.py --reset
python run.py --modo teste --no-browser
```

Percorra as telas **Provas → Configuração → Atletas → Baterias → Súmula →
Classificação → Premiação → Backup** e confira a faixa **MODO TESTE** em todas
elas. Ao final, rode o fluxo automatizado:

```bash
python scripts/smoke_test.py
```
