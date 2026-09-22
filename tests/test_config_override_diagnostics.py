from aws_cdk import App, Stack
from aws_cdk import assertions
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam

from conftest import make_method
from lambda_api_decorators_cdk import LambdaApiConfig, ResourceBuilder
from lambda_api_decorators_cdk import ast_helper
from lambda_api_decorators_cdk import resource_builder as module
from lambda_api_decorators_cdk.ast_helper import DecoratorInvocation, Resource


class RestApi:
    def __init__(self, path="/"):
        self.path = path

    def add_method(self, *args, **kwargs):
        pass

    def add_resource(self, name):
        return RestApi(f"{self.path.rstrip('/')}/{name}")


def route_graph(routes):
    root = Resource("/")
    for path, method in routes:
        resource = root if path == "/" else Resource(path)
        resource.add_method(method)
        if resource is not root:
            root.connect(resource)
    return root


def build(builder, stack, monkeypatch, routes):
    graph = route_graph(routes)
    monkeypatch.setattr(module.ast_helper, "get_lambda_graph", lambda path: graph)
    monkeypatch.setattr(builder, "_prepare_layers", lambda *args: None)
    monkeypatch.setattr(builder, "build_lambda_function", lambda *args: object())
    monkeypatch.setattr(module.apigateway, "LambdaIntegration", lambda value: value)
    builder.build(stack, RestApi(), ".")


def infos(stack):
    return assertions.Annotations.from_stack(stack).find_info(
        f"/{stack.node.path}", assertions.Match.any_value()
    )


def warnings(stack):
    return assertions.Annotations.from_stack(stack).find_warning(
        f"/{stack.node.path}", assertions.Match.any_value()
    )


def role(stack, construct_id):
    return iam.Role(
        stack,
        construct_id,
        assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
    )


def authorizer():
    class DiagnosticAuthorizer:
        __jsii_ifaces__ = [apigateway.IAuthorizer]
        authorization_type = apigateway.AuthorizationType.CUSTOM

    return DiagnosticAuthorizer()


def test_authorizer_overrides_consolidate_routes_in_stable_order(monkeypatch):
    stack = Stack(App(), "Stack")
    builder = ResourceBuilder(
        authorizers={"users": authorizer(), "admins": authorizer()},
        default_authorizer="users",
    )
    routes = [
        ("/zebra", make_method("POST", handler="zebra", decorators={"authorizer": "admins"})),
        ("/health", make_method("GET", handler="health", decorators={"public": True})),
        ("/orders", make_method("GET", handler="orders")),
    ]

    build(builder, stack, monkeypatch, routes)

    entries = infos(stack)
    assert len(entries) == 1
    text = entries[0].entry.data
    assert text.startswith("Authorization overrides")
    assert "Default authorizer: users" in text
    assert "METHOD" in text and "PATH" in text and "EFFECTIVE" in text
    assert text.index("/health") < text.index("/zebra")
    assert "GET    /health    PUBLIC" in text
    assert "POST    /zebra    admins" in text
    assert "/orders" not in text


def test_authorizer_public_default_keeps_warning_and_one_info(monkeypatch):
    stack = Stack(App(), "Stack")
    builder = ResourceBuilder(authorizers={"users": authorizer()})
    routes = [
        ("/private", make_method("POST", handler="private", decorators={"authorizer": "users"})),
        ("/public", make_method("GET", handler="public")),
    ]

    build(builder, stack, monkeypatch, routes)

    assert len([entry for entry in warnings(stack) if "LAD_AUTH_PUBLIC_DEFAULT" in entry.entry.data]) == 1
    entries = infos(stack)
    assert len(entries) == 1
    assert "Authorization overrides" in entries[0].entry.data
    assert "Default authorizer: PUBLIC" in entries[0].entry.data
    assert "POST    /private    users" in entries[0].entry.data
    assert "/public" not in entries[0].entry.data


def test_role_overrides_show_logical_key_and_identity(monkeypatch):
    stack = Stack(App(), "Stack")
    default = role(stack, "DefaultRole")
    selected = role(stack, "SelectedRole")
    builder = ResourceBuilder(
        default_role=default,
        custom_roles={"api-role": selected, "same-object": default},
    )
    routes = [
        ("/orders", make_method("POST", handler="orders", decorators={"role": "api-role"})),
        ("/same", make_method("GET", handler="same", decorators={"role": "same-object"})),
        ("/default", make_method("GET", handler="default")),
    ]

    build(builder, stack, monkeypatch, routes)

    entries = infos(stack)
    assert len(entries) == 1
    text = entries[0].entry.data
    assert text.startswith("Execution role overrides")
    assert "Default role: configured default" in text
    assert "POST    /orders    api-role" in text
    assert "/same" not in text
    assert "/default" not in text
    assert "arn:" not in text and "${Token[" not in text


def test_role_diagnostics_are_silent_without_default_or_overrides(monkeypatch):
    stack = Stack(App(), "Stack")
    builder = ResourceBuilder(custom_roles={"api-role": role(stack, "Role")})
    build(builder, stack, monkeypatch, [
        ("/orders", make_method("POST", handler="orders", decorators={"role": "api-role"})),
    ])
    assert not any("Execution role overrides" in entry.entry.data for entry in infos(stack))


def test_vpc_overrides_include_subnets_and_compare_identity(monkeypatch):
    stack = Stack(App(), "Stack")
    default_vpc = ec2.Vpc(stack, "DefaultVpc", max_azs=1)
    selected_vpc = ec2.Vpc(stack, "SelectedVpc", max_azs=1)
    default_subnets = ec2.SubnetSelection(one_per_az=True)
    selected_subnets = ec2.SubnetSelection(
        subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
    )
    builder = ResourceBuilder(
        default_vpc=(default_vpc, default_subnets),
        custom_vpcs={
            "selected-vpc": (selected_vpc, selected_subnets),
            "same-vpc": (default_vpc, default_subnets),
            "subnets-only": (default_vpc, selected_subnets),
        },
    )
    routes = [
        ("/reports", make_method("GET", handler="reports", decorators={"vpc": "selected-vpc"})),
        ("/same", make_method("GET", handler="same", decorators={"vpc": "same-vpc"})),
        ("/private", make_method("GET", handler="private", decorators={"vpc": "subnets-only"})),
    ]

    build(builder, stack, monkeypatch, routes)

    entries = infos(stack)
    assert len(entries) == 1
    text = entries[0].entry.data
    assert text.startswith("VPC overrides")
    assert "METHOD" in text and "PATH" in text and "EFFECTIVE" in text and "SUBNETS" in text
    assert "GET    /private    subnets-only" in text
    assert "GET    /reports    selected-vpc" in text
    assert "/same" not in text
    assert "PRIVATE_WITH_EGRESS" in text
    assert "arn:" not in text and "${Token[" not in text


def test_vpc_diagnostics_are_silent_without_default_or_overrides(monkeypatch):
    stack = Stack(App(), "Stack")
    selected_vpc = ec2.Vpc(stack, "SelectedVpc", max_azs=1)
    builder = ResourceBuilder(custom_vpcs={"selected": (selected_vpc, None)})
    build(builder, stack, monkeypatch, [
        ("/reports", make_method("GET", handler="reports", decorators={"vpc": "selected"})),
    ])
    assert not any("VPC overrides" in entry.entry.data for entry in infos(stack))


def test_reused_config_does_not_mix_role_diagnostics_between_snapshots(monkeypatch):
    first_stack = Stack(App(), "First")
    second_stack = Stack(App(), "Second")
    default = role(first_stack, "DefaultRole")
    selected = role(first_stack, "SelectedRole")
    config = LambdaApiConfig(
        default_role=default,
        role_registry={"selected": selected},
    )
    first = config._create_resource_builder()
    second = config._create_resource_builder()

    build(first, first_stack, monkeypatch, [
        ("/first", make_method("POST", handler="first", decorators={"role": "selected"})),
    ])
    build(second, second_stack, monkeypatch, [
        ("/second", make_method("GET", handler="second")),
    ])

    assert "/first" in infos(first_stack)[0].entry.data
    assert not any("Execution role overrides" in entry.entry.data for entry in infos(second_stack))


def test_only_requested_categories_have_override_tables(monkeypatch):
    stack = Stack(App(), "Stack")
    default = role(stack, "DefaultRole")
    selected = role(stack, "SelectedRole")
    builder = ResourceBuilder(
        default_role=default,
        custom_roles={"selected": selected},
        default_runtime=object(),
        common_environments={"KEY": "value"},
    )
    build(builder, stack, monkeypatch, [
        ("/orders", make_method("POST", handler="orders", decorators={"role": "selected"})),
    ])
    text = "\n".join(entry.entry.data for entry in infos(stack))
    assert "Execution role overrides" in text
    for category in ("Runtime overrides", "Timeout overrides", "Memory overrides",
                     "Environment overrides", "Layer overrides", "Security group overrides"):
        assert category not in text


def test_shared_role_permission_warning_is_emitted_once_per_lambda_api(monkeypatch):
    stack = Stack(App(), "Stack")
    default = role(stack, "DefaultRole")
    shared = role(stack, "SharedRole")
    builder = ResourceBuilder(
        default_role=default,
        custom_roles={"shared-role": shared},
        dynamodb_tables={"orders": object()},
        s3_buckets={"documents": object()},
    )
    routes = [
        ("/orders", make_method("GET", handler="orders", decorators={
            "role": "shared-role",
            "grant_dynamodb": "orders",
        })),
        ("/documents", make_method("GET", handler="documents", decorators={
            "role": "shared-role",
            "grant_s3": "documents",
        })),
    ]

    build(builder, stack, monkeypatch, routes)

    shared_warnings = [
        entry for entry in warnings(stack)
        if "LAD_ROLE_SHARED_PERMISSIONS" in entry.entry.data
    ]
    assert len(shared_warnings) == 1
