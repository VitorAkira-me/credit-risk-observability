"""GOV-002: aplica a política de retenção às saídas locais (outputs/ e logs/).

O que faz: lista o que passou do prazo; com --aplicar, apaga.
Por que existe: o prazo de retenção do README precisa acontecer de fato, não só estar escrito.
Onde entra no fluxo: à mão ou num agendador (ex.: semanal). Não toca em data/ nem em reports/.

Uso:
    uv run python scripts/apply_retention.py            # simulação: só lista
    uv run python scripts/apply_retention.py --aplicar  # apaga de verdade
"""

import argparse
import sys

from credit_risk_observability.config import PROJECT_ROOT
from credit_risk_observability.governance.retention import (
    FILE_RETENTION_DAYS,
    LOG_RETENTION_DAYS,
    apply_retention,
)


def main(argv: list[str] | None = None) -> int:
    """Roda a política e imprime o resultado."""
    parser = argparse.ArgumentParser(description="Aplica a retenção das saídas locais (GOV-002)")
    parser.add_argument("--aplicar", action="store_true", help="apaga de fato (padrão: simula)")
    args = parser.parse_args(argv)

    result = apply_retention(apply=args.aplicar)
    verb = "Apagados" if args.aplicar else "Seriam apagados (simulação)"
    prazos = ", ".join(
        f"{p.relative_to(PROJECT_ROOT)}: {d} dias" for p, d in FILE_RETENTION_DAYS.items()
    )
    print(f"Prazos: {prazos}; log: {LOG_RETENTION_DAYS} dias.")
    print(f"{verb}: {len(result.files)} arquivos e {result.log_lines_removed} linhas do log.")
    for path in result.files:
        print(f"  {path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
