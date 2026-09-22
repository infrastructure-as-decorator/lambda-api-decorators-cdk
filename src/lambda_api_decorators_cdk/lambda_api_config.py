from collections.abc import Mapping
from typing import Optional, Sequence

from aws_cdk import Duration
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3

from .resource_builder import ResourceBuilder


class LambdaApiConfig:
    """Reusable defaults and named resources for a :class:`LambdaApi` build."""

    def __init__(
        self,
        *,
        runtime: Optional[lambda_.Runtime] = None,
        timeout: Optional[Duration] = None,
        memory_size: Optional[int] = None,
        vpc: Optional[ec2.IVpc] = None,
        vpc_subnets: Optional[ec2.SubnetSelection] = None,
        role: Optional[iam.IRole] = None,
        layers: Optional[Sequence[lambda_.ILayerVersion]] = None,
        security_groups: Optional[Sequence[ec2.ISecurityGroup]] = None,
        environment: Optional[Mapping[str, str]] = None,
        dynamodb_tables: Optional[Mapping[str, dynamodb.ITable]] = None,
        s3_buckets: Optional[Mapping[str, s3.IBucket]] = None,
        authorizers: Optional[Mapping[str, object]] = None,
        default_authorizer: Optional[str] = None,
        default_runtime: Optional[str] = None,
        default_role: Optional[iam.IRole] = None,
        common_environment: Optional[Mapping[str, str]] = None,
        role_registry: Optional[Mapping[str, iam.IRole]] = None,
        environment_registry: Optional[Mapping[str, Mapping[str, str]]] = None,
        layer_registry: Optional[Mapping[str, lambda_.ILayerVersion]] = None,
        security_group_registry: Optional[Mapping[str, ec2.ISecurityGroup]] = None,
        vpc_registry: Optional[Mapping[str, ec2.IVpc]] = None,
        dynamodb_table_registry: Optional[Mapping[str, dynamodb.ITable]] = None,
        s3_bucket_registry: Optional[Mapping[str, s3.IBucket]] = None,
        authorizer_registry: Optional[Mapping[str, object]] = None,
    ) -> None:
        if default_runtime is not None:
            self._validate_runtime_name(default_runtime)
        if default_runtime is not None and runtime is not None:
            raise ValueError("runtime and default_runtime cannot both be supplied")
        if default_role is not None and role is not None:
            raise ValueError("role and default_role cannot both be supplied")
        if common_environment is not None and environment is not None:
            raise ValueError(
                "environment and common_environment cannot both be supplied"
            )

        self._default_runtime = runtime
        self._default_timeout = timeout
        self._default_memory_size = memory_size
        self._default_vpc = (vpc, vpc_subnets) if vpc is not None else None
        self._default_role = role

        self._common_layers = list(layers) if layers is not None else []
        self._common_security_groups = (
            list(security_groups) if security_groups is not None else []
        )
        self._common_environments = dict(
            common_environment if common_environment is not None else environment or {}
        )
        if default_runtime is not None:
            self._default_runtime = default_runtime
        if default_role is not None:
            self._default_role = default_role

        self._custom_runtimes = {}
        self._custom_roles = {}
        self._custom_layers = {}
        self._custom_environments = {}
        self._custom_security_groups = {}
        self._custom_vpcs = {}

        self._dynamodb_tables = {}
        self._s3_buckets = {}
        self._authorizers = {}
        for key, table in (dynamodb_tables or {}).items():
            self.add_dynamodb_table(key, table)
        for key, bucket in (s3_buckets or {}).items():
            self.add_s3_bucket(key, bucket)
        for key, authorizer in (authorizers or {}).items():
            self.add_authorizer(key, authorizer)
        self._default_authorizer = None
        self.set_default_authorizer(default_authorizer)

        for key, value in (role_registry or {}).items():
            self.register_role(key, value)
        for key, value in (environment_registry or {}).items():
            self.register_environment(key, value)
        for key, value in (layer_registry or {}).items():
            self.register_layer(key, value)
        for key, value in (security_group_registry or {}).items():
            self.register_security_group(key, value)
        for key, value in (vpc_registry or {}).items():
            self.register_vpc(key, value)
        for key, value in (dynamodb_table_registry or {}).items():
            self.register_dynamodb_table(key, value)
        for key, value in (s3_bucket_registry or {}).items():
            self.register_s3_bucket(key, value)
        for key, value in (authorizer_registry or {}).items():
            self.register_authorizer(key, value)

    @staticmethod
    def _validate_runtime_name(runtime: str) -> None:
        supported = {
            "python3.10", "python3.11", "python3.12", "python3.13", "python3.14"
        }
        if not isinstance(runtime, str):
            raise TypeError("runtime must be a string")
        if runtime not in supported:
            raise ValueError(
                "runtime must be one of {}".format(", ".join(sorted(supported)))
            )

    @staticmethod
    def _validate_registry_key(key: str, registry_name: str) -> None:
        if not isinstance(key, str):
            raise TypeError(f"{registry_name} keys must be strings")
        if not key.strip():
            raise ValueError(f"{registry_name} keys must not be empty or whitespace")

    @classmethod
    def _register(cls, registry: dict, key: str, value, registry_name: str) -> None:
        cls._validate_registry_key(key, registry_name)
        if key in registry:
            raise ValueError(f"{registry_name} key {key!r} is already registered")
        registry[key] = value

    def set_default_runtime(self, runtime: Optional[lambda_.Runtime]) -> None:
        self._default_runtime = runtime

    def set_default_timeout(self, timeout: Optional[Duration]) -> None:
        self._default_timeout = timeout

    def set_default_memory_size(self, memory_size: Optional[int]) -> None:
        self._default_memory_size = memory_size

    def set_default_vpc(
        self,
        vpc: Optional[ec2.IVpc],
        vpc_subnets: Optional[ec2.SubnetSelection] = None,
    ) -> None:
        self._default_vpc = (vpc, vpc_subnets) if vpc is not None else None

    def set_default_role(self, role: Optional[iam.IRole]) -> None:
        self._default_role = role

    def add_common_layer(self, layer: lambda_.ILayerVersion) -> None:
        if layer not in self._common_layers:
            self._common_layers.append(layer)

    def add_common_security_group(
        self, security_group: ec2.ISecurityGroup
    ) -> None:
        if security_group not in self._common_security_groups:
            self._common_security_groups.append(security_group)

    def add_custom_runtime(self, key: str, runtime: lambda_.Runtime) -> None:
        self._custom_runtimes[key] = runtime

    def add_custom_role(self, key: str, role: iam.IRole) -> None:
        self._custom_roles[key] = role

    def add_custom_layer(self, key: str, layer: lambda_.ILayerVersion) -> None:
        self._custom_layers[key] = layer

    def add_custom_environment(self, key: str, value: str) -> None:
        self._custom_environments[key] = value

    def add_custom_security_group(
        self, key: str, security_group: ec2.ISecurityGroup
    ) -> None:
        self._custom_security_groups[key] = security_group

    def add_custom_vpc(
        self,
        key: str,
        vpc: ec2.IVpc,
        vpc_subnets: Optional[ec2.SubnetSelection] = None,
    ) -> None:
        self._custom_vpcs[key] = (vpc, vpc_subnets)

    def add_dynamodb_table(self, key: str, table: dynamodb.ITable) -> None:
        self._add_resource(key, table, self._dynamodb_tables, "DynamoDB table")

    def add_s3_bucket(self, key: str, bucket: s3.IBucket) -> None:
        self._add_resource(key, bucket, self._s3_buckets, "S3 bucket")

    def add_authorizer(self, key: str, authorizer: object) -> None:
        if not isinstance(key, str):
            raise TypeError("Authorizer registry keys must be strings")
        if not key.strip():
            raise ValueError("Authorizer registry keys must not be empty or whitespace")
        interfaces = getattr(authorizer, "__jsii_ifaces__", ()) if authorizer is not None else ()
        supported = {
            "aws_cdk.aws_apigateway.IAuthorizer",
            "aws_cdk.aws_apigatewayv2.IHttpRouteAuthorizer",
        }
        if not any(f"{interface.__module__}.{interface.__name__}" in supported
                   for interface in interfaces):
            raise TypeError("Authorizer must be a CDK authorizer object")
        if key in self._authorizers:
            raise ValueError(f"Authorizer key {key!r} is already registered")
        self._authorizers[key] = authorizer

    def register_role(self, key: str, role: iam.IRole) -> None:
        self._register(self._custom_roles, key, role, "role registry")

    def register_environment(self, key: str, value: Mapping[str, str]) -> None:
        if not isinstance(value, Mapping):
            raise TypeError("environment registry values must be mappings")
        self._register(self._custom_environments, key, dict(value), "environment registry")

    def register_layer(self, key: str, layer: lambda_.ILayerVersion) -> None:
        self._register(self._custom_layers, key, layer, "layer registry")

    def register_security_group(self, key: str, security_group: ec2.ISecurityGroup) -> None:
        self._register(
            self._custom_security_groups, key, security_group, "security group registry"
        )

    def register_vpc(
        self,
        key: str,
        vpc: ec2.IVpc,
        vpc_subnets: Optional[ec2.SubnetSelection] = None,
    ) -> None:
        self._register(self._custom_vpcs, key, (vpc, vpc_subnets), "vpc registry")

    def register_dynamodb_table(self, key: str, table: dynamodb.ITable) -> None:
        self._register(self._dynamodb_tables, key, table, "dynamodb table registry")

    def register_s3_bucket(self, key: str, bucket: s3.IBucket) -> None:
        self._register(self._s3_buckets, key, bucket, "s3 bucket registry")

    def register_authorizer(self, key: str, authorizer: object) -> None:
        self._validate_registry_key(key, "authorizer registry")
        interfaces = getattr(authorizer, "__jsii_ifaces__", ()) if authorizer is not None else ()
        supported = {
            "aws_cdk.aws_apigateway.IAuthorizer",
            "aws_cdk.aws_apigatewayv2.IHttpRouteAuthorizer",
        }
        if not any(
            f"{interface.__module__}.{interface.__name__}" in supported
            for interface in interfaces
        ):
            raise TypeError("authorizer registry values must be CDK authorizers")
        self._register(self._authorizers, key, authorizer, "authorizer registry")

    def set_default_authorizer(self, key: Optional[str]) -> None:
        if key is None:
            self._default_authorizer = None
            return
        if not isinstance(key, str):
            raise TypeError("Default authorizer key must be a string or None")
        if not key.strip():
            raise ValueError("Default authorizer key must not be empty or whitespace")
        if key not in self._authorizers:
            raise KeyError(f"Authorizer key {key!r} is not registered")
        self._default_authorizer = key

    @staticmethod
    def _add_resource(key: str, resource, registry: dict, resource_type: str) -> None:
        if not isinstance(key, str):
            raise TypeError("Resource registry keys must be strings")
        if not key.strip():
            raise ValueError("Resource registry keys must not be empty or whitespace")
        if resource is None or isinstance(resource, (str, int)):
            raise TypeError(f"{resource_type} must be a CDK resource object")
        if key in registry:
            raise ValueError(f"Resource key {key!r} is already registered")
        registry[key] = resource

    def _create_resource_builder(self) -> ResourceBuilder:
        """Create an isolated builder snapshot without copying CDK resources."""
        return ResourceBuilder(
            default_runtime=self._default_runtime,
            default_timeout=self._default_timeout,
            default_memory_size=self._default_memory_size,
            default_vpc=self._default_vpc,
            default_role=self._default_role,
            common_layers=list(self._common_layers),
            common_security_groups=list(self._common_security_groups),
            common_environments=dict(self._common_environments),
            custom_runtimes=dict(self._custom_runtimes),
            custom_roles=dict(self._custom_roles),
            custom_layers=dict(self._custom_layers),
            custom_environments={
                key: dict(value) if isinstance(value, Mapping) else value
                for key, value in self._custom_environments.items()
            },
            custom_security_groups=dict(self._custom_security_groups),
            custom_vpcs=dict(self._custom_vpcs),
            dynamodb_tables=dict(self._dynamodb_tables),
            s3_buckets=dict(self._s3_buckets),
            authorizers=dict(self._authorizers),
            default_authorizer=self._default_authorizer,
        )
