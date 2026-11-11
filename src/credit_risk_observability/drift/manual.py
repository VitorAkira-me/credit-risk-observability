"""DRIFT-003: PSI calculado à mão, para tirar a caixa-preta do Evidently.

QUEM FEZ: implementado pelo Claude em 10/11/2026, por decisão do Akira, para não travar a entrega.
O Akira refaz esta função à mão no repasse (PMF4-38): os testes em tests/test_psi_manual.py são o
contrato, e voltam a ser pulados se o corpo da função der lugar a um NotImplementedError.

O que faz: mede o quanto a distribuição de uma coluna mudou entre a Referência e um lote.
Por que existe: para saber o que a biblioteca faz por baixo e conferir se os números batem
(scripts/compare_psi.py compara com o Evidently).
Onde entra no fluxo: não entra no pipeline; é ferramenta de aprendizado e de conferência.

A fórmula, por faixa i:  (atual%_i - ref%_i) * ln(atual%_i / ref%_i), e o PSI é a soma.
Régua usual: abaixo de 0,1 estável; de 0,1 a 0,25 atenção; acima de 0,25 mudança relevante.
"""

import numpy as np

EPSILON = 1e-4  # o que entra no lugar de uma proporção zero: ln(0) não existe


def quantile_edges(reference: np.ndarray, bins: int) -> np.ndarray:
    """Calcula as bordas das faixas a partir dos quantis da Referência.

    Recebe: os valores da Referência e quantas faixas se quer.
    Faz: corta a Referência em faixas com o mesmo número de clientes. Colunas com muitos valores
        repetidos geram bordas iguais, que são removidas; por isso podem sair menos faixas.
    Devolve: as bordas em ordem. Exemplo: 0 a 99 com bins=2 dá [0, 49.5, 99].
    """
    quantiles = np.linspace(0, 1, bins + 1)
    return np.unique(np.quantile(reference, quantiles))


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
        1. define as bordas a partir da REFERÊNCIA, porque ela é a régua fixa: se as bordas
           viessem do lote, a régua mudaria junto com o que ela mede;
        2. abre as bordas externas até o infinito, para um valor do lote fora da faixa da
           Referência contar como mudança, em vez de sumir da conta;
        3. conta quantos valores caem em cada faixa e transforma em proporção;
        4. troca as proporções zero por epsilon;
        5. aplica a fórmula e soma.
    Devolve: o PSI, um número >= 0. Exemplo: uma série contra ela mesma dá 0.
    """
    edges = quantile_edges(reference, bins) if isinstance(bins, int) else np.asarray(bins, float)
    open_edges = edges.astype(float)
    open_edges[0] = -np.inf
    open_edges[-1] = np.inf

    reference_counts, _ = np.histogram(reference, open_edges)
    current_counts, _ = np.histogram(current, open_edges)
    reference_share = reference_counts / reference_counts.sum()
    current_share = current_counts / current_counts.sum()

    # Uma faixa vazia daria ln(0). O epsilon troca o infinito por um número grande e finito.
    reference_share = np.where(reference_share == 0, epsilon, reference_share)
    current_share = np.where(current_share == 0, epsilon, current_share)

    terms = (current_share - reference_share) * np.log(current_share / reference_share)
    return float(terms.sum())
