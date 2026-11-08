"""IMP-001: portão de contrato e de evidência, rodado pelo CI em todo PR e todo merge.

O que faz: com os dados reais recém-gerados, confere três coisas e falha se alguma não vale:
(1) a Produção-base PASSA no contrato; (2) o lote corrompido é BARRADO, com as falhas esperadas;
(3) os lotes regerados têm o mesmo hash (impressão digital) dos lotes citados na evidência
versionada em reports/drift/. Os resumos da validação vão para uma pasta temporária, para o portão
nunca sobrescrever a evidência.
Por que existe: um PR que afrouxa o contrato (o lote corrompido passa) ou que endurece demais (a
Produção-base é barrada) precisa ficar vermelho antes do merge. E se o drift deixar de ser
reproduzível, os relatórios versionados deixam de valer como evidência.
Onde entra no fluxo: .github/workflows/ci.yml, depois de prepare_data, train_baseline,
make_corrupted_batch e make_drift_batch.

Uso:
    uv run python scripts/check_evidence.py

Exit code (o número que o programa devolve ao terminar): 0 = tudo confere; 1 = alguma checagem falhou.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

import pandas as pd

from credit_risk_observability.config import (
    CORRUPTED_BATCH_PATH,
    CORRUPTED_EXPECTED_PATH,
    DRIFT_REPORTS_DIR,
    PRODUCTION_BASE_PATH,
    PRODUCTION_DIR,
    PROJECT_ROOT,
)
from credit_risk_observability.contracts.validate import validate_batch

# Lotes cuja impressão digital está na evidência do DRIFT-002.
EVIDENCE_BATCHES = ("production_base", "batch_data_drift_i100", "batch_concept_drift_i100")


def _load_validation_script():
    """Importa scripts/run_validation.py, o mesmo portão que roda em produção."""
    path = PROJECT_ROOT / "scripts" / "run_validation.py"
    spec = importlib.util.spec_from_file_location("run_validation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_contract_gate() -> list[str]:
    """A Produção-base passa (exit 0) e o lote corrompido é barrado (exit 1) pelo portão real.

    Recebe: nada; usa os lotes em data/production/.
    Faz: roda o portão nos dois lotes, com os relatórios numa pasta temporária, e confere também
        se as falhas do lote corrompido são exatamente as esperadas (nem mais, nem menos).
    Devolve: a lista de problemas; vazia se tudo confere.
    """
    gate = _load_validation_script()
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        if gate.main([str(PRODUCTION_BASE_PATH)], reports_dir=Path(tmp)) != 0:
            problems.append("Produção-base foi BARRADA: o contrato ficou rígido demais.")
        if gate.main([str(CORRUPTED_BATCH_PATH)], reports_dir=Path(tmp)) != 1:
            problems.append("Lote corrompido PASSOU: o contrato deixou de barrar dado sujo.")

    expected = json.loads(CORRUPTED_EXPECTED_PATH.read_text(encoding="utf-8"))
    found = validate_batch(pd.read_parquet(CORRUPTED_BATCH_PATH))
    expected_rules = expected["expected_failures"]
    if found.failures_by_rule != expected_rules:
        problems.append(
            f"Falhas do lote corrompido diferentes do esperado: {found.failures_by_rule} "
            f"em vez de {expected_rules}."
        )
    return problems


def check_evidence_hashes() -> list[str]:
    """Os lotes regerados são idênticos, byte a byte, aos citados nos relatórios versionados.

    Recebe: nada; lê os JSON de reports/drift/ e os lotes de data/production/.
    Faz: compara o sha256 de cada lote com o campo provenance.batch_sha256 do relatório.
    Devolve: a lista de problemas; vazia se tudo confere.
    """
    problems = []
    for name in EVIDENCE_BATCHES:
        report = json.loads(
            (DRIFT_REPORTS_DIR / f"drift_report_{name}.json").read_text(encoding="utf-8")
        )
        expected = report["provenance"]["batch_sha256"]
        found = hashlib.sha256((PRODUCTION_DIR / f"{name}.parquet").read_bytes()).hexdigest()
        if found != expected:
            problems.append(f"{name}: hash {found[:12]} diferente da evidência {expected[:12]}.")
    return problems


def main() -> int:
    """Roda as checagens, imprime o resultado de cada uma e devolve o exit code."""
    problems = check_contract_gate() + check_evidence_hashes()
    if problems:
        print("PORTÃO REPROVADO:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(
        "PORTÃO APROVADO: Produção-base passa, lote corrompido é barrado com as falhas esperadas "
        f"e os {len(EVIDENCE_BATCHES)} lotes batem com a evidência versionada."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
