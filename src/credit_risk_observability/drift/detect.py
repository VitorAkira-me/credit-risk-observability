"""Mede o drift de um lote e dá um diagnóstico em quatro quadrantes (DRIFT-002).

O que faz: compara o lote com a Referência (features, alvo e score do modelo), mede a performance
do modelo no lote e cruza os resultados em um diagnóstico simples de explicar.
Por que existe: olhar só as features não basta. No concept drift, as entradas ficam iguais e só a
performance denuncia o problema, como mostrou o DRIFT-001.
Onde entra no fluxo: scripts/run_drift_report.py chama estas funções depois de conferir o contrato.
Estas funções não leem nem gravam arquivo, o que permite testá-las com dados pequenos.

Termos usados aqui:
- PSI: mede o quanto a distribuição de uma coluna mudou, comparando faixas de valores. Valor alto é
  mudança.
- KS: teste que compara as curvas acumuladas de duas amostras. Devolve um p-valor, e p-valor baixo
  é evidência de mudança. A direção é oposta à do PSI.
- AUC: mede o quanto o modelo ordena bem os clientes. 0,5 é sorteio e 1,0 é perfeito.
- Score: a probabilidade de default que o modelo dá a um cliente.
"""

from html import escape
import os

# Desliga o envio de dados de uso do Evidently. Vem antes do import para valer desde o início.
os.environ["DO_NOT_TRACK"] = "1"

from evidently import DataDefinition, Dataset, Report
from evidently.core.report import Snapshot
from evidently.metrics import ValueDrift
from evidently.presets import DataDriftPreset
import pandas as pd
from sklearn.pipeline import Pipeline

from credit_risk_observability.config import (
    CATEGORICAL_COLUMNS,
    DECISION_THRESHOLD,
    FEATURE_COLUMNS,
    TARGET,
)
from credit_risk_observability.model.predict import predict_proba
from credit_risk_observability.model.train import evaluate

# Régua do diagnóstico, decidida na spec do DRIFT-002.
PSI_LIMIT = 0.25  # acima disto, a feature mudou
KS_P_VALUE_LIMIT = 0.05  # abaixo disto, a feature mudou
# Nossa régua é "alguma feature mudou". O padrão do Evidently só declara drift do conjunto com
# 50% das colunas: o HTML diria "sem drift" logo abaixo do nosso diagnóstico de data drift.
DATASET_DRIFT_SHARE = 1 / len(FEATURE_COLUMNS)

# Performance da Produção-base, o controle do ML-001. IC é o intervalo de confiança de 95%: a faixa
# em que a AUC costuma variar só por acaso, sem nada ter mudado.
CONTROL_AUC = 0.7149
CONTROL_AUC_CI_LOW = 0.701
CONTROL_AUC_CI_HIGH = 0.728

SCORE_COLUMN = "score"  # só existe em memória: nunca é gravada no parquet do lote

DIAGNOSIS_NO_DRIFT = "sem drift relevante"
DIAGNOSIS_DATA_DRIFT_NO_IMPACT = "data drift sem impacto no modelo"
DIAGNOSIS_CONCEPT_DRIFT = "suspeita de concept drift"
DIAGNOSIS_DATA_DRIFT_WITH_IMPACT = "data drift com impacto"

_NUMERIC_FEATURES = [column for column in FEATURE_COLUMNS if column not in CATEGORICAL_COLUMNS]


def features_changed_by_psi(psi_by_feature: dict[str, float]) -> list[str]:
    """Aponta as features que mudaram pela régua do PSI.

    Recebe: o PSI de cada feature.
    Faz: fica com as que passam de PSI_LIMIT. Exatamente no limite não conta.
    Devolve: os nomes, na ordem recebida. Exemplo: {"A": 0.25, "B": 0.3} devolve ["B"].
    """
    return [feature for feature, psi in psi_by_feature.items() if psi > PSI_LIMIT]


def features_changed_by_ks(p_value_by_feature: dict[str, float]) -> list[str]:
    """Aponta as features que mudaram pela régua do KS.

    Recebe: o p-valor do KS de cada feature.
    Faz: fica com as que estão abaixo de KS_P_VALUE_LIMIT. Exatamente no limite não conta.
    Devolve: os nomes, na ordem recebida. Exemplo: {"A": 0.05, "B": 0.01} devolve ["B"].
    """
    return [
        feature for feature, p_value in p_value_by_feature.items() if p_value < KS_P_VALUE_LIMIT
    ]


def performance_dropped(auc: float) -> bool:
    """Diz se a performance do lote caiu.

    Recebe: a AUC do lote.
    Faz: compara com o limite inferior do IC da Produção-base. Acima dele, pode ser só acaso.
    Devolve: True se caiu. Exemplo: 0,66 devolve True, e 0,714 devolve False.
    """
    return auc < CONTROL_AUC_CI_LOW


def diagnose(features_changed: bool, dropped: bool) -> str:
    """Cruza as duas perguntas nos quatro quadrantes.

    Recebe: se alguma feature mudou e se a performance caiu.
    Faz: escolhe o quadrante. É um mostrador: decidir o que vira alerta é papel do OBS-002.
    Devolve: o texto do diagnóstico. Exemplo: (False, True) devolve "suspeita de concept drift".
    """
    if features_changed and dropped:
        return DIAGNOSIS_DATA_DRIFT_WITH_IMPACT
    if features_changed:
        return DIAGNOSIS_DATA_DRIFT_NO_IMPACT
    if dropped:
        return DIAGNOSIS_CONCEPT_DRIFT
    return DIAGNOSIS_NO_DRIFT


def _select_and_score(df: pd.DataFrame, model: Pipeline) -> pd.DataFrame:
    """Prepara uma tabela para o Evidently.

    Recebe: os clientes e o modelo.
    Faz: fica só com features e alvo, deixando o ID de fora (ADR-005), e acrescenta o score.
    Devolve: uma tabela nova, sem o ID e com o score; a original não muda.
    """
    selected = df[[*FEATURE_COLUMNS, TARGET]].copy()
    selected[SCORE_COLUMN] = predict_proba(model, df)
    return selected


def _run_evidently(reference: pd.DataFrame, batch: pd.DataFrame) -> Snapshot:
    """Roda o Evidently com métodos e limiares explícitos.

    Recebe: a Referência e o lote, já sem o ID e com o score.
    Faz: declara o tipo de cada coluna (sem isso, ele trata PAY_0 como número e PAY_2 como
        categoria) e pede os dois métodos. Os limiares são explícitos para o HTML concordar com
        o diagnóstico: o padrão de PSI dele é 0,1, e não 0,25. KS exige números, então as
        categóricas usam PSI.
    Devolve: o Snapshot, o resultado do Evidently, com os valores e o HTML.
    """
    definition = DataDefinition(
        numerical_columns=[*_NUMERIC_FEATURES, SCORE_COLUMN],
        categorical_columns=[*CATEGORICAL_COLUMNS, TARGET],
    )
    report = Report(
        [
            DataDriftPreset(
                columns=FEATURE_COLUMNS,
                drift_share=DATASET_DRIFT_SHARE,
                method="psi",
                threshold=PSI_LIMIT,
            ),
            DataDriftPreset(
                columns=FEATURE_COLUMNS,
                drift_share=DATASET_DRIFT_SHARE,
                num_method="ks",
                num_threshold=KS_P_VALUE_LIMIT,
                cat_method="psi",
                cat_threshold=PSI_LIMIT,
            ),
            ValueDrift(column=TARGET, method="psi", threshold=PSI_LIMIT),
            ValueDrift(column=SCORE_COLUMN, method="psi", threshold=PSI_LIMIT),
            ValueDrift(column=SCORE_COLUMN, method="ks", threshold=KS_P_VALUE_LIMIT),
        ]
    )
    # Ordem da API: primeiro o lote (current), depois a Referência.
    return report.run(
        Dataset.from_pandas(batch, data_definition=definition),
        Dataset.from_pandas(reference, data_definition=definition),
    )


def _drift_values(snapshot: Snapshot) -> dict[tuple[str, str], float]:
    """Lê os valores de drift por coluna e método.

    Recebe: o Snapshot do Evidently.
    Faz: percorre as métricas ValueDrift. O dict() traz só o valor: o limiar não decide nada aqui,
        porque a régua é aplicada pelas nossas funções.
    Devolve: um dicionário. Exemplo: {("LIMIT_BAL", "psi"): 0.27, ("LIMIT_BAL", "ks"): 1e-145}.
    """
    values = {}
    for metric in snapshot.dict()["metrics"]:
        config = metric["config"]
        if metric["metric_name"].startswith("ValueDrift("):
            values[(config["column"], config["method"])] = float(metric["value"])
    return values


def analyze_batch(
    reference: pd.DataFrame, batch: pd.DataFrame, model: Pipeline
) -> tuple[Snapshot, dict]:
    """Mede os três blocos do relatório e dá o diagnóstico.

    Recebe: a Referência, o lote e o modelo treinado.
    Faz: (a) drift das features e (b) taxa de default e score, contra a Referência;
        (c) performance, contra a Produção-base. Depois cruza (a) e (c) no diagnóstico.
    Devolve: o Snapshot, para o HTML, e um dicionário com os blocos, só com números agregados.
    """
    if TARGET not in batch.columns:
        # O contrato aceita lote sem alvo, mas aqui a performance não poderia ser medida.
        raise ValueError(f"Lote sem a coluna {TARGET}: não dá para medir a performance")
    if batch[TARGET].nunique() < 2:
        # A AUC precisa das duas classes. Sem isso ela vira NaN, e NaN nunca é "abaixo do limite":
        # o relatório diria "sem drift relevante" sem ter medido nada (sucesso vazio).
        raise ValueError(f"Lote com uma classe só em {TARGET}: não dá para medir a AUC")

    reference_scored = _select_and_score(reference, model)
    batch_scored = _select_and_score(batch, model)
    snapshot = _run_evidently(reference_scored, batch_scored)
    values = _drift_values(snapshot)

    psi_by_feature = {feature: values[(feature, "psi")] for feature in FEATURE_COLUMNS}
    p_value_by_feature = {feature: values[(feature, "ks")] for feature in _NUMERIC_FEATURES}
    changed_by_psi = features_changed_by_psi(psi_by_feature)
    changed_by_ks = features_changed_by_ks(p_value_by_feature)

    metrics = evaluate(batch[TARGET], batch_scored[SCORE_COLUMN].to_numpy(), DECISION_THRESHOLD)
    dropped = performance_dropped(metrics["roc_auc"])
    features_changed = bool(changed_by_psi or changed_by_ks)

    analysis = {
        "feature_drift": {
            "psi_limit": PSI_LIMIT,
            "ks_p_value_limit": KS_P_VALUE_LIMIT,
            "reference": "Referência",
            "features": {
                feature: {
                    "psi": psi_by_feature[feature],
                    # Categóricas não têm KS: None deixa claro que não foi medido, nem deu zero.
                    "ks_p_value": p_value_by_feature.get(feature),
                }
                for feature in FEATURE_COLUMNS
            },
            "changed_by_psi": changed_by_psi,
            "changed_by_ks": changed_by_ks,
        },
        "target_and_score": {
            "default_rate_batch": float(batch[TARGET].mean()),
            "default_rate_reference": float(reference[TARGET].mean()),
            "default_psi": values[(TARGET, "psi")],
            "score_mean_batch": float(batch_scored[SCORE_COLUMN].mean()),
            "score_mean_reference": float(reference_scored[SCORE_COLUMN].mean()),
            "score_psi": values[(SCORE_COLUMN, "psi")],
            "score_ks_p_value": values[(SCORE_COLUMN, "ks")],
        },
        "performance": {
            "roc_auc": metrics["roc_auc"],
            "recall_default": metrics["recall_default"],
            "precision_default": metrics["precision_default"],
            "compared_with": "Produção-base",
            "control_auc": CONTROL_AUC,
            "control_ci_low": CONTROL_AUC_CI_LOW,
            "control_ci_high": CONTROL_AUC_CI_HIGH,
            "dropped": dropped,
        },
        "diagnosis": {
            "text": diagnose(features_changed, dropped),
            "features_changed": features_changed,
            "performance_dropped": dropped,
        },
    }
    return snapshot, analysis


def render_summary_section(summary: dict) -> str:
    """Escreve o resumo em português que abre o HTML.

    Recebe: o resumo do lote.
    Faz: monta os três blocos. A performance fica aqui, e não nos gráficos do Evidently, porque
        ele a compararia com a Referência, e a régua compara com a Produção-base.
    Devolve: um trecho de HTML. Exemplo: começa por "Diagnóstico: sem drift relevante".
    """
    features = summary["feature_drift"]
    target = summary["target_and_score"]
    performance = summary["performance"]
    changed_by_psi = ", ".join(features["changed_by_psi"]) or "nenhuma"
    changed_by_ks = ", ".join(features["changed_by_ks"]) or "nenhuma"
    dropped_text = "caiu" if performance["dropped"] else "estável"
    # escape: o nome do lote vem de um arquivo, e não pode virar código dentro da página.
    return f"""
<section style="font-family: sans-serif; max-width: 900px; margin: 24px auto; padding: 0 16px;">
  <h1>Lote {escape(summary["batch"])}</h1>
  <h2>Diagnóstico: {escape(summary["diagnosis"]["text"])}</h2>
  <p>Este resumo cruza duas perguntas: as features mudaram? A performance caiu? Os gráficos do
  Evidently, logo abaixo, detalham as features, o alvo e o score. Neles, o limite de drift do
  conjunto ({DATASET_DRIFT_SHARE:.4f}) significa "ao menos 1 das {len(FEATURE_COLUMNS)} colunas".
  Primeiro vem a tabela do PSI e, depois, a do KS.</p>
  <h3>a) Drift das features, contra a Referência</h3>
  <p>Mudaram pelo PSI (acima de {features["psi_limit"]}): {escape(changed_by_psi)}.<br>
  Mudaram pelo KS (p-valor abaixo de {features["ks_p_value_limit"]}): {escape(changed_by_ks)}.</p>
  <h3>b) Alvo e score, contra a Referência</h3>
  <p>Taxa real de default: {target["default_rate_batch"]:.2%} no lote e
  {target["default_rate_reference"]:.2%} na Referência.<br>
  Score médio: {target["score_mean_batch"]:.4f} no lote e
  {target["score_mean_reference"]:.4f} na Referência
  (PSI {target["score_psi"]:.4f}; KS p-valor {target["score_ks_p_value"]:.3g}).</p>
  <h3>c) Performance, contra a Produção-base</h3>
  <p>AUC {performance["roc_auc"]:.4f}: {dropped_text}. Na Produção-base, a AUC é
  {performance["control_auc"]:.4f}, com IC 95% de {performance["control_ci_low"]} a
  {performance["control_ci_high"]}.<br>
  Recall: {performance["recall_default"]:.4f}.
  Precisão: {performance["precision_default"]:.4f}.</p>
  <hr>
</section>
"""


def add_section_to_html(html: str, section: str) -> str:
    """Coloca o resumo no início da página do Evidently.

    Recebe: o HTML do Evidently e o trecho a inserir.
    Faz: insere logo depois da abertura de <body>. Se não houver exatamente uma, dá erro: é melhor
        parar do que entregar um relatório sem o diagnóstico.
    Devolve: o HTML completo.
    """
    if html.count("<body>") != 1:
        raise ValueError("HTML do Evidently fora do esperado: não achei uma única tag <body>")
    return html.replace("<body>", f"<body>{section}")
