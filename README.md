# Lambda API Decorators CDK

AWS CDK integration for [Lambda API Decorators](https://github.com/infrastructure-as-decorator/lambda-api-decorators). It discovers decorated handlers, interprets their metadata, creates independent Lambda functions, connects API Gateway routes, and applies configuration and grants through AWS CDK.

[The central documentation](https://infrastructure-as-decorator.github.io/) contains the complete cross-package architecture and guides.

## Installation

```bash
pip install lambda-api-decorators-cdk
```

The package supports Python 3.10 or newer and AWS CDK v2. The runtime package
must be present at the Lambda source boundary when deployed, for example in
the handler directory's `requirements.txt`:

```text
lambda-api-decorators
```

The CDK and runtime packages are versioned independently. Installing the CDK
package does not make the runtime package a Lambda dependency automatically.

## Quick start

A small project can look like this:

```text
project/
├── app.py
├── lambdas/
│   ├── __init__.py
│   ├── health.py
│   └── orders.py
└── requirements.txt
```

Each handler has one route. Two handlers in one file still produce two
independent Lambdas; there is no runtime router.

```python
# lambdas/orders.py
from lambda_api_decorators import GET, POST


@GET("/orders")
def list_orders(event, context):
    return {"statusCode": 200, "body": "[]"}


@POST("/orders")
def create_order(event, context):
    return {"statusCode": 201, "body": "{}"}
```

```python
# app.py
from aws_cdk import App, Stack
from constructs import Construct

from lambda_api_decorators_cdk import LambdaApi, LambdaApiConfig


class OrdersStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        LambdaApi(
            self,
            "OrdersApi",
            lambda_path="lambdas",
            config=LambdaApiConfig(default_runtime="python3.14"),
        )


app = App()
OrdersStack(app, "OrdersStack")
app.synth()
```

`lambda_path` is resolved from the directory where the CDK command runs.

## `LambdaApi`

The high-level construct builds immediately during construction. It accepts:

- `lambda_path`: source directory to scan;
- `source_layout`: `SourceLayout.ROOT` by default;
- `layers_path`: optional layer-discovery directory;
- `api`: a supported existing REST API or concrete `aws_apigatewayv2.HttpApi`;
- `api_type`: `ApiType.REST` or `ApiType.HTTP`;
- `config`: a `LambdaApiConfig` snapshot source.

REST is the default. HTTP APIs use `ApiType.HTTP`:

```python
from lambda_api_decorators_cdk import ApiType, LambdaApi


LambdaApi(self, "HttpApi", lambda_path="lambdas", api_type=ApiType.HTTP)
```

Created and imported REST APIs are supported. Concrete `HttpApi` instances are
supported for HTTP; the contract does not promise general support for every
`IHttpApi` implementation. When `api` is supplied, its family is checked
against `api_type`.

## `LambdaApiConfig`

Use current defaults and registries when configuring a construct:

```python
from aws_cdk import Duration
from lambda_api_decorators_cdk import LambdaApiConfig


config = LambdaApiConfig(
    default_runtime="python3.14",
    timeout=Duration.seconds(30),
    memory_size=512,
    common_environment={
        "SERVICE": "orders",
    },
    environment_registry={
        "production": {
            "ENVIRONMENT": "production",
        },
    },
)
```

The handler can select a registered environment and override the default
runtime:

```python
from lambda_api_decorators import GET, environment, runtime


@GET("/orders")
@environment("production")
@runtime("python3.12")
def orders(event, context):
    return {"statusCode": 200, "body": "[]"}
```

Precedence is `@runtime` > `default_runtime`. The selected environment is
merged with `common_environment`; the selected value wins collisions.
Supported runtime aliases are `python3.10`, `python3.11`, `python3.12`,
`python3.13`, and `python3.14`.

### Registries

| Registry | Method | Decorator consumer |
| --- | --- | --- |
| `role_registry` | `register_role` | `@role` |
| `environment_registry` | `register_environment` | `@environment` |
| `layer_registry` | `register_layer` | `@layer` |
| `security_group_registry` | `register_security_group` | `@security_group` |
| `vpc_registry` | `register_vpc` | `@vpc` |
| `dynamodb_table_registry` | `register_dynamodb_table` | `@grant_dynamodb` |
| `s3_bucket_registry` | `register_s3_bucket` | `@grant_s3` |
| `authorizer_registry` | `register_authorizer` | `@authorizer` or default |

Registry keys must be non-empty strings. Duplicate keys are rejected and a
missing key is an error. Configuration snapshots isolate mutable mappings while
preserving the identity of supplied CDK/JSII objects.

Other supported configuration values include `timeout`, `memory_size`,
`default_role`, `vpc`/`vpc_subnets`, `layers`, and `security_groups`. A
configuration object must be complete before passing it to `LambdaApi`.

## Roles

Role selection follows:

```text
@role > default_role > role generated by CDK
```

A Lambda has one execution role. A registry supplies alternatives; it does not
attach multiple roles to one function. Without a default or override, CDK
creates an independent role. When one explicit role is shared, its grants are
the union required by the functions that use it; CDK emits
`LAD_ROLE_SHARED_PERMISSIONS` as a diagnostic.

## DynamoDB and S3 grants

Register a CDK resource, then declare the handler's intent separately:

```python
from aws_cdk import Stack
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct

from lambda_api_decorators import GET, grant_dynamodb
from lambda_api_decorators_cdk import LambdaApi, LambdaApiConfig


class DataStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        orders_table = dynamodb.Table(
            self,
            "Orders",
            partition_key=dynamodb.Attribute(
                name="id", type=dynamodb.AttributeType.STRING
            ),
        )
        config = LambdaApiConfig(
            dynamodb_table_registry={"orders": orders_table},
        )
        LambdaApi(self, "DataApi", lambda_path="lambdas", config=config)


@GET("/orders")
@grant_dynamodb("orders", "read")
def list_orders(event, context):
    return {"statusCode": 200, "body": "[]"}
```

`read` produces a read grant. `write` represents the native cumulative
read/write grant. S3 uses the same separation with `s3_bucket_registry` and
`@grant_s3`; registration identifies the CDK resource and the decorator
requests permission for it.

## Authorizers

The recommended registry API works with REST or HTTP CDK authorizer objects.
For a REST Cognito authorizer:

```python
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito

from lambda_api_decorators import GET, public
from lambda_api_decorators_cdk import LambdaApiConfig


cognito_pool = cognito.UserPool(self, "Users")
cognito_authorizer = apigateway.CognitoUserPoolsAuthorizer(
    self,
    "CognitoAuthorizer",
    cognito_user_pools=[cognito_pool],
)
config = LambdaApiConfig(
    default_runtime="python3.14",
    authorizer_registry={
        "cognito": cognito_authorizer,
    },
    default_authorizer="cognito",
)


@GET("/me")
def me(event, context):
    return {"statusCode": 200, "body": "{}"}


@GET("/health")
@public
def health(event, context):
    return {"statusCode": 200, "body": "ok"}
```

`me` inherits the default authorizer. `@public` has no parentheses and makes a
REST route use `AuthorizationType.NONE`. With no default authorizer, routes
are public and CDK emits `LAD_AUTH_PUBLIC_DEFAULT`. Authorizer, VPC, and role
deviations are reported through consolidated diagnostics. API keys and usage
plans are outside this contract.

## Source layouts

`SourceLayout.ROOT` packages handlers relative to `lambda_path`. Use
`SourceLayout.SERVICE` when the first directory is the service boundary:

```python
from lambda_api_decorators_cdk import LambdaApi, SourceLayout


LambdaApi(
    self,
    "ServiceApi",
    lambda_path="services",
    source_layout=SourceLayout.SERVICE,
)
```

The Lambda source boundary also determines where requirements are installed.
`SERVICE` requires a first-level service directory. Use enum members, not the
strings `"root"` or `"service"`, as the public API.

## Layers

Discover direct child layer directories and reference a layer by key:

```python
from lambda_api_decorators import GET, layer
from lambda_api_decorators_cdk import LambdaApi


LambdaApi(
    self,
    "LayeredApi",
    lambda_path="lambdas",
    layers_path="layers",
)


@GET("/orders")
@layer("orders")
def orders(event, context):
    return {"statusCode": 200, "body": "[]"}
```

Only visible direct children are discovery keys, and only referenced Layers
are synthesized. An explicit `layer_registry` entry can win over discovery.
A Layer shares code; it does not share roles or permissions.

## `ResourceBuilder`

`ResourceBuilder` remains a supported low-level API when direct control of an
API resource and build lifecycle is needed. `LambdaApi` is preferred for new
code and delegates option resolution to isolated builder snapshots. A minimal
low-level call uses the existing methods:

```python
from aws_cdk import Duration
from lambda_api_decorators_cdk import ResourceBuilder


builder = ResourceBuilder()
builder.set_default_timeout(Duration.seconds(30))
builder.build(self, rest_api.root, "lambdas")
```

## Examples

The integrated examples repository contains:

- [Quickstart REST](https://github.com/infrastructure-as-decorator/lambda-api-decorators-examples/tree/main/quickstart-rest)
- [HTTP API](https://github.com/infrastructure-as-decorator/lambda-api-decorators-examples/tree/main/http-api)
- [REST API DynamoDB](https://github.com/infrastructure-as-decorator/lambda-api-decorators-examples/tree/main/rest-api-dynamodb)
- [REST API Cognito authorizer](https://github.com/infrastructure-as-decorator/lambda-api-decorators-examples/tree/main/rest-api-cognito-authorizer)

## Releases

Tags are the source of the version through `setuptools-scm`, and this package
is released independently from the runtime package:

```bash
git switch main
git pull --ff-only
git tag vX.Y.Z
git push origin vX.Y.Z
```

The tag triggers the release workflow, which tests, builds, verifies the
generated version, and publishes through PyPI trusted publishing.
