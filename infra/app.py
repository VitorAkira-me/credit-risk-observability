"""AWS-002: ponto de entrada do CDK.

O que faz: instancia a stack do pipeline na região do projeto.
Por que existe: é o arquivo que o comando `cdk` executa, conforme infra/cdk.json.
Onde entra no fluxo: `make cdk-synth`, `make cdk-diff` e `make cdk-deploy`.
"""

import os

import aws_cdk as cdk
from stack import CreditRiskPipelineStack

# A região é fixa: todos os recursos do projeto ficam em São Paulo (ADR-007).
REGION = "sa-east-1"

app = cdk.App()
CreditRiskPipelineStack(
    app,
    "CreditRiskPipeline",
    # A conta vem do perfil usado no comando: o número da conta não fica no repositório.
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=REGION),
)
app.synth()
