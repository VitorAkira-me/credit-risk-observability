# SPIKE-001 · Compatibilidade do Evidently com pandas 3

- Etapa: 2 (reduz o risco do DRIFT-002, PMF4-18)
- Status: concluída
- Data: 03/11/2026

## Objetivo
Descobrir agora, e não no meio do DRIFT-002, se a versão atual do Evidently funciona com o
pandas 3.0.6 fixado no projeto. Experimento descartável: nenhum código entra em `src/`.

## Conceito por trás (didático)
Um spike é como testar se o sofá passa pela porta antes de comprá-lo: gasta pouco e responde a
uma única pergunta. O metadado do pacote (`pandas>=1.3.5`, sem teto) só diz que ninguém declarou
incompatibilidade, não que funciona. Só rodar prova. E um "sem drift" sozinho também não prova:
um detector quebrado diria o mesmo. Por isso há um controle positivo, com drift conhecido.

## Ambiente testado
Evidently 0.7.23 (a mais recente no PyPI em 03/11/2026), pandas 3.0.6, numpy 2.5.4,
scipy 1.18.1, scikit-learn 1.9.1, pydantic 2.14.1, Python 3.12.10.
O `uv add` só acrescentou 43 pacotes; nenhuma versão existente mudou. Testes: 31 passed depois.

## O que foi feito
`Report([DataDriftPreset(method=...)]).run(current, reference)`, nesta ordem de argumentos, com
Produção-base (9.000) contra Referência (21.000), só `LIMIT_BAL`, `AGE` e `PAY_0`.
Script descartável, fora do repositório. Execução com `DO_NOT_TRACK=1`.
Controle positivo, só em memória: `LIMIT_BAL * 0,75`. Não é o DRIFT-001: nada foi gravado em `data/`.

## Resultado
Funcionou nas 5 execuções: nenhuma exceção e nenhum warning em tempo de execução; HTML de ~3,8 MB gerado.

| Coluna | PSI base | KS p-valor base | PSI controle | KS p-valor controle |
|---|---|---|---|---|
| LIMIT_BAL | 0,0059 | 0,947 | **0,2715 (drift)** | **6,3e-145 (drift)** |
| AGE | 0,0015 | 0,549 | 0,0015 | 0,549 |
| PAY_0 | 0,0024 | 0,972 | 0,0024 | 0,972 |

Só a coluna alterada foi apontada: 0 de 3 na base, 1 de 3 no controle, com PSI e com KS.

**Conferência independente:** o KS bate com `scipy.stats.ks_2samp`, e o PSI recalculado com numpy
reproduz o Evidently (diferença 0,0e+00 em `LIMIT_BAL`, base e controle; `AGE` e `PAY_0` iguais
nas casas comparadas).

## Erros e armadilhas encontrados
Nenhum erro de compatibilidade com o pandas 3. Pontos que surpreenderam:
1. **PSI inflado por bins vazios.** O primeiro recálculo deu 0,002965 em `LIMIT_BAL`, contra 0,005876
   do Evidently. Causa: `get_binned_data` preenche zeros com um valor diferente em cada lado
   (4,76e-11 na Referência, 1e-4 na Produção). Por isso os 2 bins vazios nos dois lados somam
   +0,0029, quando deveriam somar 0. É pequeno perto do limiar de 0,1, mas o valor depende do formato
   dos dados.
2. **Dois métodos em um.** Com mais de 20 valores distintos, o PSI usa bins de Sturges. Com 20 ou
   menos, como `PAY_0` (11 valores), calcula valor a valor.
3. **Sem `method`, o padrão não atende o requisito.** Com 9.000 linhas o preset usou Wasserstein,
   não PSI nem KS. O método precisa ser explícito.
4. **Direções opostas.** Em PSI, valor alto é drift (>= 0,1). No KS, `value` é o p-valor, e valor
   baixo é drift (< 0,05). O `dict()` traz só `value`: o limiar está em `config`, e a decisão por coluna
   precisa ser calculada por nós.
5. **Documentação inconsistente.** A página cita `stattest` e `method`; `method` funcionou. O parâmetro
   `columns` não tem exemplo e não foi testado: aqui selecionamos as colunas no DataFrame.
6. **Ruído na importação:** `SyntaxWarning` em `evidently/descriptors/text_match.py`. Inofensivo.

## O que isso muda no DRIFT-002
- Manter pandas 3.0.6; não é preciso decidir troca de versão.
- Rodar duas vezes, com `method="psi"` e `method="ks"`, e montar a tabela "alterei / detectou" a partir
  de `value` e `config.threshold`, respeitando a direção de cada método.
- Citar a armadilha 1 ao interpretar PSI perto do limiar. O DRIFT-003 (PMF4-17) é o lugar de explicar
  isso, com o PSI calculado à mão.
- Cada HTML tem ~3,8 MB com 3 colunas. Medir o tamanho com todas as colunas antes de versionar.

## Risco que sobra (não testado)
Todas as colunas de uma vez, `DataDefinition` com `SEX`, `EDUCATION` e `MARRIAGE` como categóricas
(com `PAY_0` inteiro, o preset o tratou como numérico) e coluna de predição. Se algo quebrar com pandas 3,
será mais provável aí. Telemetria: as referências encontradas estão nos módulos de UI e collector, e
não no fluxo de `Report`; não foi medido tráfego de rede.
