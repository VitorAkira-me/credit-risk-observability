"""ML-001: treina o baseline na Referência e salva modelo + métricas.

O que faz: treina o modelo simples de referência e mede a qualidade dele.
Por que existe: para saber se o modelo piorou com o drift, é preciso medi-lo antes.
Onde entra no fluxo: depois de prepare_data.py e antes da medição de drift.

Uso:
    uv run python scripts/train_baseline.py

Métricas em dois conjuntos:
- validation: 20% da Referência que o modelo não viu no treino;
- production_base: Produção ainda sem drift (grupo de controle do DRIFT-002).
"""

import json
import logging
import platform

import joblib
import pandas as pd
import sklearn
from sklearn.model_selection import train_test_split

from credit_risk_observability.config import (
    DECISION_THRESHOLD,
    METRICS_PATH,
    MODEL_FEATURES,
    MODEL_PATH,
    PRODUCTION_BASE_PATH,
    REFERENCE_PATH,
    SEED,
    SENSITIVE_EXCLUDED,
    SPLIT_METADATA_PATH,
    TARGET,
    VALIDATION_SIZE,
)
from credit_risk_observability.model.predict import predict_proba
from credit_risk_observability.model.train import build_pipeline, evaluate

logger = logging.getLogger("train_baseline")


def main() -> None:
    """Treina, mede e salva o modelo.

    Recebe: nada; lê os dados de config.py.
    Faz: separa 20% da Referência para validação, treina no resto e mede nos três conjuntos.
    Devolve: nada; grava o modelo e as métricas. AUC esperado na Produção-base: cerca de 0,715.
    """
    reference = pd.read_parquet(REFERENCE_PATH)
    production = pd.read_parquet(PRODUCTION_BASE_PATH)

    # stratify: treino e validação ficam com a mesma taxa de default.
    train, validation = train_test_split(
        reference, test_size=VALIDATION_SIZE, stratify=reference[TARGET], random_state=SEED
    )
    logger.info("Treino %d linhas, validação %d linhas", len(train), len(validation))

    # O fit usa só o treino: a validação e a Produção precisam ser dados que o modelo não viu.
    model = build_pipeline().fit(train[MODEL_FEATURES], train[TARGET])

    metrics = {
        "model": "LogisticRegression(class_weight=balanced)",
        "features": MODEL_FEATURES,
        "excluded_sensitive": SENSITIVE_EXCLUDED,
        "threshold": DECISION_THRESHOLD,
        "seed": SEED,
        # Versões registradas: um modelo pode mudar de resultado entre versões de biblioteca.
        "versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__},
        "data": json.loads(SPLIT_METADATA_PATH.read_text(encoding="utf-8")),
        "metrics": {
            name: evaluate(df[TARGET], predict_proba(model, df), DECISION_THRESHOLD)
            for name, df in (
                ("train", train),
                ("validation", validation),
                ("production_base", production),
            )
        },
    }

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Modelo salvo em %s", MODEL_PATH)
    for name, values in metrics["metrics"].items():
        logger.info("%-16s %s", name, values)

    print(
        "Modelo treinado e salvo. AUC (qualidade da ordenação dos clientes, de 0,5 a 1,0): "
        f"{metrics['metrics']['validation']['roc_auc']:.4f} na validação e "
        f"{metrics['metrics']['production_base']['roc_auc']:.4f} na Produção-base."
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    main()
