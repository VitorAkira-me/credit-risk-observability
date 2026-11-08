"""OBS-002: painel estático das semanas, lido do MLflow, para o README e o vídeo.

O que faz: busca os runs do experimento no MLflow e desenha três gráficos lado a lado (um por
régua): AUC contra o piso, taxa de default contra o intervalo e PSI máximo contra 0,25.
Semanas com alerta ganham marcador vermelho e o texto "alerta"; a semana barrada no contrato
aparece como texto, porque ela não tem AUC (e zero no gráfico pareceria um modelo péssimo).
Por que existe: a UI do MLflow é o painel vivo; esta figura é a evidência versionada dele.
Onde entra no fluxo: depois de run_weekly_pipeline.py.

Uso:
    uv run python scripts/plot_weekly_panel.py
"""

import os

os.environ.setdefault("MLFLOW_DISABLE_TELEMETRY", "true")
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")  # desenha em arquivo, sem abrir janela
import matplotlib.pyplot as plt
import mlflow

from credit_risk_observability.config import (
    ALERT_THRESHOLDS_PATH,
    MLFLOW_EXPERIMENT,
    MLFLOW_TRACKING_URI,
    REPORTS_DIR,
)

PANEL_PATH = REPORTS_DIR / "figures" / "painel_semanas.png"
SERIES = "#2a78d6"  # cor da série (azul)
CRITICAL = "#d03b3b"  # cor reservada para alerta, sempre com o texto "alerta" ao lado
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
BAND = "#e6e5e1"


def load_runs(tracking_uri: str = MLFLOW_TRACKING_URI):
    """Os runs do experimento, em ordem de semana."""
    mlflow.set_tracking_uri(tracking_uri)
    runs = mlflow.search_runs(experiment_names=[MLFLOW_EXPERIMENT])
    runs["semana"] = runs["params.semana"].astype(int)
    return runs.sort_values("semana").reset_index(drop=True)


def _panel(ax, runs, metric: str, alert_tag: str, title: str, fmt: str) -> None:
    """Uma régua: linha da métrica por semana, marcador vermelho onde a tag de alerta ligou."""
    ok = runs[runs["tags.status"] == "sucesso"]
    ax.plot(ok["semana"], ok[metric], color=SERIES, linewidth=2, zorder=3)
    for _, row in ok.iterrows():
        alert = row[alert_tag] == "true"
        ax.scatter(
            row["semana"],
            row[metric],
            s=70,
            zorder=4,
            color=CRITICAL if alert else SERIES,
            edgecolor="white",
            linewidth=2,
        )
        # Vírgula decimal: o projeto é em português.
        label = f"{row[metric]:{fmt}}".replace(".", ",") + ("\nalerta" if alert else "")
        ax.annotate(
            label,
            (row["semana"], row[metric]),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=8.5,
            color=CRITICAL if alert else INK,
        )
    for _, row in runs[runs["tags.status"] == "falha"].iterrows():
        ax.text(
            row["semana"],
            0.12,
            "barrada\nno contrato",
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="center",
            fontsize=8.5,
            color=INK_SECONDARY,
        )
    ax.set_title(title, fontsize=10.5, color=INK, loc="left")
    ax.set_xticks(runs["semana"])
    ax.set_xlim(runs["semana"].min() - 0.4, runs["semana"].max() + 0.5)
    ax.set_xlabel("semana", fontsize=9, color=INK_SECONDARY)
    ax.margins(y=0.25)
    ax.grid(axis="y", color=BAND, linewidth=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=INK_SECONDARY, labelsize=8.5)


def draw(runs, thresholds: dict, path: Path) -> Path:
    """Desenha os três gráficos e grava o PNG."""
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), dpi=150)

    _panel(axes[0], runs, "metrics.roc_auc", "tags.alerta_auc", "AUC do modelo", ".3f")
    axes[0].axhline(thresholds["auc_floor"], color=INK_SECONDARY, linestyle="--", linewidth=1)
    floor = f"{thresholds['auc_floor']:.3f}".replace(".", ",")
    axes[0].text(
        0.02,
        thresholds["auc_floor"],
        f"piso {floor}",
        transform=axes[0].get_yaxis_transform(),
        ha="left",
        va="top",
        fontsize=8,
        color=INK_SECONDARY,
    )

    _panel(
        axes[1],
        runs,
        "metrics.taxa_default",
        "tags.alerta_taxa_default",
        "Taxa de default do lote",
        ".1%",
    )
    axes[1].axhspan(
        thresholds["default_rate_low"], thresholds["default_rate_high"], color=BAND, zorder=1
    )
    axes[1].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    axes[1].text(
        0.02,
        thresholds["default_rate_low"],
        "intervalo sem drift (95%)",
        transform=axes[1].get_yaxis_transform(),
        ha="left",
        va="bottom",
        fontsize=8,
        color=INK_SECONDARY,
    )

    _panel(
        axes[2], runs, "metrics.psi_max", "tags.drift_alert", "PSI máximo entre as features", ".2f"
    )
    axes[2].axhline(thresholds["psi_limit"], color=INK_SECONDARY, linestyle="--", linewidth=1)
    axes[2].text(
        0.02,
        thresholds["psi_limit"],
        f"limite {thresholds['psi_limit']}".replace(".", ","),
        transform=axes[2].get_yaxis_transform(),
        ha="left",
        va="bottom",
        fontsize=8,
        color=INK_SECONDARY,
    )

    fig.suptitle(
        f"Monitoramento semanal: lotes de {thresholds['batch_size']} clientes, "
        "drift crescente da semana 1 (nenhum) à 4 (cheio)",
        fontsize=11.5,
        color=INK,
        x=0.01,
        ha="left",
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="#fcfcfb")
    plt.close(fig)
    return path


def main() -> int:
    """Lê do MLflow e dos limites calibrados e grava o painel."""
    runs = load_runs()
    if runs.empty:
        print("Nenhum run no MLflow: rode run_weekly_pipeline.py antes.")
        return 1
    thresholds = json.loads(ALERT_THRESHOLDS_PATH.read_text(encoding="utf-8"))
    path = draw(runs, thresholds, PANEL_PATH)
    print(f"Painel com {len(runs)} semanas gravado em {path.relative_to(REPORTS_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
