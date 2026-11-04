"""Pacote principal do projeto: a camada de sustentação do modelo de Credit Scoring.

O que faz: reúne os módulos config, data, model, contracts, monitoring e drift.
Por que existe: com um pacote, os scripts e testes importam o mesmo código de um lugar só.
Onde entra no fluxo: é a base de tudo; o trabalho real está nos módulos e em scripts/.
"""


def main() -> None:
    """Responde ao comando credit-risk-observability, declarado no pyproject.toml.

    Recebe: nada.
    Faz: imprime uma saudação. É o exemplo criado com o projeto, sem papel no pipeline.
    Devolve: nada.
    """
    print("Hello from credit-risk-observability!")
