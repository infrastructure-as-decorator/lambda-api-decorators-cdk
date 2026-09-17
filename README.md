# Lambda API Decorators CDK

AWS CDK integration for [Lambda API Decorators](https://github.com/infrastructure-as-decorator/lambda-api-decorators). Define API routes with Python decorators and let CDK create the Lambda functions, integrations, routes, and related configuration.

The complete cross-package guides and architecture documentation are available at [infrastructure-as-decorator.github.io](https://infrastructure-as-decorator.github.io/).

## Installation

```bash
pip install lambda-api-decorators-cdk
```

The package requires Python 3.10 or newer and AWS CDK v2. The `lambda-api-decorators` package provides the decorators used by the Lambda source files.

## Quick start

`LambdaApi` is the recommended high-level construct. It creates a REST API by default and discovers decorated handlers below `lambda_path`.

```python
from aws_cdk import Stack
from constructs import Construct

from lambda_api_decorators_cdk import LambdaApi


class ExampleStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        LambdaApi(self, "ExampleApi", lambda_path="lambdas")
```

A handler must include an HTTP method decorator from `lambda-api-decorators`:

```python
from lambda_api_decorators import GET


@GET("/hello")
def hello(event, context):
    return {"statusCode": 200, "body": "Hello, world!"}
```

`lambda_path` is resolved from the directory where CDK is run. Files without a supported route decorator are ignored.

## API types and imported APIs

REST is the default. Select an HTTP API with `ApiType.HTTP`, or provide an existing supported API and let the construct infer its type.

```python
from aws_cdk import aws_apigateway as apigateway
from lambda_api_decorators_cdk import ApiType, LambdaApi


LambdaApi(self, "HttpApi", lambda_path="lambdas", api_type=ApiType.HTTP)

existing_rest_api = apigateway.RestApi(self, "ExistingRestApi")
LambdaApi(self, "ExistingApiRoutes", lambda_path="lambdas", api=existing_rest_api)
```

Created and imported REST APIs are supported. Concrete `aws_apigatewayv2.HttpApi` instances are supported for HTTP APIs.

## Reusable configuration

Use `LambdaApiConfig` for defaults and named resources shared by one or more `LambdaApi` constructs. Configuration must be complete before constructing the API.

```python
from aws_cdk import Duration, aws_lambda as lambda_
from lambda_api_decorators_cdk import LambdaApi, LambdaApiConfig


config = LambdaApiConfig(
    runtime=lambda_.Runtime.PYTHON_3_12,
    timeout=Duration.seconds(30),
    memory_size=512,
    environment={"ENVIRONMENT": "production"},
)
config.add_custom_environment("PAYMENTS_URL", "https://payments.example.com")

LambdaApi(self, "ConfiguredApi", lambda_path="lambdas", config=config)
```

`LambdaApiConfig` supports default and custom runtimes, roles, VPCs, subnets, layers, security groups, and environment variables. It also supports registries for DynamoDB tables, S3 buckets, and REST or HTTP authorizers. A reused configuration creates an isolated builder snapshot for each API.

## Source layout and layers

By default, each handler is packaged relative to the source root. For a service-oriented layout, use `SourceLayout.SERVICE`:

```python
from lambda_api_decorators_cdk import LambdaApi, SourceLayout


LambdaApi(
    self,
    "ServiceApi",
    lambda_path="services",
    source_layout=SourceLayout.SERVICE,
    layers_path="layers",
)
```

When `layers_path` is provided, each visible child directory is treated as a discoverable layer source. Explicit layer configuration remains available through `LambdaApiConfig`.

## Authorization and permissions

Register authorizers with a logical key and select the default authorizer for routes. A handler can override the default with `@authorizer("key")` or make itself public with `@public`.

```python
from aws_cdk import aws_apigateway as apigateway
from lambda_api_decorators_cdk import LambdaApiConfig


authorizer = apigateway.TokenAuthorizer(self, "UsersAuthorizer", handler=authorizer_fn)
config = LambdaApiConfig(authorizers={"users": authorizer}, default_authorizer="users")
```

The resource registries also allow decorated handlers to request least-privilege grants for registered DynamoDB tables and S3 buckets. See the [complete documentation](https://infrastructure-as-decorator.github.io/docs/api-reference/index) for decorator syntax and supported access levels.

## Low-level builder

`ResourceBuilder` remains a supported lower-level API for callers that need direct control over the API root or build lifecycle:

```python
from aws_cdk import Duration
from lambda_api_decorators_cdk import ResourceBuilder


builder = ResourceBuilder()
builder.set_default_timeout(Duration.seconds(30))
builder.add_common_environment("ENVIRONMENT", "production")
builder.build(self, rest_api.root, "lambdas")
```

Prefer `LambdaApi` for new code. It owns API creation or reuse and delegates option resolution to isolated `ResourceBuilder` snapshots.

## Releases

The Git tag is the single source of truth for this package's version. For example, `v0.3.0` produces Python package version `0.3.0`. This repository is versioned independently from `lambda-api-decorators`.

To release from `main`, push a semantic version tag:

```bash
git checkout main
git pull
git tag v0.3.0
git push origin v0.3.0
```

Pushing the tag triggers the release workflow, which tests, builds, verifies the version, and publishes to PyPI using trusted publishing. The PyPI project must have a trusted publisher configured for this repository, the `release.yml` workflow, and the `pypi` GitHub environment.
