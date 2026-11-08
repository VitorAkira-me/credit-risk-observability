"""GOV-003: auditoria de viés por sexo e faixa etária, antes e depois do drift.

O que faz: mede as taxas de aprovação por grupo na Referência, na Produção-base e nos dois lotes
com drift; testa se as features adivinham o sexo (proxy) e compara a disparidade do modelo atual
(sem SEX e MARRIAGE) com a de um modelo que os usa. Grava reports/fairness/fairness_report.json.
Por que existe: é a evidência numérica da seção de vieses do README (Etapa 4).
Onde entra no fluxo: depois de train_baseline.py e make_drift_batch.py.

Uso:
    uv run python scripts/run_fairness.py

Privacidade: o relatório tem só taxas agregadas por grupo, com milhares de clientes em cada um.
"""

import json
import sys

import pandas as pd

from credit_risk_observability.config import (
    MODEL_PATH,
    PRODUCTION_BASE_PATH,
    PRODUCTION_DIR,
    REFERENCE_PATH,
    REPORTS_DIR,
    TARGET,
)
from credit_risk_observability.governance.fairness import (
    COUNTERFACTUALS,
    audit,
    build_counterfactual,
    proxy_strength,
)
from credit_risk_observability.model.predict import load_model

FAIRNESS_REPORT_PATH = REPORTS_DIR / "fairness" / "fairness_report.json"
DATASETS = {
    "referencia": REFERENCE_PATH,
    "producao_base": PRODUCTION_BASE_PATH,
    "data_drift": PRODUCTION_DIR / "batch_data_drift_i100.parquet",
    "concept_drift": PRODUCTION_DIR / "batch_concept_drift_i100.parquet",
}


def main() -> int:
    """Roda a auditoria e grava o relatório.

    Recebe: nada; usa os caminhos de config.py.
    Faz: audita cada conjunto com o modelo do ML-001, mede o proxy e roda o contrafactual.
    Devolve: o exit code (0).
    """
    model = load_model(MODEL_PATH)
    data = {name: pd.read_parquet(path) for name, path in DATASETS.items()}
    report = {"conjuntos": {name: audit(df, model) for name, df in data.items()}}

    # Tirar a coluna resolve? (1) As outras features adivinham o sexo? (2) Contrafactuais: o mesmo
    # modelo com SEX e MARRIAGE, e sem AGE, treinados na mesma Referência e medidos na Produção-base.
    reference = data["referencia"]
    report["proxy"] = {"auc_features_preveem_sexo": proxy_strength(reference)}
    report["contrafactuais_producao_base"] = {}
    for name, (categorical, numeric) in COUNTERFACTUALS.items():
        features = [*categorical, *numeric]
        model_cf = build_counterfactual(categorical, numeric).fit(
            reference[features], reference[TARGET]
        )
        report["contrafactuais_producao_base"][name] = audit(
            data["producao_base"], model_cf, features
        )

    FAIRNESS_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    FAIRNESS_REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    for name, result in report["conjuntos"].items():
        sex, age = result["sexo"]["diferencas"], result["idade"]["diferencas"]
        print(
            f"{name:14s} AUC {result['roc_auc']:.4f}, aprovação {result['taxa_aprovacao_geral']:.1%} | sexo: paridade "
            f"{sex['paridade_demografica']:.3f}, oportunidade {sex['igualdade_oportunidade']:.3f}, "
            f"razão {sex['razao_impacto']:.3f} | idade: paridade {age['paridade_demografica']:.3f}, "
            f"oportunidade {age['igualdade_oportunidade']:.3f}, razão {age['razao_impacto']:.3f}"
        )
    print(
        f"Proxy: as features do modelo preveem o sexo com AUC {report['proxy']['auc_features_preveem_sexo']}."
    )
    for name, result in report["contrafactuais_producao_base"].items():
        sex, age = result["sexo"]["diferencas"], result["idade"]["diferencas"]
        print(
            f"Contrafactual {name}: AUC {result['roc_auc']:.4f}; sexo paridade {sex['paridade_demografica']:.3f}; idade paridade "
            f"{age['paridade_demografica']:.3f}, razão {age['razao_impacto']:.3f}"
        )
    print(f"Relatório: {FAIRNESS_REPORT_PATH.relative_to(REPORTS_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
