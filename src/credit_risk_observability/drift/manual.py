"""DRIFT-003: PSI calculado à mão, para tirar a caixa-preta do Evidently.

QUEM PILOTA: Akira. Este arquivo é o esqueleto: a assinatura, o contrato (docstring) e os testes
em tests/test_psi_manual.py já estão prontos. A implementação de `psi` é sua.

O que faz: mede o quanto a distribuição de uma coluna mudou entre a Referência e um lote.
Por que existe: para saber o que a biblioteca faz por baixo e conferir se os números batem
(scripts/compare_psi.py compara com o Evidently depois que `psi` estiver pronto).
Onde entra no fluxo: não entra no pipeline; é ferramenta de aprendizado e de conferência.

A fórmula, por faixa i:  (atual%_i - ref%_i) * ln(atual%_i / ref%_i), e o PSI é a soma.
Régua usual: abaixo de 0,1 estável; de 0,1 a 0,25 atenção; acima de 0,25 mudança relevante.
"""

import numpy as np

EPSILON = 1e-4  # o que entra no lugar de uma proporção zero (ver a pergunta do card)


def psi(
    reference: np.ndarray,
    current: np.ndarray,
    bins: int | np.ndarray = 10,
    epsilon: float = EPSILON,
) -> float:
    """Population Stability Index entre duas amostras de uma coluna numérica.

    Recebe:
        reference: os valores da Referência (o "antes").
        current: os valores do lote (o "depois").
        bins: um inteiro (quantas faixas, com bordas tiradas da Referência) ou um array com as
            bordas já prontas (útil nos testes, para controlar a conta).
        epsilon: valor que substitui uma proporção zero, para o ln() não explodir.
    Faz:
        1. define as bordas das faixas a partir da REFERÊNCIA (por quê não do lote?);
        2. conta quantos valores de cada amostra caem em cada faixa e transforma em proporção;
        3. troca as proporções zero por epsilon;
        4. aplica a fórmula e soma.
    Devolve: o PSI, um número >= 0. Exemplo: uma série contra ela mesma dá 0.
    """
    raise NotImplementedError("DRIFT-003: implementação do Akira")
