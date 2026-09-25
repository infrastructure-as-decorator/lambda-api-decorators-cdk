# CDK behavior

## Construction and precedence

`LambdaApi` selects REST by default, infers the API family from a supplied concrete REST or HTTP API, and rejects a conflicting explicit `api_type`. Configuration must be complete before construction; `LambdaApiConfig` creates an isolated `ResourceBuilder` snapshot and does not deep-copy CDK constructs.

Explicit configuration wins over convention. Runtime, role, environment, layer, VPC, security group, table, bucket, and authorizer registries resolve named decorator values. A registry is a lookup mechanism, not an authorization grant.

## Routes and authorization

The runtime contract permits one HTTP route per callable. CDK discovers those declarations and builds the matching REST or HTTP resources. `public` suppresses the effective authorizer for that callable; otherwise a callable override, the configured default authorizer, or no authorizer is resolved according to the current builder behavior.

## Grants

`grant_dynamodb` and `grant_s3` resolve either a registered logical resource or a physical resource name. `read` applies read access and `write` applies cumulative write access as implemented by the builder. Generic `permission` statements are applied separately. Missing registry entries, invalid authorizers, conflicting defaults, and unsupported API/resource combinations produce errors or CDK diagnostics rather than silently changing the runtime metadata.
