import inspect

import pytest
from aws_cdk import Duration, aws_ec2 as ec2, aws_lambda as lambda_
from constructs import Construct

from lambda_api_decorators_cdk import LambdaApiConfig, ResourceBuilder


def test_constructor_contract_and_empty_snapshot():
    parameters = inspect.signature(LambdaApiConfig).parameters
    assert list(parameters) == [
        "runtime", "timeout", "memory_size", "vpc", "vpc_subnets", "role",
        "layers", "security_groups", "environment", "dynamodb_tables",
        "s3_buckets", "authorizers", "default_authorizer",
    ]
    assert all(value.kind is inspect.Parameter.KEYWORD_ONLY
               for value in parameters.values())
    builder = LambdaApiConfig()._create_resource_builder()
    assert isinstance(builder, ResourceBuilder)
    assert not isinstance(LambdaApiConfig(), (Construct, ResourceBuilder))
    assert (builder.default_runtime, builder.default_timeout,
            builder.default_memory_size, builder.default_vpc,
            builder.default_role) == (None, None, None, None, None)
    assert (builder.common_layers, builder.common_security_groups,
            builder.common_environments) == ([], [], {})
    assert builder.custom_roles == {}
    assert builder.custom_layers == {}
    assert builder.custom_environments == {}
    assert builder.custom_security_groups == {}
    assert builder.custom_vpcs == {}
    assert builder.authorizers == {}
    assert builder.default_authorizer is None


def test_constructor_maps_defaults_common_values_and_preserves_object_identity():
    runtime, timeout = lambda_.Runtime.PYTHON_3_12, Duration.seconds(15)
    vpc, subnets, role, layer, group = (
        object(), ec2.SubnetSelection(one_per_az=True), object(), object(), object())
    builder = LambdaApiConfig(
        runtime=runtime, timeout=timeout, memory_size=512, vpc=vpc,
        vpc_subnets=subnets, role=role, layers=[layer],
        security_groups=[group], environment={"STAGE": "dev"},
    )._create_resource_builder()
    assert builder.default_runtime is runtime
    assert builder.default_timeout is timeout
    assert builder.default_memory_size == 512
    assert builder.default_vpc == (vpc, subnets)
    assert builder.default_role is role
    assert builder.common_layers[0] is layer
    assert builder.common_security_groups[0] is group
    assert builder.common_environments == {"STAGE": "dev"}


def test_constructor_owns_input_containers():
    layers, groups, environment = ["layer"], ["group"], {"A": "one"}
    config = LambdaApiConfig(
        layers=layers, security_groups=groups, environment=environment)
    layers.append("later")
    groups.clear()
    environment["A"] = "changed"
    builder = config._create_resource_builder()
    assert builder.common_layers == ["layer"]
    assert builder.common_security_groups == ["group"]
    assert builder.common_environments == {"A": "one"}


@pytest.mark.parametrize("method,args,attribute,expected", [
    ("set_default_runtime", (lambda_.Runtime.PYTHON_3_12,), "default_runtime", lambda_.Runtime.PYTHON_3_12),
    ("set_default_timeout", (Duration.seconds(7),), "default_timeout", Duration.seconds(7)),
    ("set_default_memory_size", (768,), "default_memory_size", 768),
    ("set_default_role", ("role",), "default_role", "role"),
    ("add_common_layer", ("layer",), "common_layers", ["layer"]),
    ("add_common_security_group", ("group",), "common_security_groups", ["group"]),
])
def test_default_and_common_mutators_return_none(method, args, attribute, expected):
    config = LambdaApiConfig()
    assert getattr(config, method)(*args) is None
    actual = getattr(config._create_resource_builder(), attribute)
    if method == "set_default_timeout":
        assert actual.to_seconds() == expected.to_seconds()
    elif method == "set_default_runtime":
        assert actual is args[0]
    else:
        assert actual == expected


@pytest.mark.parametrize("subnets", [None, ec2.SubnetSelection(one_per_az=True)])
def test_default_vpc_accepts_optional_subnet_selection(subnets):
    config, vpc = LambdaApiConfig(), object()
    assert config.set_default_vpc(vpc, subnets) is None
    actual = config._create_resource_builder().default_vpc
    assert actual[0] is vpc and actual[1] is subnets


@pytest.mark.parametrize("method,value,attribute", [
    ("add_custom_runtime", lambda_.Runtime.PYTHON_3_12, "custom_runtimes"),
    ("add_custom_role", object(), "custom_roles"),
    ("add_custom_layer", object(), "custom_layers"),
    ("add_custom_environment", "value", "custom_environments"),
    ("add_custom_security_group", object(), "custom_security_groups"),
])
def test_custom_mutators_return_none_and_replace_keys(method, value, attribute):
    config, replacement = LambdaApiConfig(), object()
    assert getattr(config, method)("named", value) is None
    first = config._create_resource_builder()
    assert getattr(first, attribute)["named"] is value
    getattr(config, method)("named", replacement)
    second = config._create_resource_builder()
    assert getattr(second, attribute)["named"] is replacement


@pytest.mark.parametrize("subnets", [None, ec2.SubnetSelection(one_per_az=True)])
def test_custom_vpc_accepts_optional_subnet_selection(subnets):
    config, vpc = LambdaApiConfig(), object()
    assert config.add_custom_vpc("private", vpc, subnets) is None
    actual = config._create_resource_builder().custom_vpcs["private"]
    assert actual[0] is vpc and actual[1] is subnets


def test_repeated_custom_vpc_key_replaces_vpc_and_subnet_selection():
    config = LambdaApiConfig()
    first_vpc, second_vpc = object(), object()
    first_subnets = ec2.SubnetSelection(subnet_group_name="first")
    second_subnets = ec2.SubnetSelection(subnet_group_name="second")
    config.add_custom_vpc("private", first_vpc, first_subnets)
    first = config._create_resource_builder().custom_vpcs["private"]
    assert first[0] is first_vpc and first[1] is first_subnets
    config.add_custom_vpc("private", second_vpc, second_subnets)
    second = config._create_resource_builder().custom_vpcs["private"]
    assert second[0] is second_vpc and second[1] is second_subnets


def test_common_duplicates_and_constructor_environment_match_builder_semantics():
    config = LambdaApiConfig(environment={"A": "two"})
    config.add_common_layer("same")
    config.add_common_layer("same")
    config.add_common_security_group("same")
    config.add_common_security_group("same")
    builder = config._create_resource_builder()
    assert builder.common_layers == ["same"]
    assert builder.common_security_groups == ["same"]
    assert builder.common_environments == {"A": "two"}


def test_snapshots_have_independent_containers_but_shared_cdk_objects():
    layer = object()
    config = LambdaApiConfig(layers=[layer], environment={"A": "one"})
    first, second = config._create_resource_builder(), config._create_resource_builder()
    assert first is not second
    for name in (
        "common_layers", "common_security_groups", "common_environments",
        "custom_runtimes", "custom_roles", "custom_layers",
        "custom_environments", "custom_security_groups", "custom_vpcs",
    ):
        assert getattr(first, name) is not getattr(second, name)
    assert first.common_layers[0] is layer and second.common_layers[0] is layer
    first.common_layers.append("first-only")
    assert second.common_layers == [layer]


def test_builder_mutation_before_later_snapshot_does_not_mutate_config():
    config = LambdaApiConfig(
        layers=["common-layer"], security_groups=["common-group"],
        environment={"A": "one"})
    config.add_custom_layer("configured", "custom-layer")
    config.add_custom_environment("CONFIGURED", "value")
    first = config._create_resource_builder()
    first.common_layers.append("builder-only-layer")
    first.common_security_groups.append("builder-only-group")
    first.common_environments["A"] = "builder-only"
    first.custom_layers["builder-only"] = "layer"
    first.custom_environments["builder-only"] = "environment"
    second = config._create_resource_builder()
    assert second.common_layers == ["common-layer"]
    assert second.common_security_groups == ["common-group"]
    assert second.common_environments == {"A": "one"}
    assert second.custom_layers == {"configured": "custom-layer"}
    assert second.custom_environments == {"CONFIGURED": "value"}


def test_resource_builder_builtin_runtimes_are_fresh_and_do_not_mutate_config():
    expected = {"python3.10", "python3.11", "python3.12", "python3.13", "python3.14"}
    config = LambdaApiConfig()
    first = config._create_resource_builder()
    assert set(first.custom_runtimes) == expected
    first.custom_runtimes["builder-only"] = object()
    second = config._create_resource_builder()
    assert set(second.custom_runtimes) == expected
    assert "builder-only" not in second.custom_runtimes


def test_config_mutation_only_affects_later_snapshot_and_builtin_runtimes_do_not_leak():
    config, layer = LambdaApiConfig(), object()
    first = config._create_resource_builder()
    first.custom_runtimes["builder-only"] = object()
    config.add_custom_layer("later", layer)
    second = config._create_resource_builder()
    assert "later" not in first.custom_layers
    assert second.custom_layers["later"] is layer
    assert "builder-only" not in second.custom_runtimes


def test_resource_builder_retains_precedence_responsibility():
    selected_runtime = lambda_.Runtime.PYTHON_3_12
    config = LambdaApiConfig(
        runtime=lambda_.Runtime.PYTHON_3_11, layers=["common"],
        environment={"SHARED": "common"})
    config.add_custom_runtime("selected", selected_runtime)
    config.add_custom_layer("selected", "custom")
    config.add_custom_environment("SHARED", "custom")
    config.add_common_security_group("common-sg")
    config.add_custom_security_group("selected", "custom-sg")
    options = config._create_resource_builder().get_options({
        "runtime": "selected", "layer": "selected", "environment": "SHARED",
        "security_group": "selected"})
    assert options["runtime"] is selected_runtime
    assert options["layer"] == ["common", "custom"]
    assert options["environment"] == {"SHARED": "custom"}
    assert options["security_group"] == ["common-sg", "custom-sg"]
