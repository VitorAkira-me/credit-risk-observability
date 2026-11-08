# DRIFT-003 · PSI e KS à mão, antes de confiar no Evidently

- Etapa: 2 (aprendizado)
- Status: aprovada; implementação do Akira em andamento
- Data: 08/11/2026
- Jira: [PMF4-17](https://akiravkax.atlassian.net/browse/PMF4-17)
- Pilotagem: **Akira pilota**. O Claude montou o esqueleto, os testes e o script de comparação;
  a função `psi()` é do Akira, com uma dica de cada vez.

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
- [ ] `psi()` implementada; 5 testes passando.
- [ ] KS de `LIMIT_BAL` Referência x Produção calculado com o scipy.
- [ ] Tabela de comparação anotada aqui, com a explicação das diferenças.

## Resultado (preencher o Akira)
