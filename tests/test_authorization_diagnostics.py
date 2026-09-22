from aws_cdk import App, Stack, aws_apigateway as apigateway
from aws_cdk.assertions import Annotations, Match

from conftest import make_graph, make_method
from lambda_api_decorators_cdk import ResourceBuilder
from lambda_api_decorators_cdk.ast_helper import DecoratorInvocation
from lambda_api_decorators_cdk import resource_builder as module


class RestApi:
    path = "/"

    def add_method(self, *args, **kwargs):
        pass


def build(builder, stack, monkeypatch, methods):
    monkeypatch.setattr(module.ast_helper, "get_lambda_graph", lambda path: make_graph(methods=methods))
    monkeypatch.setattr(builder, "_prepare_layers", lambda *args: None)
    monkeypatch.setattr(builder, "build_lambda_function", lambda *args: object())
    monkeypatch.setattr(module.apigateway, "LambdaIntegration", lambda value: value)
    builder.build(stack, RestApi(), ".")


def messages(stack, level, pattern):
    annotations = Annotations.from_stack(stack)
    finder = annotations.find_warning if level == "warning" else annotations.find_info
    return finder(f"/{stack.node.path}", Match.string_like_regexp(pattern))


def rest_authorizer(stack, construct_id):
    class DiagnosticAuthorizer:
        __jsii_ifaces__ = [apigateway.IAuthorizer]
        authorization_type = apigateway.AuthorizationType.CUSTOM

    return DiagnosticAuthorizer()


def test_public_default_emits_exactly_one_stable_cdk_warning(monkeypatch):
    stack = Stack(App(), "Stack")
    builder = ResourceBuilder(authorizers={}, default_authorizer=None)
    build(builder, stack, monkeypatch, [make_method()])
    found = messages(
        stack,
        "warning",
        r"LAD_AUTH_PUBLIC_DEFAULT[\s\S]*[Rr]outes without explicit auth[\s\S]*public",
    )
    assert len(found) == 1


def test_protected_default_summary_lists_only_sorted_deviations(monkeypatch):
    stack = Stack(App(), "Stack")
    builder = ResourceBuilder(
        authorizers={
            "users": rest_authorizer(stack, "Users"),
            "admins": rest_authorizer(stack, "Admins"),
        },
        default_authorizer="users",
    )
    methods = [
        make_method("POST", decorators=[DecoratorInvocation("authorizer", ("admins",), ())]),
        make_method("GET", decorators=[DecoratorInvocation("public", (), ())]),
        make_method("PUT"),
    ]
    build(builder, stack, monkeypatch, methods)
    found = messages(stack, "info", r"Authorization overrides[\s\S]*Default authorizer: users")
    assert len(found) == 1
    text = found[0].entry.data
    assert "METHOD" in text and "PATH" in text and "EFFECTIVE" in text
    assert "GET    /    PUBLIC" in text
    assert "POST    /    admins" in text
    assert "PUT    /" not in text


def test_public_default_summary_lists_only_explicit_protected_routes(monkeypatch):
    stack = Stack(App(), "Stack")
    builder = ResourceBuilder(
        authorizers={"users": rest_authorizer(stack, "Users")},
        default_authorizer=None,
    )
    methods = [
        make_method("POST", decorators=[DecoratorInvocation("authorizer", ("users",), ())]),
        make_method("GET"),
    ]
    build(builder, stack, monkeypatch, methods)
    assert len(messages(stack, "warning", r"LAD_AUTH_PUBLIC_DEFAULT")) == 1
    found = messages(stack, "info", r"Authorization overrides[\s\S]*Default authorizer: PUBLIC")
    assert len(found) == 1
    text = found[0].entry.data
    assert "METHOD" in text and "PATH" in text and "EFFECTIVE" in text
    assert "POST    /    users" in text
    assert "GET    /" not in text


def test_no_summary_when_every_route_inherits_protected_default(monkeypatch):
    stack = Stack(App(), "Stack")
    builder = ResourceBuilder(
        authorizers={"users": rest_authorizer(stack, "Users")},
        default_authorizer="users",
    )
    build(builder, stack, monkeypatch, [make_method("GET"), make_method("POST")])
    Annotations.from_stack(stack).has_no_info("*", Match.any_value())
