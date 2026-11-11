# DRIFT-003 · PSI e KS à mão, antes de confiar no Evidently

- Etapa: 2 (aprendizado)
- Status: concluída pelo Claude por decisão do Akira (10/11); o Akira refaz à mão no repasse (PMF4-38)
- Data: 10/11/2026
- Jira: [PMF4-17](https://akiravkax.atlassian.net/browse/PMF4-17)
- Pilotagem: era **Akira pilota**. Em 10/11, por decisão do Akira, o Claude implementou a `psi()` para
  não travar a entrega. O exercício continua no repasse: trocar o corpo por `NotImplementedError` volta os
  testes ao estado de pulados.

## Objetivo
Calcular o PSI do zero e o KS com o scipy, comparar com os números do Evidently nos relatórios do
DRIFT-002 e explicar qualquer diferença.

## Conceito por trás (didático)
O **PSI** divide os valores em faixas, compara a proporção de clientes em cada faixa antes e depois,
e soma `(atual% - ref%) * ln(atual% / ref%)`. Cada termo é sempre >= 0: se a faixa ganhou gente, os
dois fatores são positivos; se perdeu, os dois são negativos. O **KS** não usa faixas: compara as
duas curvas acumuladas e pega a maior distância vertical.
Analogia: o PSI é comparar duas turmas pela quantidade de alunos em cada faixa de nota; o KS é
sobrepor os dois boletins ordenados e achar onde eles mais se afastam.

## O que já está pronto (Claude)
- `src/credit_risk_observability/drift/manual.py`: assinatura e contrato de `psi()`.
- `tests/test_psi_manual.py`: 5 testes (série contra si mesma, valor feito à mão 0,2747, simetria,
  deslocamento maior dá PSI maior, faixa vazia não explode). Ficam **pulados** até `psi()` existir;
  foram validados contra uma implementação de referência que não está no repositório.
- `scripts/compare_psi.py`: tabela PSI à mão x Evidently e KS scipy x Evidently.

## Passos (Akira)
1. Implementar `psi()` até os 5 testes passarem (`uv run pytest tests/test_psi_manual.py`).
2. Rodar `uv run python scripts/compare_psi.py` e anotar os números abaixo.
3. Explicar cada diferença entre a sua `psi()` e o Evidently (pista: SPIKE-001, armadilhas 1 e 2).
4. Testar com `--bins` diferentes e responder: a decisão "drift ou não" muda?

## Critérios de aceite
- [x] `psi()` implementada; 5 testes passando.
- [x] KS de `LIMIT_BAL` Referência x Produção calculado com o scipy.
- [x] Tabela de comparação anotada aqui, com a explicação das diferenças.

## Resultado (feito pelo Claude por decisão do Akira; revisar no repasse)
A `psi()` usa faixas por quantis da Referência (padrão em crédito) e bordas externas abertas, para um
valor do lote fora da faixa contar como mudança, em vez de sumir da conta.

| Lote | Feature | PSI por quantis (10 faixas) | PSI com as faixas do Evidently | PSI do Evidently | KS p (scipy) | KS p (Evidently) |
|---|---|---|---|---|---|---|
| Produção-base | `LIMIT_BAL` | 0,0008 | 0,0030 | 0,0059 | 0,947 | 0,947 |
| Produção-base | `AGE` | 0,0007 | 0,0015 | 0,0015 | 0,549 | 0,549 |
| Data drift | `LIMIT_BAL` | 0,2486 | 0,2686 | 0,2715 | 6,3e-145 | 6,3e-145 |
| Data drift | `BILL_AMT1` | 0,0460 | 0,0226 | 0,0355 | 5,9e-37 | 5,9e-37 |
| Data drift | `BILL_AMT6` | 0,0182 | 0,0214 | 0,0456 | 5,12e-31 | 5,12e-31 |

**Por que os números diferem (duas causas, ambas medidas):**
1. **Faixas.** O Evidently usa faixas de largura igual (regra de Sturges) sobre Referência e lote
   juntos; a `psi()`, quantis só da Referência. Com 20 ou menos valores distintos, ele usa uma faixa por valor.
2. **Preenchimento de zeros.** Com as mesmas faixas, `AGE` e as `PAY_*` batem. O que sobra nas outras
   vem de `get_binned_data`, que preenche proporção zero com um valor diferente em cada lado (armadilha 1
   do SPIKE-001), e faixas vazias nos dois lados somam PSI que não deveria existir. Reproduzindo essa
   regra, a diferença em todas as 40 comparações foi de 4e-19: o cálculo é o mesmo.

**A decisão "drift ou não" muda com as faixas? Sim.** O PSI de `LIMIT_BAL` no lote de data drift vai de
0,1882 (5 quantis) a 0,2486 (10 quantis) e 0,4795 (20 quantis); no Evidently, 0,2715. Com 10 quantis,
ficaria abaixo do limite de 0,25; com o Evidently, acima. O número do PSI depende da escolha das faixas:
o limite só faz sentido junto com o método. O KS não tem faixas, e os p-valores são idênticos.
