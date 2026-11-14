# DRIFT-001 · Lote de Produção com data drift e concept drift

- Etapa: 2 (Jira PMF4-16)
- Status: concluída (aguardando PR; decisões do Akira em 04/11/2026, modo prazo)
- Data: 04/11/2026

## Objetivo
Adulterar a Produção-base de forma controlada para simular uma mudança econômica, sabendo de
antemão a "resposta certa". Entrega 2 lotes: um com data drift em 7 colunas (`BILL_AMT1` a
`BILL_AMT6` e `LIMIT_BAL`) e um com concept drift. Atende o requisito "Dataset de produção com ≥ 2
variáveis alteradas" e alimenta o relatório Evidently do DRIFT-002.

## Conceito por trás (didático)
**Data drift** muda quem chega: as entradas (X) mudam, e cada perfil se comporta como antes.
**Concept drift** muda o que o perfil significa: as entradas são as mesmas, mas o resultado (y) muda.
No segundo caso, um monitor que olha só as entradas não vê nada de errado, e é por isso que ele é o
mais perigoso.

Simular com deslocamentos conhecidos é como testar um alarme de incêndio acendendo um fósforo de
propósito: como sabemos o que foi alterado, dá para conferir se o detector acertou.

Duas medidas usadas aqui: **PSI** (Population Stability Index) mede o quanto a distribuição de uma coluna
mudou; abaixo de 0,1 é estável, de 0,1 a 0,25 pede atenção e acima de 0,25 é mudança relevante. **AUC** mede
o quanto o modelo ordena bem os clientes: 0,5 é sorteio e 1,0 é perfeito.

## Decisões do Akira
Racional completo registrado nas notas internas do projeto (fora do repositório).

### 1. Data drift: "inflação + aperto de crédito"
`BILL_AMT1` a `BILL_AMT6` sobem com o mesmo fator nas seis, o que preserva a correlação entre elas, e
`LIMIT_BAL` cai. O `default` não muda: é uma mudança nominal (preços) e de política do banco (limites), não
de comportamento do cliente. Descartado: deslocar `PAY_*` mantendo o y, que seria concept drift disfarçado.

### 2. Tamanho
| Coluna | Intensidade 1 | Intensidade i |
|---|---|---|
| `BILL_AMT1` a `BILL_AMT6` | × 1,25 | × (1 + 0,25 · i) |
| `LIMIT_BAL` | × 0,75 | × (1 − 0,25 · i) |

Os valores são arredondados para inteiro, e `LIMIT_BAL` continua > 0. **Faturas negativas** (crédito a favor do
cliente) também são multiplicadas: o crédito de 1.000 vira 1.250.

### 3. Concept drift
Nenhuma coluna X muda. Entre os clientes do quartil mais alto de `BILL_AMT1` que não deram default, uma fração
passa a ter `default = 1`. Com intensidade 1, a taxa de default desse subgrupo dobra.

**A conta**, com N clientes no subgrupo, D com default e N − D sem default:
- taxa atual r = D / N; para dobrar, precisamos chegar a 2D / N;
- portanto, trocar **exatamente D rótulos**;
- fração dos que não deram default: f = D / (N − D) = r / (1 − r).

Com intensidade i, trocam-se `round(i · D)` rótulos. Os valores reais estão em "Resultado" e no manifesto.

## Decisões de implementação (Claude, modo prazo)
- **Quartil calculado na própria Produção-base**, com `BILL_AMT1 >= percentil 75`.
- **Sorteio com lista embaralhada uma vez só:** a seed define a ordem dos candidatos, e cada intensidade pega os
  primeiros da lista. Assim, quem muda em 0,3 continua mudando em 0,6, e o número trocado é exato. Alternativa
  descartada: comparar um número aleatório com a probabilidade, que só acerta o número em média.
- **O data drift não usa sorteio:** os fatores são determinísticos, então a seed só afeta o concept drift.
- **Se a conta não fechar, o script para:** subgrupo sem nenhum default (trocaria 0 rótulos, sucesso vazio) ou com
  taxa acima de 50% (não há rótulos suficientes para dobrar) levanta erro.
- **`detect.py` e `DataDefinition` ficam para o DRIFT-002.** A medição de PSI e AUC abaixo é só conferência, com
  script temporário fora do repositório. Os resultados do teste de `DataDefinition` de 03/11 foram para o REPASSE.

## Previsões
Escritas antes de gerar os lotes. Faixas de PSI, contra a Referência: estável (< 0,1), atenção (0,1 a 0,25),
mudança relevante (> 0,25). A coluna do Akira é preenchida na revisão do PMF4-38.

| Cenário | Coluna | Alteração | Previsão do Claude: PSI | Previsão do Claude: a AUC cai? | Previsão do Akira |
|---|---|---|---|---|---|
| Data drift | `LIMIT_BAL` | × 0,75 | relevante, ~0,27 (medido no spike) | Pouco ou nada: dentro do intervalo de 0,702 a 0,728 | a preencher no repasse |
| Data drift | `BILL_AMT1` a `BILL_AMT6` | × 1,25 | **estável**, 0,01 a 0,10: a cauda longa concentra quase todos em poucos bins | Pouco ou nada | a preencher no repasse |
| Concept drift | nenhuma coluna X | `default`: ~450 rótulos | estável, iguais aos da Produção-base (X idêntico) | **Sim**: fora do intervalo, entre 0,66 e 0,69 | a preencher no repasse |

**Previsão do `run_validation.py`, por lote:** exit 0, evento `validation_passed`, 9.000 linhas, 0 falhas, nenhum arquivo
novo em `reports/validation/`. Drift é "diferente mas possível", e o contrato não barra isso.

**Previsão das contagens:**
- Data drift: 0 rótulos trocados; 7 colunas alteradas e 17 idênticas, contando `ID` e sem contar `default`.
- Concept drift: subgrupo com cerca de 2.250 clientes, taxa de default perto de 20%, ~450 rótulos trocados, taxa
  geral de 22,1% para ~27%; 24 colunas idênticas (`ID` e as 23 features).

## Escopo
- Dentro: `drift/scenarios.py`, `scripts/make_drift_batch.py`, testes, `run_id` no log JSON, manifesto por lote.
- Fora: `drift/detect.py` e relatório Evidently (DRIFT-002); PSI à mão (DRIFT-003, sem reaproveitar a função do spike);
  gerar as várias "semanas" (OBS-002, que só chamará o script com outras intensidades).

## Estrutura
```
src/credit_risk_observability/drift/
├── __init__.py
└── scenarios.py              # funções puras: DataFrame + intensidade -> DataFrame + detalhes
scripts/make_drift_batch.py   # ponto de entrada: gera, valida no contrato, salva, registra
tests/test_drift.py
```
- **Funções puras:** não leem nem gravam arquivo, então testam com dados sintéticos.
- **Saídas:** `data/production/batch_<cenario>_i<intensidade>.parquet` (fora do git, regerável) e
  `reports/drift/batch_<cenario>_i<intensidade>_manifest.json` (versionado). O manifesto traz `run_id`, seed, intensidade,
  fatores, rótulos trocados, hashes e versões; só agregados, sem valores de linhas (ADR-005).
- **A Produção-base nunca é alterada.** Lote reprovado no contrato não é gravado, e o script sai com exit 1.
- **`run_id`:** `new_run_id()` em `monitoring/events.py`; uma identificação por execução, no log e no manifesto, e também no
  `run_validation.py`. Prepara o OBS-001 para correlacionar os eventos de uma execução.

## Passos
1. Testes primeiro.
2. `drift/scenarios.py` e `scripts/make_drift_batch.py` até passarem.
3. Gerar os 2 lotes e validar com `run_validation.py`.
4. Comparar com as previsões e rodar a `revisao-critica`.

## Critérios de aceite (verificáveis)
- [x] Intensidade 0 devolve lote idêntico à Produção-base
- [x] Intensidade 1 aplica exatamente os fatores
- [x] Lote com drift passa no contrato; lote reprovado não é gravado
- [x] Concept drift não muda nenhuma coluna X e troca exatamente o número de rótulos calculado
- [x] A mesma seed gera o mesmo lote; rótulos trocados em uma intensidade continuam trocados em uma maior
- [x] Dois lotes em `data/production/`, com manifesto, exit 0 no `run_validation.py`
- [x] Testes novos e os 31 antigos passando; ruff limpo; comando conferido nos dois shells

## Como validar de verdade
```
uv run python scripts/make_drift_batch.py --scenario data_drift --intensity 1
uv run python scripts/make_drift_batch.py --scenario concept_drift --intensity 1
uv run python scripts/run_validation.py data/production/batch_data_drift_i100.parquet
uv run python scripts/run_validation.py data/production/batch_concept_drift_i100.parquet
uv run pytest -q
```

## Riscos e perguntas em aberto
- O card do Jira cita `src/credit_obs/drift/`, nome antigo do pacote. O caminho certo é `src/credit_risk_observability/drift/`.
- Subir as faturas e cortar o limite ao mesmo tempo aumenta os casos de fatura maior que o limite. Contar no resultado.

## Resultado (preencher ao concluir)
**O que isso significa na prática:** os dois lotes passaram no contrato e fizeram o que a simulação pedia. O lote de concept
drift derruba o modelo sem nenhuma entrada mudar. O lote de data drift muda bastante as entradas, mas o modelo quase não
percebe, e o PSI só aponta o limite, não as faturas.

Medido em 04/11 com o baseline, sem retreino, contra a Referência. PSI e KS com Evidently 0.7.23 e método explícito, em script
de conferência fora do repositório (`detect.py` é do DRIFT-002). O KS devolve um p-valor: abaixo de 0,05, ele aponta mudança.

| Lote | Colunas | PSI | KS (p-valor) | AUC (IC 95%) | Default real |
|---|---|---|---|---|---|
| Produção-base (controle) | as 23 | todas < 0,1 | nenhuma < 0,05 | 0,7149 (0,701 a 0,728) | 22,12% |
| `batch_data_drift_i100` | `LIMIT_BAL` | **0,2715** | 6,3e-145 | 0,7144 (0,702 a 0,728) | 22,12% |
| `batch_data_drift_i100` | `BILL_AMT1` a `BILL_AMT6` | **0,025 a 0,046** | 5,9e-37 a 1,0e-27 | igual acima | igual acima |
| `batch_data_drift_i100` | as outras 16 | todas < 0,1 | nenhuma < 0,05 | igual acima | igual acima |
| `batch_concept_drift_i100` | as 23 | iguais às do controle | iguais às do controle | **0,6647 (0,650 a 0,678)** | 27,22% |

**Contas do concept drift:** corte de `BILL_AMT1` em 67.290,75; N = 2.250 clientes; D = 459 com default; taxa de 20,4% para 40,8%;
f = 459 / 1.791 = 25,63%; **459 rótulos trocados** (conferido por diferença contra a base).

**Previsão x resultado:**
- Contrato: previ exit 0, 9.000 linhas, 0 falhas e nenhum arquivo novo em `reports/validation/`. **Acertei** nos 2 lotes.
- Contagens: previ ~2.250 clientes, ~450 rótulos e taxa geral de ~27%. **Perto:** 2.250, 459 e 27,22%. Colunas iguais à base: 18 de 25 no data drift e 24 de 25 no concept drift, como previsto.
- PSI: previ `LIMIT_BAL` em ~0,27 e faturas estáveis entre 0,01 e 0,10. **Acertei:** 0,2715 e 0,025 a 0,046.
- AUC: previ queda pequena no data drift e 0,66 a 0,69 no concept drift. **Acertei**, com 0,7144 e 0,6647, perto da borda inferior.

**Reprodutibilidade:** gerar de novo dá o mesmo hash nos 2 lotes, no Git Bash e no PowerShell; a Produção-base não mudou (`2a7537e8...`).
A correlação entre `BILL_AMT1` e `BILL_AMT2` ficou em 0,9491, igual à base.

**Achados para o repasse:**
1. **As faturas não aparecem no PSI.** Mudaram 25%, e o KS as detecta com folga, mas o PSI fica na faixa "estável".
2. **O data drift não dói.** A AUC praticamente não muda: a ordem dos clientes quase não mudou (correlação de postos de 0,9986 entre os scores). A dor deste projeto vem do concept drift.
3. **Realismo:** clientes com `BILL_AMT1` acima do limite sobem de 643 (7,1%) para 3.265 (36,3%). O contrato aceita, mas é um efeito colateral forte da combinação de faturas × 1,25 com limite × 0,75.
