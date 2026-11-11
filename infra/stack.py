"""AWS-002 e AWS-003: toda a infraestrutura do pipeline na AWS, descrita em código (ADR-007).

O que faz: declara o bucket, a função Lambda com a imagem do pipeline, o gatilho do S3, o
agendamento semanal, os logs, o painel, os alarmes e o aviso por e-mail.
Por que existe: infra em código se revisa num PR, se recria igual e se apaga com um comando.
Onde entra no fluxo: infra/app.py instancia esta stack; `make cdk-diff` e `make cdk-deploy` a aplicam.

Termos usados aqui:
- CDK: biblioteca que gera modelos do CloudFormation (o serviço que cria recursos na AWS).
- Stack: o conjunto de recursos criado e apagado junto.
- EMF: linha JSON no log que o CloudWatch transforma em métrica (ver cloud/handler.py).
"""

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    CfnParameter,
    Duration,
    IgnoreMode,
    RemovalPolicy,
    Stack,
    Tags,
    TimeZone,
)
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_notifications as s3_notifications
from aws_cdk import aws_scheduler as scheduler
from aws_cdk import aws_scheduler_targets as scheduler_targets
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[1]

# Precisam ser iguais às constantes de cloud/handler.py; tests/test_cloud_handler.py confere.
METRICS_NAMESPACE = "CreditRisk/Pipeline"
PIPELINE_NAME = "credit-risk-observability"
AUC_FLOOR = 0.6871  # piso calibrado em reports/monitoring/alert_thresholds.json

# Falhas por etapa, para a consulta salva no Logs Insights.
FAILURES_QUERY = """fields @timestamp, etapa, evento, linhas_entrada, linhas_rejeitadas
| filter status = "falha"
| stats count(*) as falhas by etapa, evento"""


def pipeline_metric(name: str, statistic: str = "Sum") -> cloudwatch.Metric:
    """Aponta para uma métrica publicada pelo pipeline.

    Recebe: o nome da métrica e a estatística.
    Faz: usa o namespace e a dimensão gravados na linha EMF; sem isso, o alarme olharia uma métrica
        que não existe e ficaria parado para sempre.
    Devolve: a métrica, com janela de 1 minuto.
    """
    return cloudwatch.Metric(
        namespace=METRICS_NAMESPACE,
        metric_name=name,
        dimensions_map={"Pipeline": PIPELINE_NAME},
        statistic=statistic,
        period=Duration.minutes(1),
    )


class CreditRiskPipelineStack(Stack):
    """O pipeline na AWS: um lote chega ao S3, a função roda e o alarme avisa."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """Declara os recursos.

        Recebe: o escopo do CDK, o identificador da stack e as opções (região e conta).
        Faz: cria os recursos na ordem em que dependem uns dos outros.
        Devolve: nada.
        """
        super().__init__(scope, construct_id, **kwargs)

        # Parâmetro do deploy: o repositório é público, e o e-mail não pode estar no código.
        alert_email = CfnParameter(
            self,
            "AlertEmail",
            type="String",
            no_echo=True,
            description="E-mail que recebe os alarmes do pipeline",
        )

        bucket = self._build_bucket()
        function = self._build_function(bucket)
        self._build_triggers(bucket, function)
        topic = sns.Topic(
            self,
            "Alertas",
            display_name="Alertas do pipeline de crédito",
            # Sem KMS de propósito: o CloudWatch não publica em tópico com a chave alias/aws/sns,
            # e a mensagem só tem o nome do alarme, sem dado de cliente (ADR-007).
            enforce_ssl=True,
        )
        topic.add_subscription(subscriptions.EmailSubscription(alert_email.value_as_string))
        alarms = self._build_alarms(function, topic)
        self._build_dashboard(function, alarms)

        Tags.of(self).add("projeto", PIPELINE_NAME)
        Tags.of(self).add("dono", "akira")
        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        CfnOutput(self, "FunctionName", value=function.function_name)

    def _build_bucket(self) -> s3.Bucket:
        """Cria o bucket privado.

        Recebe: nada.
        Faz: bloqueia acesso público, criptografa, exige TLS e expira os arquivos no prazo do plano
            de retenção (GOV-002): lotes em 30 dias, relatórios em 90.
        Devolve: o bucket. auto_delete_objects permite o teardown em um comando.
        """
        return s3.Bucket(
            self,
            "Dados",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(prefix="incoming/", expiration=Duration.days(30)),
                s3.LifecycleRule(prefix="reports/", expiration=Duration.days(90)),
            ],
        )

    def _build_function(self, bucket: s3.Bucket) -> lambda_.DockerImageFunction:
        """Cria a função com a imagem do pipeline.

        Recebe: o bucket.
        Faz: define memória e tempo, zera as novas tentativas (um lote com erro geraria três
            execuções e três alarmes) e dá permissão mínima, prefixo por prefixo.
        Devolve: a função.
        """
        log_group = logs.LogGroup(
            self,
            "Logs",
            retention=logs.RetentionDays.SIX_MONTHS,  # 180 dias, como no plano de retenção
            removal_policy=RemovalPolicy.DESTROY,
        )
        function = lambda_.DockerImageFunction(
            self,
            "Pipeline",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(REPO_ROOT),
                platform=ecr_assets.Platform.LINUX_AMD64,
                ignore_mode=IgnoreMode.DOCKER,
            ),
            architecture=lambda_.Architecture.X86_64,
            memory_size=3008,
            timeout=Duration.minutes(5),
            retry_attempts=0,
            log_group=log_group,
            environment={"BUCKET_NAME": bucket.bucket_name},
        )
        bucket.grant_read(function, "seed/*")
        bucket.grant_read(function, "incoming/*")
        bucket.grant_put(function, "reports/*")

        logs.CfnQueryDefinition(
            self,
            "FalhasPorEtapa",
            name="credit-risk/falhas-por-etapa",
            query_string=FAILURES_QUERY,
            log_group_names=[log_group.log_group_name],
        )
        return function

    def _build_triggers(self, bucket: s3.Bucket, function: lambda_.DockerImageFunction) -> None:
        """Liga os dois gatilhos da função.

        Recebe: o bucket e a função.
        Faz: dispara em arquivos novos em incoming/ e toda segunda às 9h com o lote de controle.
            O filtro por prefixo impede que os relatórios gravados disparem a própria função.
        Devolve: nada.
        """
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3_notifications.LambdaDestination(function),
            s3.NotificationKeyFilter(prefix="incoming/", suffix=".parquet"),
        )
        scheduler.Schedule(
            self,
            "Semanal",
            description="Roda o lote de controle toda segunda-feira",
            schedule=scheduler.ScheduleExpression.cron(
                minute="0",
                hour="9",
                week_day="MON",
                time_zone=TimeZone.AMERICA_SAO_PAULO,
            ),
            target=scheduler_targets.LambdaInvoke(
                function,
                input=scheduler.ScheduleTargetInput.from_object({"source": "agendamento-semanal"}),
                retry_attempts=0,
            ),
        )

    def _build_alarms(
        self, function: lambda_.DockerImageFunction, topic: sns.Topic
    ) -> list[cloudwatch.Alarm]:
        """Cria os alarmes e liga ao e-mail.

        Recebe: a função e o tópico.
        Faz: separa lote ruim (contrato), modelo piorando (drift) e pipeline quebrado (erro da
            função): são problemas diferentes, com ações diferentes. Sem dados, fica em OK, porque
            a métrica só existe quando um lote roda.
        Devolve: a lista de alarmes.
        """
        definitions = [
            ("ContratoReprovado", pipeline_metric("LotesReprovados"), "Lote barrado no contrato"),
            ("AlertaDrift", pipeline_metric("AlertasDrift"), "Réguas de drift dispararam"),
            ("ErroPipeline", function.metric_errors(period=Duration.minutes(1)), "Erro na função"),
        ]
        alarms = []
        for name, metric, description in definitions:
            alarm = cloudwatch.Alarm(
                self,
                name,
                alarm_name=f"credit-risk-{name}",
                alarm_description=description,
                metric=metric,
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            alarm.add_alarm_action(cloudwatch_actions.SnsAction(topic))
            alarms.append(alarm)
        return alarms

    def _build_dashboard(
        self, function: lambda_.DockerImageFunction, alarms: list[cloudwatch.Alarm]
    ) -> None:
        """Cria o painel com as métricas de saúde do README.

        Recebe: a função e os alarmes.
        Faz: responde às três perguntas do painel: rodou? Rodou bem? O modelo ainda é confiável?
        Devolve: nada.
        """
        dashboard = cloudwatch.Dashboard(
            self, "Painel", dashboard_name="credit-risk-observability"
        )
        dashboard.add_widgets(
            cloudwatch.AlarmStatusWidget(title="Alarmes", alarms=alarms, width=24, height=3),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Lotes processados e reprovados",
                left=[pipeline_metric("LotesProcessados"), pipeline_metric("LotesReprovados")],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Linhas de entrada e rejeitadas",
                left=[pipeline_metric("LinhasEntrada"), pipeline_metric("LinhasRejeitadas")],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Duração da função",
                left=[function.metric_duration(period=Duration.minutes(1))],
                width=8,
            ),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="AUC do lote",
                left=[pipeline_metric("AUC", "Average")],
                left_annotations=[
                    cloudwatch.HorizontalAnnotation(value=AUC_FLOOR, label="piso calibrado")
                ],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Taxa de default",
                left=[pipeline_metric("TaxaDefault", "Average")],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Features com drift e alertas",
                left=[pipeline_metric("FeaturesComDrift"), pipeline_metric("AlertasDrift")],
                width=8,
            ),
        )
