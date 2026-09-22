"""Contract tests for the LambdaApiConfig registry model.

This file is intentionally a RED-stage contract.  It exercises the CDK
integration's public configuration vocabulary and keeps CDK objects intact so
JSII identity is part of the contract.
"""

import ast

import pytest
from aws_cdk import App, Stack, assertions
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3

from lambda_api_decorators import GET, environment, layer, role, runtime, security_group, vpc
from lambda_api_decorators_cdk import LambdaApi, LambdaApiConfig, ResourceBuilder
from lambda_api_decorators_cdk import ast_helper
from lambda_api_decorators_cdk import resource_builder as resource_builder_module


@pytest.fixture
def stack():
    return Stack(App(), "ConfigRegistryContract")


@pytest.fixture
def resources(stack):
    vpc_resource = ec2.Vpc(stack, "Vpc", max_azs=1)
    role_resource = iam.Role(
        stack,
        "Role",
        assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
    )
    authorizer_handler = lambda_.Function(
        stack,
        "AuthorizerHandler",
        runtime=lambda_.Runtime.PYTHON_3_12,
        handler="index.handler",
        code=lambda_.Code.from_inline("def handler(event, context): return {}"),
    )
    return {
        "role": role_resource,
        "layer": lambda_.LayerVersion.from_layer_version_arn(
            stack,
            "Layer",
            "arn:aws:lambda:us-east-1:123456789012:layer:shared:1",
        ),
        "security_group": ec2.SecurityGroup(stack, "SecurityGroup", vpc=vpc_resource),
        "vpc": vpc_resource,
        "table": dynamodb.Table.from_table_arn(
            stack,
            "Table",
            "arn:aws:dynamodb:us-east-1:123456789012:table/orders",
        ),
        "bucket": s3.Bucket.from_bucket_name(stack, "Bucket", "documents"),
        "authorizer": apigateway.RequestAuthorizer(
            stack,
            "Authorizer",
            handler=authorizer_handler,
            identity_sources=[apigateway.IdentitySource.header("Authorization")],
        ),
    }


def builder_snapshot(config):
    return config._create_resource_builder()


def options(config, **decorators):
    return builder_snapshot(config).get_options(decorators)


def test_each_lambda_api_requires_lambda_api_config(stack, monkeypatch):
    calls = []

    class NoopBuilder:
        def build(self, *args, **kwargs):
            calls.append((args, kwargs))

        def build_http(self, *args, **kwargs):
            calls.append((args, kwargs))

    config = LambdaApiConfig()
    monkeypatch.setattr(config, "_create_resource_builder", lambda: NoopBuilder())

    with pytest.raises(TypeError, match="config"):
        LambdaApi(stack, "Invalid", lambda_path="lambdas", config=object())

    LambdaApi(stack, "Valid", lambda_path="lambdas", config=config)
    assert calls


def test_reusing_config_creates_isolated_mutable_snapshots(resources):
    config = LambdaApiConfig(
        common_environment={"SHARED": "yes"},
        environment_registry={"database": {"DB": "one"}},
        layer_registry={"shared": resources["layer"]},
    )

    first = builder_snapshot(config)
    second = builder_snapshot(config)

    assert first is not second
    assert first.common_environments is not second.common_environments
    assert first.custom_environments is not second.custom_environments
    assert first.custom_layers is not second.custom_layers
    assert first.custom_layers["shared"] is resources["layer"]
    assert second.custom_layers["shared"] is resources["layer"]

    first.common_environments["ONLY_FIRST"] = "first"
    first.custom_environments["ONLY_FIRST"] = {"VALUE": "first"}
    assert "ONLY_FIRST" not in second.common_environments
    assert "ONLY_FIRST" not in second.custom_environments


@pytest.mark.parametrize(
    "runtime_name",
    ["python3.10", "python3.11", "python3.12", "python3.13", "python3.14"],
)
def test_default_runtime_accepts_only_python_310_through_314(runtime_name):
    config = LambdaApiConfig(default_runtime=runtime_name)
    assert builder_snapshot(config).default_runtime == runtime_name


@pytest.mark.parametrize(
    "runtime_name",
    ["python3.9", "python3.15", "nodejs20.x", "java21", "provided.al2023", ""],
)
def test_default_runtime_rejects_unsupported_and_non_python_runtimes(runtime_name):
    with pytest.raises((TypeError, ValueError), match="runtime"):
        LambdaApiConfig(default_runtime=runtime_name)


def test_runtime_decorator_overrides_default_runtime():
    config = LambdaApiConfig(default_runtime="python3.10")
    selected = options(config, runtime="python3.14")["runtime"]
    assert selected.name == "python3.14"


def test_runtime_registry_and_register_runtime_do_not_exist():
    assert not hasattr(LambdaApiConfig, "runtime_registry")
    assert not hasattr(LambdaApiConfig, "register_runtime")
    assert not hasattr(ResourceBuilder, "runtime_registry")
    assert not hasattr(ResourceBuilder, "register_runtime")


def test_default_role_and_role_registry_select_one_execution_role(resources):
    config = LambdaApiConfig(
        default_role=resources["role"],
        role_registry={"selected": resources["role"]},
    )
    config.register_role("another", resources["role"])

    selected = options(config, role="selected")["role"]
    default = options(config)["role"]
    assert selected is resources["role"]
    assert default is resources["role"]


def test_common_environment_is_constructor_only_and_registered_values_override_it():
    config = LambdaApiConfig(
        common_environment={"KEY": "common", "KEEP": "yes"},
        environment_registry={"selected": {"KEY": "registered"}},
    )
    config.register_environment("selected", {"KEY": "registered"})

    assert not hasattr(config, "set_common_environment")
    assert not hasattr(config, "add_common_environment")
    selected = options(config, environment="selected")["environment"]
    assert selected["KEY"] == "registered"
    assert selected["KEEP"] == "yes"


@pytest.mark.parametrize(
    "registry_name,register_name,resource_name,builder_name",
    [
        ("layer_registry", "register_layer", "layer", "custom_layers"),
        ("security_group_registry", "register_security_group", "security_group", "custom_security_groups"),
        ("vpc_registry", "register_vpc", "vpc", "custom_vpcs"),
        ("dynamodb_table_registry", "register_dynamodb_table", "table", "dynamodb_tables"),
        ("s3_bucket_registry", "register_s3_bucket", "bucket", "s3_buckets"),
        ("authorizer_registry", "register_authorizer", "authorizer", "authorizers"),
    ],
)
def test_resource_registries_are_constructor_backed_and_registerable(
    resources, registry_name, register_name, resource_name, builder_name
):
    resource = resources[resource_name]
    config = LambdaApiConfig(**{registry_name: {"constructor": resource}})
    registered = resources[resource_name]
    getattr(config, register_name)("registered", registered)
    builder = builder_snapshot(config)

    assert getattr(builder, builder_name)["constructor"] is resource
    assert getattr(builder, builder_name)["registered"] is registered


@pytest.mark.parametrize(
    "register_name,resource_name",
    [
        ("register_role", "role"),
        ("register_environment", None),
        ("register_layer", "layer"),
        ("register_security_group", "security_group"),
        ("register_vpc", "vpc"),
        ("register_dynamodb_table", "table"),
        ("register_s3_bucket", "bucket"),
        ("register_authorizer", "authorizer"),
    ],
)
def test_registry_keys_cannot_be_empty_or_duplicated(resources, register_name, resource_name):
    resource = {"KEY": "value"} if resource_name is None else resources[resource_name]
    config = LambdaApiConfig()

    with pytest.raises((TypeError, ValueError), match="key"):
        getattr(config, register_name)("", resource)
    getattr(config, register_name)("unique", resource)
    with pytest.raises(ValueError, match="unique"):
        getattr(config, register_name)("unique", resource)


@pytest.mark.parametrize("decorator", [role, environment, layer, security_group, vpc])
def test_missing_registered_keys_have_descriptive_errors(decorator):
    config = LambdaApiConfig()
    with pytest.raises((KeyError, ValueError), match="missing"):
        options(config, **{decorator.__name__: "missing"})


def test_registered_cdk_objects_keep_jsii_identity(resources):
    config = LambdaApiConfig(
        layer_registry={"layer": resources["layer"]},
        security_group_registry={"group": resources["security_group"]},
        vpc_registry={"vpc": resources["vpc"]},
        dynamodb_table_registry={"table": resources["table"]},
        s3_bucket_registry={"bucket": resources["bucket"]},
        authorizer_registry={"authorizer": resources["authorizer"]},
    )
    builder = builder_snapshot(config)

    assert builder.custom_layers["layer"] is resources["layer"]
    assert builder.custom_security_groups["group"] is resources["security_group"]
    assert builder.custom_vpcs["vpc"][0] is resources["vpc"]
    assert builder.dynamodb_tables["table"] is resources["table"]
    assert builder.s3_buckets["bucket"] is resources["bucket"]
    assert builder.authorizers["authorizer"] is resources["authorizer"]


def test_registering_dynamodb_or_s3_does_not_grant_permissions(resources):
    config = LambdaApiConfig(
        dynamodb_table_registry={"orders": resources["table"]},
        s3_bucket_registry={"documents": resources["bucket"]},
    )
    builder = builder_snapshot(config)
    assert builder.dynamodb_tables["orders"] is resources["table"]
    assert builder.s3_buckets["documents"] is resources["bucket"]
    assert not hasattr(config, "grant_dynamodb")
    assert not hasattr(config, "grant_s3")


def test_built_in_precedence_combines_common_and_selected_values(resources):
    config = LambdaApiConfig(
        default_role=resources["role"],
        common_environment={"SHARED": "common"},
        environment_registry={"selected": {"SHARED": "selected"}},
        layers=[resources["layer"]],
        layer_registry={"selected": resources["layer"]},
        security_groups=[resources["security_group"]],
        security_group_registry={"selected": resources["security_group"]},
        vpc_registry={"selected": resources["vpc"]},
    )
    resolved = options(
        config,
        role="selected",
        environment="selected",
        layer="selected",
        security_group="selected",
        vpc="selected",
    )

    assert resolved["environment"]["SHARED"] == "selected"
    assert resolved["layer"] == [resources["layer"], resources["layer"]]
    assert resolved["security_group"] == [
        resources["security_group"], resources["security_group"]
    ]
    assert resolved["vpc"][0] is resources["vpc"]
    assert resolved["role"] is resources["role"]


def test_multiple_routes_for_one_handler_are_rejected_defensively(tmp_path):
    source = tmp_path / "handler.py"
    source.write_text(
        '@GET("/first")\n@GET("/second")\n@runtime("python3.12")\n'
        'def handler(event, context):\n    pass\n',
        encoding="utf-8",
    )
    graph = ast_helper.get_lambda_graph(str(tmp_path))
    methods = ResourceBuilder._iter_methods(graph)
    route_stack = Stack(App(), "Routes")
    api = apigateway.RestApi(route_stack, "Api")

    with pytest.raises((ValueError, TypeError), match="route|handler|multiple"):
        assert len(methods) == 2
        ResourceBuilder().build_from_graph(
            route_stack, graph, api.root, tmp_path,
        )


def test_lambda_api_passes_the_same_config_to_each_snapshot(stack, monkeypatch):
    snapshots = []
    original = LambdaApiConfig._create_resource_builder

    def create(self):
        snapshot = original(self)
        snapshots.append(snapshot)
        return snapshot

    monkeypatch.setattr(LambdaApiConfig, "_create_resource_builder", create)
    config = LambdaApiConfig()
    monkeypatch.setattr(ResourceBuilder, "build", lambda *args, **kwargs: None)
    LambdaApi(stack, "One", lambda_path="lambdas", config=config)
    LambdaApi(stack, "Two", lambda_path="lambdas", config=config)

    assert len(snapshots) == 2
    assert snapshots[0] is not snapshots[1]
