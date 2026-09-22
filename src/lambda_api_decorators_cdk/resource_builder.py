from aws_cdk import (
    aws_ec2 as ec2,
    aws_dynamodb as dynamodb,
    aws_iam as iam, 
    Duration, 
    aws_apigateway as apigateway,
    aws_apigatewayv2 as apigateway2,
    aws_apigatewayv2_integrations as integrations,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_lambda_python_alpha as _lambda_python,
    Annotations)
import hashlib
import inspect
import os
from pathlib import Path
from lambda_api_decorators_cdk import ast_helper
from lambda_api_decorators_cdk.source_layout import SourceLayout
from typing import Optional, List, Dict
from constructs import Construct

class ResourceBuilder():
    '''
    Entrypoint to lambda_api_decorators_cdk's functionality. Create a Builder object and set the custom requirements for your Lambda Functions.

    Refer to the constructor method to get started instantiating a builder. 

    For more configuration options, use the set_default_XXXX, add_common_XXXX and add_custom_XXXX methods to add VPCs, Layers, Roles, Runtimes, Security Groups and Environment Variables. 
    '''

    def __init__(self,
                default_runtime: Optional[lambda_.Runtime] = None,
                default_timeout: Optional[Duration] = None,
                default_memory_size: Optional[int] = None,
                default_vpc = None,
                default_role: Optional[iam.Role] = None,
                common_layers: Optional[List] = None,
                common_security_groups: Optional[List[ec2.SecurityGroup]] = None,
                common_environments: Optional[Dict[str, str]] = None,
                custom_runtimes: Optional[Dict[str, lambda_.Runtime]] = None,
                custom_roles: Optional[Dict[str, iam.Role]] = None,
                custom_layers: Optional[Dict[str, None]] = None, ####TODO
                custom_environments: Optional[Dict[str, str]] = None,
                custom_security_groups: Optional[Dict[str, ec2.SecurityGroup]] = None,
                custom_vpcs = None, ####TODO
                dynamodb_tables: Optional[Dict[str, dynamodb.ITable]] = None,
                s3_buckets: Optional[Dict[str, s3.IBucket]] = None,
                authorizers: Optional[Dict[str, object]] = None,
                default_authorizer: Optional[str] = None,
                ) -> 'ResourceBuilder':
    
        '''
        Creates base instance of a Resource Builder. By default, there are no predetermined custom, common nor default settings with the exception of the following custom runtimes: python3.10, python3.11, python3.12, python3.13, python3.14.
        You can optionally specify arguments (Keep in mind some of them are constructs of the aws_cdk toolkit) such as:
        @param default_runtime
        @param default_timeout
        @param default_memory_size
        @param default_vpc
        @param default_role
        @param common_layers
        @param common_security_groups
        @param common_environments
        @param custom_runtimes
        @param custom_roles
        @param custom_layers
        @param custom_environments
        @param custom_security_groups
        @param custom_vpcs
        @param dynamodb_tables
        @param s3_buckets
        '''
        # Check and set properties based on provided keyword arguments
        self.default_runtime = default_runtime
        self.default_timeout = default_timeout
        self.default_memory_size = default_memory_size
        self.default_vpc = default_vpc
        self.default_role = default_role
        
        self.common_layers = common_layers if common_layers is not None else []
        self.common_security_groups = common_security_groups if common_security_groups is not None else []
        self.common_environments = common_environments if common_environments is not None else {}
        
        self.custom_runtimes = custom_runtimes if custom_runtimes is not None else {}
        self.custom_roles = custom_roles if custom_roles is not None else {}
        self.custom_layers = custom_layers if custom_layers is not None else {}
        self.custom_environments = custom_environments if custom_environments is not None else {}
        self.custom_security_groups = custom_security_groups if custom_security_groups is not None else {}
        self.custom_vpcs = custom_vpcs if custom_vpcs is not None else {}
        self.dynamodb_tables = dynamodb_tables if dynamodb_tables is not None else {}
        self.s3_buckets = s3_buckets if s3_buckets is not None else {}
        self.authorizers = authorizers if authorizers is not None else {}
        self.default_authorizer = default_authorizer
        self._physical_dynamodb_tables = {}
        self._physical_s3_buckets = {}

        self.custom_runtimes.update({'python3.10':lambda_.Runtime.PYTHON_3_10})
        self.custom_runtimes.update({'python3.11':lambda_.Runtime.PYTHON_3_11})
        self.custom_runtimes.update({'python3.12':lambda_.Runtime.PYTHON_3_12})
        self.custom_runtimes.update({'python3.13':lambda_.Runtime.PYTHON_3_13})
        self.custom_runtimes.update({'python3.14':lambda_.Runtime.PYTHON_3_14})


    #Setters
    def set_default_runtime(self, runtime: lambda_.Runtime):
        '''Set the default runtime every Lambda Function in the scope of the builder will have.'''
        self.default_runtime = runtime
    
    def set_default_timeout(self, timeout: Duration):
        '''Set the default timeout every Lambda Function in the scope of the builder will have. If not specified, timeout will be CDK's default.'''
        self.default_timeout = timeout

    def set_default_memory_size(self, memory_size: int):
        '''Set the default memory size every Lambda Function in the scope of the builder will have. If not specified, memory size will be CDK's default.'''
        self.default_memory_size = memory_size 

    def set_default_vpc(self, vpc, vpc_subnets: list):
        '''Set the default VPC and Subnets every Lambda Function in the scope of the builder will have. If not specified, none will be assigned to Lambda.'''
        self.default_vpc = (vpc, vpc_subnets)

    def set_default_role(self, role: iam.Role):
        '''Set the default Role and permissions every Lambda Function in the scope of the builder will have. If not specified, CDK will create it's own for your Lambda.'''
        self.default_role = role

    #Adders
    def add_common_layer(self, layer = lambda_.LayerVersion | _lambda_python.PythonLayerVersion):
        '''Add a common layer for all your Lambda Functions.'''
        self.common_layers.append(layer) if layer not in self.common_layers else None

    def add_common_security_group(self, security_group):
        '''Add a common security group for all your Lambda Functions.'''
        self.common_security_groups.append(security_group) if security_group not in self.common_security_groups else None

    def add_custom_vpc(self, key: str, vpc: ec2.Vpc, vpc_subnets: list):
        self.custom_vpcs.update({key:(vpc, vpc_subnets)})
    
    def add_custom_environment(self, key: str, value: str | int | float):
        '''Add a custom environment variable and value for every lambda function with the decorator @environment(key).'''
        self.custom_environments.update({key:value})

    def add_custom_runtime(self, key: str, value: lambda_.Runtime):
        '''Add a custom Rruntime for every lambda function with the decorator @runtime(key).'''
        self.custom_runtimes.update({key:value})

    def add_custom_role(self, key: str, value: iam.Role):
        '''Add a custom Role for every lambda function with the decorator @role(key).'''
        self.custom_roles.update({key:value})

    def add_custom_layer(self, key: str, value: lambda_.LayerVersion | _lambda_python.PythonLayerVersion):
        '''Add a custom Layer for every lambda function with the decorator @layer(key).'''
        self.custom_layers.update({key:value})

    def add_custom_security_group(self, key: str, value: ec2.SecurityGroup):
        '''Add a custom security group for every lambda function with the decorator @security_group(key).'''
        self.custom_security_groups.update({key:value})


    #Getters
    def get_default_runtime(self) -> lambda_.Runtime | None:
        return self.default_runtime
    
    def get_default_timeout(self) -> Duration | None:
        return self.default_timeout

    def get_default_memory_size(self) -> int | None:
        return self.default_memory_size

    def get_default_vpc(self) -> tuple | None:
        return self.default_vpc

    def get_default_role(self) -> iam.Role | None:
        return self.default_role
    
    def get_common_layers(self) -> list | None:
        return self.common_layers

    def get_common_layer(self, value: str) -> lambda_.LayerVersion | _lambda_python.PythonLayerVersion:
        return self.common_layers[value]
    
    def get_common_security_groups(self) -> list | None:
        return self.common_security_groups
    
    def get_common_security_group(self, value: str):
        return self.common_security_groups[value]        

    def get_common_environments(self):
        return self.common_environments
    
    def get_common_environment(self, value: str):
        return self.common_environments[value]
    
    def get_custom_layer(self, value: str) -> lambda_.LayerVersion | _lambda_python.PythonLayerVersion:
        if value in self.custom_layers:
            return self.custom_layers[value]
        else: raise KeyError(f'layer registry key {value!r} is not registered')

    def get_custom_roles(self):
        return self.custom_roles
    
    def get_custom_role(self, value: str) -> iam.Role:
        if value in self.custom_roles:
            return self.custom_roles[value]
        else: raise KeyError(f'role registry key {value!r} is not registered')
    
    def get_custom_security_group(self, value: str) -> ec2.SecurityGroup:
        if value in self.custom_security_groups:
            return self.custom_security_groups[value]
        else: raise KeyError(f'security group registry key {value!r} is not registered')
    
    def get_custom_environment(self, value: str):
        if value in self.custom_environments:
            return self.custom_environments[value]
        else: raise KeyError(f'environment registry key {value!r} is not registered')
    
    def get_custom_runtime(self, value: str) -> lambda_.Runtime: 
        if value in self.custom_runtimes:
            return self.custom_runtimes[value]
        else: raise KeyError(f'runtime alias {value!r} is not registered')
    
    def get_custom_vpc(self, value: str) -> tuple:
        try:
            return self.custom_vpcs[value]
        except KeyError:
            raise KeyError(f'vpc registry key {value!r} is not registered') from None

    def build(self, construct, api_resource: apigateway.IResource, lambda_path:str,
              print_tree: bool = False,
              source_layout: SourceLayout = SourceLayout.ROOT,
              layers_path: Optional[str] = None):
        '''
        Dynamically create Lambda Functions and Rest Api resources based on the options assigned to the builder.
        @param construct: Stack which new resources and functions will be assigned to.
        @param api_resource: REST API root resource from which the new resources/endpoints will be added.
        @param lambda_path: Relative path (from cdk project workspace root dir) to the lambda functions defined.
        @param print_tree: Optional value to output to terminal the API and functions built in a tree syntaxis.. Defaults to False.
        '''

        self._validate_source_layout(source_layout)
        lambda_root = Path(lambda_path).resolve()
        layer_sources = self._discover_layer_sources(layers_path)
        graph = ast_helper.get_lambda_graph(str(lambda_root))
        if print_tree:
            ast_helper.dump_tree(graph)
        self._prepare_layers(construct, graph, layer_sources)
        self.build_from_graph(
            construct, graph, api_resource, lambda_root, source_layout)
        self._emit_configuration_diagnostics(construct, graph)

    def build_http(self, construct, http_api: apigateway2.HttpApi,
                   lambda_path:str, print_tree: bool = False,
                   source_layout: SourceLayout = SourceLayout.ROOT,
                   layers_path: Optional[str] = None):
        '''
        Dynamically create Lambda Functions and Rest Api resources based on the options assigned to the builder.
        @param construct: Stack which new resources and functions will be assigned to.
        @param api_resource: REST API root resource from which the new resources/endpoints will be added.
        @param lambda_path: Relative path (from cdk project workspace root dir) to the lambda functions defined.
        @param print_tree: Optional value to output to terminal the API and functions built in a tree syntaxis.. Defaults to False.
        '''
        self._validate_source_layout(source_layout)
        lambda_root = Path(lambda_path).resolve()
        layer_sources = self._discover_layer_sources(layers_path)
        graph = ast_helper.get_lambda_graph(str(lambda_root))
        if print_tree:
            ast_helper.dump_tree(graph)
        self._prepare_layers(construct, graph, layer_sources)
        self.build_http_from_graph(
            construct, graph, http_api, lambda_root, source_layout)
        self._emit_configuration_diagnostics(construct, graph)

    @staticmethod
    def _discover_layer_sources(layers_path: Optional[str]):
        if layers_path is None:
            return None

        layers_root = Path(layers_path).resolve()
        if not layers_root.exists():
            raise ValueError(f"layers_path does not exist: {layers_root}")
        if not layers_root.is_dir():
            raise ValueError(f"layers_path is not a directory: {layers_root}")

        return {
            child.name: child
            for child in sorted(layers_root.iterdir(), key=lambda path: path.name)
            if not child.name.startswith('.')
            and child.name != '__pycache__'
            and child.is_dir()
        }

    @staticmethod
    def _iter_methods(graph: ast_helper.Resource):
        methods = []

        def visit(resource):
            for method in resource.get_methods():
                methods.append((resource.get_path(), method))
            for child in resource.get_connections():
                visit(child)

        visit(graph)
        methods.sort(key=lambda item: (
            item[1].get_path_to_file(),
            item[1].get_file(),
            item[1].get_handler(),
            item[0],
            item[1].get_method(),
        ))
        return [method for _, method in methods]

    def _resolve_runtime(self, decorators: dict):
        runtime = self.get_default_runtime()
        if isinstance(runtime, str):
            runtime = self.get_custom_runtime(runtime)
        if 'runtime' in decorators:
            runtime = self.get_custom_runtime(decorators['runtime'])
        return runtime

    @staticmethod
    def _runtime_name(runtime):
        try:
            name = runtime.name
        except Exception as error:
            raise ValueError("Runtime compatibility metadata is unreadable") from error
        if not isinstance(name, str):
            raise ValueError("Runtime compatibility metadata is unusable")
        return name

    def _validate_explicit_layer(self, layer, runtime, identifier):
        try:
            compatible_runtimes = layer.compatible_runtimes
        except Exception as error:
            raise ValueError(
                f"Compatibility metadata for explicit layer {identifier!r} "
                "is unreadable"
            ) from error

        if compatible_runtimes is None:
            return
        try:
            declared_names = [
                self._runtime_name(candidate) for candidate in compatible_runtimes
            ]
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Compatibility metadata for explicit layer {identifier!r} "
                "is unusable"
            ) from error

        if runtime is None:
            raise ValueError(
                f"Explicit layer {identifier!r} requires a concrete Lambda runtime"
            )
        runtime_name = self._runtime_name(runtime)
        if runtime_name not in declared_names:
            raise ValueError(
                f"Explicit layer {identifier!r} is not compatible with Lambda "
                f"runtime {runtime_name!r}; declared compatible runtimes: "
                f"{declared_names!r}"
            )

    def _prepare_layers(self, construct, graph, layer_sources):
        if layer_sources is None:
            return

        explicit_layer_keys = set(self.custom_layers)
        required_runtimes = {}
        for method in self._iter_methods(graph):
            decorators = self._configuration_decorators(method)
            runtime = self._resolve_runtime(decorators)

            for common_layer in self.common_layers:
                identifier = getattr(
                    common_layer, 'layer_version_arn', 'common layer')
                self._validate_explicit_layer(
                    common_layer, runtime, identifier)

            requested_layers = decorators.get('layer', [])
            if not isinstance(requested_layers, list):
                requested_layers = [requested_layers]
            for layer_key in requested_layers:
                if layer_key in explicit_layer_keys:
                    self._validate_explicit_layer(
                        self.custom_layers[layer_key], runtime, layer_key)
                elif layer_key in layer_sources:
                    if runtime is None:
                        raise ValueError(
                            f"Autodiscovered layer {layer_key!r} requires a "
                            "concrete Lambda runtime"
                        )
                    if runtime.family is not lambda_.RuntimeFamily.PYTHON:
                        raise ValueError(
                            f"Autodiscovered layer {layer_key!r} requires a "
                            "Python Lambda runtime"
                        )
                    runtime_name = self._runtime_name(runtime)
                    required_runtimes.setdefault(layer_key, {})\
                        .setdefault(runtime_name, runtime)
                else:
                    self.get_custom_layer(layer_key)

        for layer_key, entry in layer_sources.items():
            if layer_key not in required_runtimes:
                continue
            layer = _lambda_python.PythonLayerVersion(
                construct,
                f"AutodiscoveredLayer:{layer_key}",
                entry=str(entry),
                compatible_runtimes=list(required_runtimes[layer_key].values()),
            )
            self.add_custom_layer(layer_key, layer)

    @staticmethod
    def _validate_source_layout(source_layout: SourceLayout):
        if not isinstance(source_layout, SourceLayout):
            raise TypeError("source_layout must be a SourceLayout")

    @staticmethod
    def _resolve_source(method: ast_helper.Method, lambda_root: Path,
                        source_layout: SourceLayout):
        handler_path = (
            Path(method.get_path_to_file()) / method.get_file()
        ).resolve()
        relative_handler = handler_path.relative_to(lambda_root)

        if source_layout is SourceLayout.ROOT:
            return lambda_root, relative_handler.as_posix()

        if len(relative_handler.parts) < 2:
            raise ValueError(
                "SERVICE source layout requires handlers to live inside "
                "a first-level service directory beneath lambda_path"
            )
        service = relative_handler.parts[0]
        return (
            lambda_root / service,
            Path(*relative_handler.parts[1:]).as_posix(),
        )

    def get_options(self, decorators:dict) -> dict:
        options = {}
        options.update({'runtime':self._resolve_runtime(decorators)})
        options.update({'memory_size': self.get_default_memory_size()})
        options.update({'timeout': self.get_default_timeout()})
        options.update({'role': self.get_default_role()})
        options.update({'vpc':self.get_default_vpc()})
        options.update({'environment':dict(self.get_common_environments())})
        options.update({'layer': list(self.get_common_layers())})
        options.update({'security_group':list(self.get_common_security_groups())})
        #Optional values that may be or not be overriden
        options.update({'description':None})
        options.update({'name':None})
        #Add defaults and let the decorators overwrite them (in case of defaults) or aggregate them (in case of common)
        for key, value in decorators.items():
            if key in ['memory_size','description','name']:
                options.update({key: value})
            elif key ==  'runtime':
                continue
            elif key == 'timeout':
                timeout = Duration.seconds(value)
                options.update({key: timeout})
            elif key == 'layer':
                if type(value) == list:
                    for v in value:
                        options[key].append(self.get_custom_layer(v))
                else:
                    options[key].append(self.get_custom_layer(value))
            elif key == 'role':
                options[key] = self.get_custom_role(value)
            elif key == 'security_group':
                if type(value) == list:
                    for v in value:
                        options[key].append(self.get_custom_security_group(v))
                else:
                    options[key].append(self.get_custom_security_group(value))
            elif key == 'environment':
                if type(value) == list:
                    for v in value:
                        selected = self.get_custom_environment(v)
                        if isinstance(selected, dict):
                            options[key].update(selected)
                        else:
                            options[key][v] = selected
                else:
                    selected = self.get_custom_environment(value)
                    if isinstance(selected, dict):
                        options[key].update(selected)
                    else:
                        options[key][value] = selected
            elif key == 'vpc':
                options[key] = self.get_custom_vpc(value)
        return options

    @staticmethod
    def _configuration_decorators(method: ast_helper.Method) -> dict:
        """Interpret ordered AST metadata using the established option semantics."""
        decorators = {}
        ignored = ast_helper.Method.ALLOWED_METHODS | {
            'grant_dynamodb', 'grant_s3', 'permission'}
        for invocation in method.get_decorator_invocations():
            if invocation.name in ignored or not invocation.args:
                continue
            value = (invocation.args[0] if len(invocation.args) == 1
                     else list(invocation.args))
            if invocation.name in decorators:
                current = decorators[invocation.name]
                if not isinstance(current, list):
                    current = [current]
                    decorators[invocation.name] = current
                current.extend(value if isinstance(value, list) else [value])
            else:
                decorators[invocation.name] = value
        return decorators

    @staticmethod
    def _auth_override(method: ast_helper.Method):
        """Return inherit, public, or an explicit logical authorizer key."""
        for invocation in method.get_decorator_invocations():
            if invocation.name == "public":
                return ("public", None)
            if invocation.name == "authorizer":
                return ("authorizer", invocation.args[0])
        return ("inherit", None)

    def _effective_authorizer_key(self, method: ast_helper.Method):
        state, key = self._auth_override(method)
        if state == "public":
            return None
        return key if state == "authorizer" else self.default_authorizer

    @staticmethod
    def _diagnostic_rows(graph: ast_helper.Resource):
        rows = []

        def visit(resource):
            for method in resource.get_methods():
                rows.append((resource.get_path(), method))
            for child in resource.get_connections():
                visit(child)

        visit(graph)
        return sorted(rows, key=lambda item: (item[0], item[1].get_method()))

    @staticmethod
    def _diagnostic_table(title, default_label, columns, rows):
        if not rows:
            return None
        lines = [title, default_label, "", "  ".join(columns)]
        lines.extend("    ".join(row) for row in rows)
        return "\n".join(lines)

    def _emit_configuration_diagnostics(self, construct, graph):
        if not isinstance(construct, Construct):
            return
        self._emit_authorization_diagnostics(construct, graph)
        self._emit_role_diagnostics(construct, graph)
        self._emit_vpc_diagnostics(construct, graph)
        self._emit_shared_role_warning(construct, graph)

    def _emit_role_diagnostics(self, construct, graph):
        if self.default_role is None:
            return
        rows = []
        for path, method in self._diagnostic_rows(graph):
            decorators = self._configuration_decorators(method)
            selected = decorators.get("role")
            if selected is None:
                continue
            effective = self.get_custom_role(selected)
            if effective is self.default_role:
                continue
            rows.append((method.get_method(), path, str(selected)))
        message = self._diagnostic_table(
            "Execution role overrides",
            "Default role: configured default",
            ("METHOD", "PATH", "EFFECTIVE"),
            rows,
        )
        if message:
            Annotations.of(construct).add_info(message)

    @staticmethod
    def _subnet_selection_name(selection):
        if selection is None:
            return "NONE"
        subnet_type = getattr(selection, "subnet_type", None)
        if subnet_type is not None:
            return getattr(subnet_type, "value", str(subnet_type))
        if getattr(selection, "subnet_group_name", None):
            return str(selection.subnet_group_name)
        if getattr(selection, "one_per_az", False):
            return "ONE_PER_AZ"
        if getattr(selection, "subnets", None):
            return "EXPLICIT_SUBNETS"
        return "DEFAULT"

    def _emit_vpc_diagnostics(self, construct, graph):
        if self.default_vpc is None:
            return
        default_vpc, default_subnets = self.default_vpc
        rows = []
        for path, method in self._diagnostic_rows(graph):
            decorators = self._configuration_decorators(method)
            selected = decorators.get("vpc")
            if selected is None:
                continue
            effective_vpc, effective_subnets = self.get_custom_vpc(selected)
            if (
                effective_vpc is default_vpc
                and effective_subnets is default_subnets
            ):
                continue
            rows.append((
                method.get_method(),
                path,
                str(selected),
                self._subnet_selection_name(effective_subnets),
            ))
        message = self._diagnostic_table(
            "VPC overrides",
            "Default VPC: configured default",
            ("METHOD", "PATH", "EFFECTIVE", "SUBNETS"),
            rows,
        )
        if message:
            Annotations.of(construct).add_info(message)

    def _emit_shared_role_warning(self, construct, graph):
        roles = {}
        for path, method in self._diagnostic_rows(graph):
            decorators = self._configuration_decorators(method)
            selected = decorators.get("role")
            if selected is None:
                continue
            grants = {
                invocation.name
                for invocation in method.get_decorator_invocations()
                if invocation.name in {"grant_dynamodb", "grant_s3"}
            }
            if not grants:
                continue
            effective = self.get_custom_role(selected)
            roles.setdefault(id(effective), (effective, set()))[1].add(path)

        if any(len(paths) > 1 for _, paths in roles.values()):
            Annotations.of(construct).add_warning_v2(
                "LAD_ROLE_SHARED_PERMISSIONS",
                "LAD_ROLE_SHARED_PERMISSIONS: an explicit execution role with "
                "derived permissions is shared by multiple Lambda handlers.",
            )

    @staticmethod
    def _implements_interface(authorizer, interface) -> bool:
        return interface in getattr(authorizer, "__jsii_ifaces__", ())

    def _resolve_authorizer(self, method: ast_helper.Method, family: str):
        key = self._effective_authorizer_key(method)
        if key is None:
            return None
        try:
            authorizer = self.authorizers[key]
        except KeyError:
            raise KeyError(f"Authorizer key {key!r} is not registered") from None
        interface = (
            apigateway.IAuthorizer
            if family == "REST"
            else apigateway2.IHttpRouteAuthorizer
        )
        if not self._implements_interface(authorizer, interface):
            raise TypeError(
                f"Authorizer key {key!r} is not compatible with {family} APIs"
            )
        return authorizer

    def _rest_method_options(self, method: ast_helper.Method):
        authorizer = self._resolve_authorizer(method, "REST")
        if authorizer is None:
            return {
                "authorizer": None,
                "authorization_type": apigateway.AuthorizationType.NONE,
            }
        return {
            "authorizer": authorizer,
            "authorization_type": authorizer.authorization_type,
        }

    def _add_rest_method(self, resource, method, integration):
        options = self._rest_method_options(method)
        parameters = inspect.signature(resource.add_method).parameters.values()
        accepts_options = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            or parameter.name == "authorization_type"
            for parameter in parameters
        )
        if accepts_options:
            return resource.add_method(method.get_method(), integration, **options)
        # Preserve compatibility with narrow direct-builder test doubles and
        # existing callers that expose only the historical two-argument shape.
        return resource.add_method(method.get_method(), integration)

    def _http_route_authorizer(self, method: ast_helper.Method):
        authorizer = self._resolve_authorizer(method, "HTTP")
        return authorizer if authorizer is not None else apigateway2.HttpNoneAuthorizer()

    def _emit_authorization_diagnostics(self, construct, graph):
        if not isinstance(construct, Construct):
            return
        if self.default_authorizer is None:
            Annotations.of(construct).add_warning_v2(
                "LAD_AUTH_PUBLIC_DEFAULT",
                "LAD_AUTH_PUBLIC_DEFAULT: Routes without explicit authorization are public because no "
                "default authorizer is configured.",
            )

        deviations = []

        def visit(resource):
            for method in resource.get_methods():
                state, key = self._auth_override(method)
                if self.default_authorizer is None:
                    if state == "authorizer":
                        deviations.append((resource.get_path(), method.get_method(), key))
                elif state == "public":
                    deviations.append((resource.get_path(), method.get_method(), "PUBLIC"))
                elif state == "authorizer" and key != self.default_authorizer:
                    deviations.append((resource.get_path(), method.get_method(), key))
            for child in resource.get_connections():
                visit(child)

        visit(graph)
        if not deviations:
            return
        deviations.sort(key=lambda item: (item[0], item[1]))
        if self.default_authorizer is None:
            default_label = "Default authorizer: PUBLIC"
        else:
            default_label = f"Default authorizer: {self.default_authorizer}"
        rows = [
            (method, path, value)
            for path, method, value in deviations
        ]
        message = self._diagnostic_table(
            "Authorization overrides",
            default_label,
            ("METHOD", "PATH", "EFFECTIVE"),
            rows,
        )
        if message:
            Annotations.of(construct).add_info(message)

    @staticmethod
    def _physical_resource_id(resource_type: str, physical_name: str) -> str:
        """Create a stable, collision-safe construct ID for an imported resource."""
        digest = hashlib.sha256(physical_name.encode("utf-8")).hexdigest()[:12]
        return f"Permission{resource_type}:{digest}"

    @staticmethod
    def _find_imported_resource(construct, construct_id, resource_type,
                                name_attribute, physical_name):
        """Find a compatible physical import already owned by this scope."""
        resource = construct.node.try_find_child(construct_id)
        if resource is None:
            return None
        if (
            not isinstance(resource, resource_type)
            or getattr(resource, name_attribute, None) != physical_name
        ):
            raise RuntimeError(
                f"Construct {construct_id!r} already exists but is not the "
                f"expected imported resource {physical_name!r}"
            )
        return resource

    @staticmethod
    def _grant_arguments(invocation, physical_field: str):
        """Read a grant invocation whose public shape was validated by the AST."""
        if invocation.args:
            if len(invocation.args) != 2 or invocation.kwargs:
                raise ValueError(f"Malformed {invocation.name} invocation")
            resource_key, access = invocation.args
            if access not in ("read", "write"):
                raise ValueError(f"Malformed {invocation.name} invocation")
            return resource_key, None, access

        arguments = dict(invocation.kwargs)
        resource_key = arguments.get("resource_key")
        physical_name = arguments.get(physical_field)
        access = arguments.get("access")
        if (
            access not in ("read", "write")
            or (resource_key is None) == (physical_name is None)
        ):
            raise ValueError(f"Malformed {invocation.name} invocation")
        return resource_key, physical_name, access

    def _resolve_dynamodb_table(self, construct, resource_key, table_name):
        if resource_key is not None:
            try:
                return self.dynamodb_tables[resource_key]
            except KeyError:
                raise KeyError(
                    f"DynamoDB table resource key {resource_key!r} is not registered"
                ) from None

        cache_key = (construct, table_name)
        if cache_key not in self._physical_dynamodb_tables:
            construct_id = self._physical_resource_id(
                "DynamoDBTable", table_name)
            table = self._find_imported_resource(
                construct,
                construct_id,
                dynamodb.TableBase,
                "table_name",
                table_name,
            )
            if table is None:
                table = dynamodb.Table.from_table_attributes(
                    construct,
                    construct_id,
                    table_name=table_name,
                    grant_index_permissions=True,
                )
            self._physical_dynamodb_tables[cache_key] = table
        return self._physical_dynamodb_tables[cache_key]

    def _resolve_s3_bucket(self, construct, resource_key, bucket_name):
        if resource_key is not None:
            try:
                return self.s3_buckets[resource_key]
            except KeyError:
                raise KeyError(
                    f"S3 bucket resource key {resource_key!r} is not registered"
                ) from None

        cache_key = (construct, bucket_name)
        if cache_key not in self._physical_s3_buckets:
            construct_id = self._physical_resource_id("S3Bucket", bucket_name)
            bucket = self._find_imported_resource(
                construct,
                construct_id,
                s3.BucketBase,
                "bucket_name",
                bucket_name,
            )
            if bucket is None:
                bucket = s3.Bucket.from_bucket_name(
                    construct, construct_id, bucket_name)
            self._physical_s3_buckets[cache_key] = bucket
        return self._physical_s3_buckets[cache_key]

    @staticmethod
    def _ensure_permission_applied(applied, permission_kind):
        if not applied:
            raise RuntimeError(
                f"{permission_kind} permission could not be applied because "
                "the selected execution role cannot accept policy mutations"
            )

    @classmethod
    def _ensure_role_policy_applied(cls, function, statement,
                                    permission_kind):
        result = function.role.add_to_principal_policy(statement)
        cls._ensure_permission_applied(
            result.statement_added and any(
                isinstance(child, iam.Policy)
                for child in function.role.node.children
            ),
            permission_kind,
        )

    @classmethod
    def _ensure_grant_applied(cls, function, grant, permission_kind):
        # Narrow test doubles used by existing callers may not model CDK Grant.
        if grant is None:
            return
        cls._ensure_permission_applied(
            grant.success and any(
                isinstance(child, iam.Policy)
                for child in function.role.node.children
            ),
            permission_kind,
        )

    def _apply_dynamodb_grant(self, construct, function, invocation):
        resource_key, table_name, access = self._grant_arguments(
            invocation, "table_name"
        )
        table = self._resolve_dynamodb_table(construct, resource_key, table_name)
        if access == "read":
            grant = table.grant_read_data(function)
        else:
            grant = table.grant_read_write_data(function)
        self._ensure_grant_applied(function, grant, invocation.name)

    def _apply_s3_grant(self, construct, function, invocation):
        resource_key, bucket_name, access = self._grant_arguments(
            invocation, "bucket_name"
        )
        bucket = self._resolve_s3_bucket(construct, resource_key, bucket_name)
        if access == "read":
            grant = bucket.grant_read(function)
        else:
            grant = bucket.grant_read_write(function)
        self._ensure_grant_applied(function, grant, invocation.name)

    @staticmethod
    def _apply_generic_permission(function, invocation):
        if invocation.args:
            raise ValueError("Malformed permission invocation")
        arguments = dict(invocation.kwargs)
        try:
            actions = list(arguments["actions"])
            resources = list(arguments["resources"])
        except (KeyError, TypeError):
            raise ValueError("Malformed permission invocation") from None
        statement = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=actions,
            resources=resources,
        )
        ResourceBuilder._ensure_role_policy_applied(
            function, statement, invocation.name)

    def _apply_permissions(self, construct, function, method):
        """Apply each ordered permission invocation to a created function once."""
        for invocation in method.get_decorator_invocations():
            if invocation.name == "grant_dynamodb":
                self._apply_dynamodb_grant(construct, function, invocation)
            elif invocation.name == "grant_s3":
                self._apply_s3_grant(construct, function, invocation)
            elif invocation.name == "permission":
                self._apply_generic_permission(function, invocation)

    def build_lambda_function(self, construct, method: ast_helper.Method,
                              lambda_root: Optional[Path] = None,
                              source_layout: SourceLayout = SourceLayout.ROOT):
        # Create Lambda function with aggregated metadata from all decorators

        logical_id = method.get_logical_id()
        handler = method.get_handler()
        if lambda_root is None:
            file = method.get_file()
            entry_path = method.get_path_to_file()
        else:
            entry_path, file = self._resolve_source(
                method, lambda_root, source_layout)
            entry_path = str(entry_path)
        options = self.get_options(self._configuration_decorators(method))
        vpc_options = options['vpc']
        vpc = vpc_options[0] if vpc_options is not None else None
        vpc_subnets = vpc_options[1] if vpc_options is not None else None
        lambda_function = _lambda_python.PythonFunction(
            construct, logical_id,
            function_name = options['name'] if options['name'] else logical_id,
            description = options['description'],
            entry = entry_path,
            index = file,
            handler = handler,
            runtime = options['runtime'],
            timeout = options['timeout'],
            layers = options['layer'],
            memory_size=options['memory_size'],
            security_groups= options['security_group'],
            vpc=vpc,
            vpc_subnets=vpc_subnets,
            allow_public_subnet=False,
            environment= options['environment'],
            role= options['role'] 
        )
        self._apply_permissions(construct, lambda_function, method)
        return lambda_function

    def _build_discovered_lambda(self, construct, method, lambda_root,
                                 source_layout):
        if lambda_root is None:
            return self.build_lambda_function(construct, method)
        return self.build_lambda_function(
            construct, method, lambda_root, source_layout)

    @staticmethod
    def _validate_single_route_handlers(graph: ast_helper.Resource) -> None:
        seen = {}

        def visit(resource):
            for method in resource.get_methods():
                handler = (
                    method.get_path_to_file(),
                    method.get_file(),
                    method.get_handler(),
                    method.get_method(),
                )
                if handler in seen:
                    raise ValueError(
                        f"Handler {handler[2]!r} has multiple routes for "
                        f"HTTP method {handler[3]!r}: "
                        f"{seen[handler]!r} and {resource.get_path()!r}"
                    )
                seen[handler] = resource.get_path()
            for child in resource.get_connections():
                visit(child)

        visit(graph)

    def build_from_graph(self, construct, graph: ast_helper.Resource,
                         api_resource: apigateway.IResource,
                         lambda_root: Optional[Path] = None,
                         source_layout: SourceLayout = SourceLayout.ROOT):

        if isinstance(construct, Construct):
            self._validate_single_route_handlers(graph)

        path = graph.get_path()
        level = path.count('/')
        if level <= 1 and len(path) <= 1: #root '/'
            new_resource = api_resource
            for method in graph.get_methods():
                lbda = self._build_discovered_lambda(
                    construct, method, lambda_root, source_layout)
                self._add_rest_method(
                    new_resource, method, apigateway.LambdaIntegration(lbda))
        else:
            #We can get a skip from /something to /something/one/two/method, so resources with no methods "one" and "two" should be created
            new_api_resources = path[len(api_resource.path):].lstrip('/').split('/')
            if len(new_api_resources) > 1: #Resources with no methods associated need to be created. No possible conflict because graph is sorted.
                for res in new_api_resources[:-1]: # Exclude last resource that will be created w/lambda
                    api_resource = api_resource.add_resource(res)
            resource_name = path[path.rindex('/')+1:] #Now we can create the resource associated with the node even if 
            new_resource = api_resource.add_resource(resource_name)
            for method in graph.get_methods():
                lbda = self._build_discovered_lambda(
                    construct, method, lambda_root, source_layout)
                self._add_rest_method(
                    new_resource, method, apigateway.LambdaIntegration(lbda))

        for node in graph.get_connections():
            self.build_from_graph(
                construct, node, new_resource, lambda_root, source_layout)
        
    def build_http_from_graph(self, construct, graph: ast_helper.Resource,
                              http_api: apigateway2.HttpApi,
                              lambda_root: Optional[Path] = None,
                              source_layout: SourceLayout = SourceLayout.ROOT):
        if isinstance(construct, Construct):
            self._validate_single_route_handlers(graph)

        method_mapping = {
            'GET': apigateway2.HttpMethod.GET,
            'POST': apigateway2.HttpMethod.POST,
            'PUT': apigateway2.HttpMethod.PUT,
            'DELETE': apigateway2.HttpMethod.DELETE,
            'PATCH': apigateway2.HttpMethod.PATCH,
            'OPTIONS': apigateway2.HttpMethod.OPTIONS,
            'HEAD': apigateway2.HttpMethod.HEAD,
        }
        path = graph.get_path()
        level = path.count('/')
        if level <= 1 and len(path) <= 1: #root '/'
            # new_resource = api_resource
            for method in graph.get_methods():
                lbda = self._build_discovered_lambda(
                    construct, method, lambda_root, source_layout)
                api_lbda_integration = integrations.HttpLambdaIntegration(f"{method.get_logical_id()}ApiLambdaIntegration",lbda)
                http_api.add_routes(
                    path='/',
                    methods=[method_mapping[method.get_method()]],
                    integration=api_lbda_integration,
                    authorizer=self._http_route_authorizer(method),
                )
        else:
            for method in graph.get_methods():
                lbda = self._build_discovered_lambda(
                    construct, method, lambda_root, source_layout)
                api_lbda_integration = integrations.HttpLambdaIntegration(f"{method.get_logical_id()}ApiLambdaIntegration",lbda)
                http_api.add_routes(
                    path=path,
                    methods=[method_mapping[method.get_method()]],
                    integration=api_lbda_integration,
                    authorizer=self._http_route_authorizer(method),
                )

        for node in graph.get_connections():
            self.build_http_from_graph(
                construct, node, http_api, lambda_root, source_layout)
