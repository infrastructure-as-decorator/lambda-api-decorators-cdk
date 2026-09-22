import pytest
from aws_cdk import Duration, aws_lambda as lambda_

from lambda_api_decorators_cdk import ResourceBuilder


COLLECTION_NAMES = (
    "common_layers", "common_security_groups", "common_environments",
    "custom_runtimes", "custom_roles", "custom_layers", "custom_environments",
    "custom_security_groups", "custom_vpcs",
)


def test_constructor_preserves_scalar_defaults_and_supplied_state():
    values = {name: {} if "environment" in name or name.startswith("custom_") else []
              for name in COLLECTION_NAMES}
    runtime, timeout, role, vpc = object(), Duration.seconds(12), object(), object()
    builder = ResourceBuilder(default_runtime=runtime, default_timeout=timeout,
                              default_memory_size=384, default_role=role,
                              default_vpc=vpc, **values)
    assert (builder.default_runtime, builder.default_timeout,
            builder.default_memory_size, builder.default_role, builder.default_vpc) == (
                runtime, timeout, 384, role, vpc)
    for name, value in values.items():
        assert getattr(builder, name) is value  # explicit-container ownership today


def test_omitted_collection_arguments_are_not_shared_between_instances():
    """EXPECTED BEHAVIOR / BUG REGRESSION: constructor mutable defaults."""
    first, second = ResourceBuilder(), ResourceBuilder()
    for name in COLLECTION_NAMES:
        assert getattr(first, name) is not getattr(second, name)


def test_mutation_of_omitted_collections_does_not_leak_between_builders():
    """EXPECTED BEHAVIOR / BUG REGRESSION: mutations currently leak."""
    first, second = ResourceBuilder(), ResourceBuilder()
    first.add_common_layer("only-first")
    first.add_common_security_group("only-first")
    first.common_environments["only-first"] = "value"
    first.add_custom_role("only-first", object())
    assert "only-first" not in second.common_layers
    assert "only-first" not in second.common_security_groups
    assert "only-first" not in second.common_environments
    assert "only-first" not in second.custom_roles


def test_builtin_runtime_registry_has_existing_aliases(builder):
    expected = {"python3.10", "python3.11", "python3.12", "python3.13", "python3.14"}
    assert set(builder.custom_runtimes) == expected
    assert {runtime.name for runtime in builder.custom_runtimes.values()} == expected
    assert builder.default_runtime is None


@pytest.mark.parametrize("kind", ["runtime", "role", "layer", "environment", "vpc"])
def test_custom_registry_add_get_and_unknown_key(builder, kind):
    value = "" if kind == "environment" else object()
    if kind == "vpc":
        builder.add_custom_vpc("shared", value, ["subnet"])
        assert builder.get_custom_vpc("shared") == (value, ["subnet"])
    else:
        getattr(builder, f"add_custom_{kind}")("shared", value)
        assert getattr(builder, f"get_custom_{kind}")("shared") is value
    with pytest.raises(KeyError):
        getattr(builder, f"get_custom_{kind}")("missing")


def test_custom_environment_accepts_and_returns_zero(builder):
    builder.add_custom_environment("zero", 0)
    assert builder.custom_environments["zero"] == 0
    assert builder.get_custom_environment("zero") == 0


def test_same_key_is_isolated_across_custom_registries(builder):
    runtime, role, layer, env, vpc = object(), object(), object(), "value", object()
    builder.add_custom_runtime("key", runtime)
    builder.add_custom_role("key", role)
    builder.add_custom_layer("key", layer)
    builder.add_custom_environment("key", env)
    builder.add_custom_vpc("key", vpc, ["subnet"])
    assert [builder.get_custom_runtime("key"), builder.get_custom_role("key"),
            builder.get_custom_layer("key"), builder.get_custom_environment("key")] == [
                runtime, role, layer, env]
    assert builder.get_custom_vpc("key") == (vpc, ["subnet"])


def test_custom_security_group_uses_its_own_registry(builder):
    """EXPECTED BEHAVIOR / BUG REGRESSION: add currently writes custom_layers."""
    group = object()
    builder.add_custom_security_group("private", group)
    assert builder.get_custom_security_group("private") is group
    assert "private" not in builder.custom_layers


def test_custom_security_group_getter_success_and_unknown_key(builder):
    group = object()
    builder.custom_security_groups["private"] = group
    assert builder.get_custom_security_group("private") is group
    with pytest.raises(KeyError):
        builder.get_custom_security_group("missing")


def test_public_resource_builder_import():
    from lambda_api_decorators_cdk import ResourceBuilder as PublicBuilder
    assert PublicBuilder is ResourceBuilder
