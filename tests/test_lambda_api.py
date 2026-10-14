import inspect
from enum import Enum

import pytest
from aws_cdk import App, Stack, aws_apigateway as apigateway
from aws_cdk import aws_apigatewayv2 as apigatewayv2
from aws_cdk.assertions import Template
from constructs import Construct

from lambda_api_decorators_cdk import ApiType, LambdaApi, LambdaApiConfig


class RecordingBuilder:
    def __init__(self):
        self.rest_calls = []
        self.http_calls = []
        self.rest_layouts = []
        self.http_layouts = []
        self.rest_layers_paths = []
        self.http_layers_paths = []

    def build(self, *args, source_layout=None, layers_path=None):
        self.rest_calls.append(args)
        self.rest_layouts.append(source_layout)
        if hasattr(self, "rest_layers_paths"):
            self.rest_layers_paths.append(layers_path)

    def build_http(self, *args, source_layout=None, layers_path=None):
        self.http_calls.append(args)
        self.http_layouts.append(source_layout)
        if hasattr(self, "http_layers_paths"):
            self.http_layers_paths.append(layers_path)


class _FutureSourceLayout(Enum):
    ROOT = "root"
    SERVICE = "service"


def source_layout(name):
    try:
        from lambda_api_decorators_cdk import SourceLayout
    except ImportError:
        SourceLayout = _FutureSourceLayout
    return SourceLayout[name]


@pytest.fixture
def stack():
    return Stack(App(), "Stack")


@pytest.fixture
def builders(monkeypatch):
    created = []

    def create(_config):
        builder = RecordingBuilder()
        created.append(builder)
        return builder

    monkeypatch.setattr(LambdaApiConfig, "_create_resource_builder", create)
    return created


@pytest.mark.parametrize("explicit", [False, True])
def test_rest_is_default_and_builds_under_construct(stack, builders, explicit):
    kwargs = {"api_type": ApiType.REST} if explicit else {}
    subject = LambdaApi(stack, "Api", lambda_path="lambdas", **kwargs)
    assert isinstance(subject, Construct)
    assert subject.node.scope is stack
    assert isinstance(subject.api, apigateway.RestApiBase)
    assert subject.api.node.scope is subject
    assert subject.api_type is ApiType.REST
    owner, root, path = builders[0].rest_calls[0]
    assert owner is subject and path == "lambdas"
    assert root.path == subject.api.root.path
    assert root.resource_id == subject.api.root.resource_id
    assert builders[0].http_calls == []


@pytest.mark.parametrize("endpoint_type", [None, apigateway.EndpointType.EDGE])
def test_created_rest_api_defaults_to_or_accepts_edge_endpoint(
        stack, builders, endpoint_type):
    kwargs = {} if endpoint_type is None else {"endpoint_type": endpoint_type}
    subject = LambdaApi(stack, "Api", lambda_path="lambdas", **kwargs)
    subject.api.root.add_resource("health").add_method(
        "GET", apigateway.MockIntegration())

    Template.from_stack(stack).has_resource_properties(
        "AWS::ApiGateway::RestApi",
        {"EndpointConfiguration": {"Types": ["EDGE"]}},
    )


def test_created_rest_api_accepts_regional_endpoint(stack, builders):
    subject = LambdaApi(
        stack, "Api", lambda_path="lambdas",
        endpoint_type=apigateway.EndpointType.REGIONAL,
    )
    subject.api.root.add_resource("health").add_method(
        "GET", apigateway.MockIntegration())

    Template.from_stack(stack).has_resource_properties(
        "AWS::ApiGateway::RestApi",
        {"EndpointConfiguration": {"Types": ["REGIONAL"]}},
    )


@pytest.mark.parametrize("endpoint_type", [
    apigateway.EndpointType.PRIVATE,
    "REGIONAL",
    object(),
])
def test_invalid_created_rest_endpoint_type_fails_before_build(
        stack, builders, endpoint_type):
    with pytest.raises((TypeError, ValueError)):
        LambdaApi(
            stack, "Api", lambda_path="lambdas", endpoint_type=endpoint_type)
    assert builders == []
    assert not any(
        isinstance(node, apigateway.RestApiBase)
        for node in stack.node.find_all()
    )


@pytest.mark.parametrize("endpoint_type", [
    apigateway.EndpointType.EDGE,
    apigateway.EndpointType.REGIONAL,
])
def test_http_api_rejects_explicit_endpoint_type_before_build(
        stack, builders, endpoint_type):
    with pytest.raises(ValueError):
        LambdaApi(
            stack, "Api", lambda_path="lambdas", api_type=ApiType.HTTP,
            endpoint_type=endpoint_type,
        )
    assert builders == []
    assert not any(
        isinstance(node, apigatewayv2.HttpApi)
        for node in stack.node.find_all()
    )


def test_lambda_api_constructor_has_layer_autodiscovery_parameter():
    parameters = inspect.signature(LambdaApi.__init__).parameters
    assert list(parameters) == [
        "self", "scope", "construct_id", "lambda_path", "source_layout",
        "layers_path", "api", "api_type", "config", "endpoint_type"]
    for name in (
        "lambda_path", "source_layout", "layers_path", "api", "api_type",
        "config", "endpoint_type"
    ):
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["layers_path"].default is None
    assert parameters["endpoint_type"].default is None
    assert not {"api_resource", "print_tree"}.intersection(parameters)


@pytest.mark.parametrize("api_type, call_kind", [
    (ApiType.REST, "rest"),
    (ApiType.HTTP, "http"),
])
@pytest.mark.parametrize("layers_path", [None, "layers"])
def test_lambda_api_propagates_layers_path(
        stack, builders, api_type, call_kind, layers_path):
    kwargs = {} if layers_path is None else {"layers_path": layers_path}
    LambdaApi(
        stack, "Api", lambda_path="lambdas", api_type=api_type, **kwargs)
    assert getattr(builders[0], f"{call_kind}_layers_paths") == [layers_path]


@pytest.mark.parametrize("api_type, call_kind", [
    (ApiType.REST, "rest"),
    (ApiType.HTTP, "http"),
])
def test_lambda_api_defaults_source_layout_to_root_at_build_boundary(
        stack, builders, api_type, call_kind):
    LambdaApi(stack, "Api", lambda_path="lambdas", api_type=api_type)
    assert getattr(builders[0], f"{call_kind}_layouts") == [source_layout("ROOT")]


@pytest.mark.parametrize("api_type, call_kind", [
    (ApiType.REST, "rest"),
    (ApiType.HTTP, "http"),
])
@pytest.mark.parametrize("layout_name", ["ROOT", "SERVICE"])
def test_lambda_api_propagates_explicit_source_layout(
        stack, builders, api_type, call_kind, layout_name):
    layout = source_layout(layout_name)
    LambdaApi(
        stack, "Api", lambda_path="lambdas", api_type=api_type,
        source_layout=layout,
    )
    assert getattr(builders[0], f"{call_kind}_layouts") == [layout]


@pytest.mark.parametrize("value", ["root", "service"])
def test_lambda_api_rejects_string_source_layout_before_build(stack, builders, value):
    with pytest.raises(TypeError):
        LambdaApi(stack, "Api", lambda_path="lambdas", source_layout=value)
    assert builders == []


def test_explicit_http_builds_under_construct(stack, builders):
    subject = LambdaApi(
        stack, "Api", lambda_path="functions", api_type=ApiType.HTTP)
    assert isinstance(subject.api, apigatewayv2.HttpApi)
    assert subject.api.node.scope is subject
    assert subject.api_type is ApiType.HTTP
    assert builders[0].rest_calls == []
    assert builders[0].http_calls == [(subject, subject.api, "functions")]


@pytest.mark.parametrize("explicit", [False, True])
def test_existing_rest_is_inferred_and_reused(stack, builders, explicit):
    existing = apigateway.RestApi(stack, "Existing")
    before = [node for node in stack.node.find_all()
              if isinstance(node, apigateway.RestApi)]
    kwargs = {"api_type": ApiType.REST} if explicit else {}
    subject = LambdaApi(
        stack, "Api", lambda_path="lambdas", api=existing, **kwargs)
    assert subject.api is existing
    assert subject.api_type is ApiType.REST
    owner, root, path = builders[0].rest_calls[0]
    assert owner is subject and path == "lambdas"
    assert root.path == existing.root.path
    assert root.resource_id == existing.root.resource_id
    after = [node for node in stack.node.find_all()
             if isinstance(node, apigateway.RestApi)]
    assert after == before


def test_imported_rest_api_is_supported(stack, builders):
    imported = apigateway.RestApi.from_rest_api_attributes(
        stack, "Imported", rest_api_id="api-id", root_resource_id="root-id")
    subject = LambdaApi(stack, "Api", lambda_path="lambdas", api=imported)
    assert subject.api is imported
    assert subject.api_type is ApiType.REST
    owner, root, path = builders[0].rest_calls[0]
    assert owner is subject and path == "lambdas"
    assert root.path == imported.root.path
    assert root.resource_id == imported.root.resource_id


@pytest.mark.parametrize("api_kind", ["created", "imported"])
def test_supplied_rest_api_rejects_explicit_endpoint_type(
        stack, builders, api_kind):
    api = (
        apigateway.RestApi(stack, "Existing")
        if api_kind == "created"
        else apigateway.RestApi.from_rest_api_attributes(
            stack, "Imported", rest_api_id="api-id", root_resource_id="root-id")
    )
    with pytest.raises(ValueError):
        LambdaApi(
            stack, "Api", lambda_path="lambdas", api=api,
            endpoint_type=apigateway.EndpointType.REGIONAL,
        )
    assert builders == []


@pytest.mark.parametrize("explicit", [False, True])
def test_existing_http_is_inferred_and_reused(stack, builders, explicit):
    existing = apigatewayv2.HttpApi(stack, "Existing")
    before = [node for node in stack.node.find_all()
              if isinstance(node, apigatewayv2.HttpApi)]
    kwargs = {"api_type": ApiType.HTTP} if explicit else {}
    subject = LambdaApi(
        stack, "Api", lambda_path="lambdas", api=existing, **kwargs)
    assert subject.api is existing
    assert subject.api_type is ApiType.HTTP
    assert builders[0].http_calls == [(subject, existing, "lambdas")]
    after = [node for node in stack.node.find_all()
             if isinstance(node, apigatewayv2.HttpApi)]
    assert after == before


def test_supplied_http_api_rejects_explicit_endpoint_type(stack, builders):
    existing = apigatewayv2.HttpApi(stack, "Existing")
    with pytest.raises(ValueError):
        LambdaApi(
            stack, "Api", lambda_path="lambdas", api=existing,
            endpoint_type=apigateway.EndpointType.EDGE,
        )
    assert builders == []


@pytest.mark.parametrize("kind,wrong", [
    ("rest", ApiType.HTTP), ("http", ApiType.REST),
])
def test_conflicting_type_fails_before_build(stack, builders, kind, wrong):
    api = (apigateway.RestApi(stack, "Existing") if kind == "rest"
           else apigatewayv2.HttpApi(stack, "Existing"))
    with pytest.raises(ValueError, match="conflict"):
        LambdaApi(stack, "Api", lambda_path="lambdas", api=api, api_type=wrong)
    assert builders == []


@pytest.mark.parametrize("argument", ["api", "api_type", "config"])
def test_invalid_wrapper_values_fail_before_build(stack, builders, argument):
    with pytest.raises(TypeError):
        LambdaApi(stack, "Api", lambda_path="lambdas", **{argument: object()})
    assert builders == []


def test_imported_general_http_api_is_rejected(stack, builders):
    imported = apigatewayv2.HttpApi.from_http_api_attributes(
        stack, "Imported", http_api_id="api-id")
    assert not isinstance(imported, apigatewayv2.HttpApi)
    assert not hasattr(imported, "add_routes")
    with pytest.raises(TypeError):
        LambdaApi(stack, "Api", lambda_path="lambdas", api=imported)
    assert builders == []


def test_reused_config_creates_fresh_builders_and_separate_subtrees(
        stack, monkeypatch):
    layer, created = object(), []
    config = LambdaApiConfig(layers=[layer])
    original = LambdaApiConfig._create_resource_builder

    def create(self):
        builder = original(self)
        builder.rest_calls, builder.http_calls = [], []
        builder.rest_layouts, builder.http_layouts = [], []
        monkeypatch.setattr(builder, "build", RecordingBuilder.build.__get__(builder))
        monkeypatch.setattr(builder, "build_http", RecordingBuilder.build_http.__get__(builder))
        created.append(builder)
        return builder

    monkeypatch.setattr(LambdaApiConfig, "_create_resource_builder", create)
    first = LambdaApi(stack, "ApiA", lambda_path="a", config=config)
    second = LambdaApi(stack, "ApiB", lambda_path="b", config=config)
    assert first.node.path != second.node.path
    assert created[0] is not created[1]
    assert created[0].common_layers is not created[1].common_layers
    assert created[0].common_layers[0] is layer
    assert created[1].common_layers[0] is layer
    created[0].common_layers.append("first-only")
    assert created[1].common_layers == [layer]


def test_reused_config_builds_with_independent_source_layouts(stack, monkeypatch):
    created = []
    config = LambdaApiConfig()
    original = LambdaApiConfig._create_resource_builder

    def create(self):
        builder = original(self)
        builder.rest_calls, builder.http_calls = [], []
        builder.rest_layouts, builder.http_layouts = [], []
        monkeypatch.setattr(builder, "build", RecordingBuilder.build.__get__(builder))
        monkeypatch.setattr(
            builder, "build_http", RecordingBuilder.build_http.__get__(builder))
        created.append(builder)
        return builder

    monkeypatch.setattr(LambdaApiConfig, "_create_resource_builder", create)
    LambdaApi(
        stack, "RootApi", lambda_path="root", config=config,
        source_layout=source_layout("ROOT"),
    )
    LambdaApi(
        stack, "ServiceApi", lambda_path="services", config=config,
        source_layout=source_layout("SERVICE"),
    )

    assert created[0] is not created[1]
    assert created[0].rest_layouts == [source_layout("ROOT")]
    assert created[1].rest_layouts == [source_layout("SERVICE")]


def test_custom_config_registration_reaches_lambda_api_builder(stack, monkeypatch):
    layer, captured = object(), []
    config = LambdaApiConfig()
    config.add_custom_layer("shared", layer)
    original = LambdaApiConfig._create_resource_builder

    def create(self):
        builder = original(self)
        builder.rest_calls, builder.http_calls = [], []
        builder.rest_layouts, builder.http_layouts = [], []
        monkeypatch.setattr(builder, "build", RecordingBuilder.build.__get__(builder))
        monkeypatch.setattr(builder, "build_http", RecordingBuilder.build_http.__get__(builder))
        captured.append(builder)
        return builder

    monkeypatch.setattr(LambdaApiConfig, "_create_resource_builder", create)
    LambdaApi(stack, "Api", lambda_path="lambdas", config=config)
    assert len(captured) == 1
    assert captured[0].custom_layers["shared"] is layer


def test_lambda_api_does_not_expose_post_build_configuration(stack, builders):
    subject = LambdaApi(stack, "Api", lambda_path="lambdas")
    forbidden = (
        "set_default_runtime", "set_default_timeout", "set_default_memory_size",
        "set_default_vpc", "set_default_role", "add_custom_runtime",
        "add_custom_role", "add_custom_layer", "add_custom_environment",
        "add_custom_security_group", "add_custom_vpc", "resource_builder",
        "rest_api", "http_api",
    )
    assert all(not hasattr(subject, name) for name in forbidden)
