"""Testes do DRIFT-003: o que a função psi() precisa cumprir.

O que faz: define o comportamento certo antes do código existir (é o "contrato" do Akira).
Por que existe: enquanto psi() não está implementada, os testes são pulados e o CI fica verde;
quando o Akira implementar, eles passam a valer sozinhos.
Onde entra no fluxo: roda no pytest.
"""

import numpy as np
import pytest

from credit_risk_observability.drift import manual


def call_psi(*args, **kwargs) -> float:
    """Chama psi(); se ainda não foi implementada, pula o teste em vez de falhar."""
    try:
        return manual.psi(*args, **kwargs)
    except NotImplementedError:
        pytest.skip("psi() ainda não implementada (DRIFT-003, Akira pilota)")


def test_series_against_itself_is_zero():
    """Critério do card: nada mudou, PSI zero."""
    values = np.random.default_rng(0).normal(size=5_000)

    assert call_psi(values, values) == pytest.approx(0.0, abs=1e-12)


def test_known_value_computed_by_hand():
    """Duas faixas: Referência 50% e 50%; lote 25% e 75%.

    (0,25 - 0,50) * ln(0,25 / 0,50) + (0,75 - 0,50) * ln(0,75 / 0,50)
    = 0,1733 + 0,1014 = 0,2747. Faça a conta no papel antes de rodar.
    """
    reference = np.array([0.0, 0.0, 1.0, 1.0])
    current = np.array([0.0, 1.0, 1.0, 1.0])
    edges = np.array([-0.5, 0.5, 1.5])

    assert call_psi(reference, current, bins=edges) == pytest.approx(0.2747, abs=1e-4)


def test_psi_is_symmetric():
    """Trocar Referência e lote não muda o PSI. Olhe a fórmula: por quê?"""
    rng = np.random.default_rng(1)
    a, b = rng.normal(0, 1, 3_000), rng.normal(0.5, 1, 3_000)
    edges = np.linspace(-4, 5, 11)

    assert call_psi(a, b, bins=edges) == pytest.approx(call_psi(b, a, bins=edges))


def test_bigger_shift_gives_bigger_psi():
    """Mais deslocamento, mais PSI: é o que permite usar o PSI como régua."""
    rng = np.random.default_rng(2)
    reference = rng.normal(0, 1, 5_000)
    small = call_psi(reference, reference + 0.1)
    big = call_psi(reference, reference + 1.0)

    assert 0 < small < 0.1  # deslocamento pequeno: "estável" na régua
    assert big > 0.25  # deslocamento grande: "mudança relevante"


def test_empty_bin_does_not_explode():
    """Uma faixa sem ninguém no lote: o resultado precisa ser finito (a pergunta do card)."""
    reference = np.array([0.0, 1.0, 2.0, 3.0])
    current = np.array([0.0, 0.0, 1.0, 1.0])  # ninguém nas faixas de 2 e 3
    edges = np.array([-0.5, 0.5, 1.5, 2.5, 3.5])

    result = call_psi(reference, current, bins=edges)

    assert np.isfinite(result) and result > 0
