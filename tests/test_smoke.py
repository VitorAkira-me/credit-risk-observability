from pathlib import Path

# Raiz do projeto: dois níveis acima deste arquivo,
# considerando que ele está em tests/test_smoke.py.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_project_structure():
    """Verifica a existência dos diretórios essenciais."""
    required_paths = [
        PROJECT_ROOT / "src",
        PROJECT_ROOT / "tests",
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "pyproject.toml",
    ]

    missing_paths = [
        str(path.relative_to(PROJECT_ROOT)) for path in required_paths if not path.exists()
    ]

    assert not missing_paths, f"Arquivos ou diretórios ausentes: {missing_paths}"


def test_source_package_exists():
    """Confirma que o pacote principal foi criado."""
    package_dir = PROJECT_ROOT / "src" / "credit_risk_observability"

    assert package_dir.is_dir(), f"Pacote não encontrado: {package_dir}"
    assert (package_dir / "__init__.py").is_file(), "O pacote não possui __init__.py"


def test_core_dependencies_are_available():
    """Verifica dependências fundamentais do projeto."""
    import numpy
    import pandas
    import sklearn

    assert numpy.__version__
    assert pandas.__version__
    assert sklearn.__version__
