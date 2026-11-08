"""GOV-004: experimento de dose-resposta, um drift de cada vez.

O que faz: aplica data drift e concept drift separadamente, em 5 doses, na Produção-base; mede AUC
e impacto no negócio; grava reports/causal/dose_resposta.json e o gráfico em reports/figures/.
Por que existe: é a evidência da análise causal do README. Correlação na série semanal não prova
causa; intervenção controlada prova.
Onde entra no fluxo: depois de train_baseline.py.

Uso:
    uv run python scripts/run_causal_analysis.py
"""

import json
import sys

import matplotlib

matplotlib.use("Agg")  # desenha em arquivo, sem abrir janela
import matplotlib.pyplot as plt
import pandas as pd

from credit_risk_observability.config import (
    MODEL_PATH,
    PRODUCTION_BASE_PATH,
    REPORTS_DIR,
)
from credit_risk_observability.governance.causal import dose_response
from credit_risk_observability.model.predict import load_model

REPORT_PATH = REPORTS_DIR / "causal" / "dose_resposta.json"
FIGURE_PATH = REPORTS_DIR / "figures" / "dose_resposta.png"
COLORS = {"data_drift": "#2a78d6", "concept_drift": "#eb6834"}  # azul e laranja
LABELS = {
    "data_drift": "data drift (faturas e limite)",
    "concept_drift": "concept drift (rótulos)",
}
INK, INK_SECONDARY, GRID = "#0b0b0b", "#52514e", "#e6e5e1"


def draw(rows: pd.DataFrame) -> None:
    """Dois gráficos lado a lado, cada um com um só eixo: AUC e calotes aprovados por dose."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), dpi=150)
    panels = (
        ("roc_auc", "AUC do modelo", "{:.3f}"),
        ("calote_aprovado", "Calotes aprovados (de 9.000 clientes)", "{:.0f}"),
    )
    for ax, (metric, title, fmt) in zip(axes, panels, strict=True):
        for scenario, part in rows.groupby("cenario"):
            ax.plot(
                part["dose"],
                part[metric],
                color=COLORS[scenario],
                linewidth=2,
                marker="o",
                markersize=7,
                markeredgecolor="white",
                markeredgewidth=1.5,
            )
            last = part.iloc[-1]
            ax.annotate(
                f"{LABELS[scenario]}\n" + fmt.format(last[metric]).replace(".", ","),
                (last["dose"], last[metric]),
                textcoords="offset points",
                xytext=(8, 0),
                va="center",
                fontsize=8.5,
                color=INK,
            )
        ax.set_title(title, fontsize=10.5, color=INK, loc="left")
        ax.set_xlabel(
            "dose do drift (0 = nenhum, 1 = cenário cheio)", fontsize=9, color=INK_SECONDARY
        )
        ax.set_xlim(-0.05, 1.6)  # espaço à direita para os rótulos; as marcas vão só até 1
        ax.set_xticks(sorted(rows["dose"].unique()))
        ax.margins(y=0.12)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.tick_params(colors=INK_SECONDARY, labelsize=8.5)
    fig.suptitle(
        "Um drift de cada vez: qual deles derruba o modelo?",
        fontsize=11.5,
        color=INK,
        x=0.01,
        ha="left",
    )
    fig.tight_layout()
    FIGURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PATH, facecolor="#fcfcfb")
    plt.close(fig)


def main() -> int:
    """Roda o experimento, grava o JSON e o gráfico e imprime a tabela."""
    rows = dose_response(pd.read_parquet(PRODUCTION_BASE_PATH), load_model(MODEL_PATH))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    table = pd.DataFrame(rows)
    draw(table)
    print(table.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
