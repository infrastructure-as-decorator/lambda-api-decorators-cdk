# Lambda API Decorators CDK — Agent Instructions

## Project purpose

This repository contains **Lambda API Decorators CDK**, the AWS CDK integration for the Lambda API Decorators project.

The project goal is:

> Define AWS Lambda APIs with Python decorators and automatically generate the infrastructure with AWS CDK.

GitHub organization:

`infrastructure-as-decorator`

Package:

`lambda-api-decorators-cdk`

Python module:

`lambda_api_decorators_cdk`

Project documentation:

`https://infrastructure-as-decorator.github.io/`

## Design principles

Follow these principles when changing the project:

> Simple by default, CDK-native when needed.

> Convention when convenient, configuration when needed.

> Explicit configuration always wins over convention.

Prefer small, composable APIs over large constructors or abstractions.

Do not add configuration knobs before the corresponding feature has been designed.

Do not introduce compatibility shims or aliases unless explicitly requested.

## Public architecture

The intended architecture is:

```text
LambdaApi
    ↓
LambdaApiConfig
    ↓
ResourceBuilder
    ↓
AWS CDK
```

`LambdaApi` is the recommended high-level CDK construct.

`LambdaApiConfig` contains reusable Lambda/API build configuration and creates isolated `ResourceBuilder` snapshots.

`ResourceBuilder` remains the lower-level engine and a supported public API.

Do not duplicate `ResourceBuilder` option-resolution or precedence logic in higher-level classes.

## Configuration lifecycle

The high-level lifecycle is:

```text
configure
    ↓
construct
    ↓
build
```

Configuration intended to affect generated Lambda resources must exist before `LambdaApi` construction.

Do not expose post-build configuration APIs that imply already-created resources can be retroactively changed.

## Mutable state

Avoid mutable default arguments.

Reusable configuration must not share mutable container state across builds.

Shallow-copy configuration containers when isolation is required.

Do not deep-copy AWS CDK constructs.

CDK objects supplied by callers should normally preserve object identity.

## AWS CDK usage

Prefer AWS CDK interfaces in public type annotations when the actual implementation supports them.

Do not claim support for an interface unless the underlying implementation can actually operate on all supported instances.

Be careful with JSII Python proxy identity.

Two accesses to the same CDK property may produce different Python proxy objects.

When appropriate, compare stable CDK properties instead of Python proxy identity.

## REST and HTTP APIs

REST is the semantic default for `LambdaApi`.

Standard created and imported REST APIs are supported by the current high-level API.

Concrete `apigatewayv2.HttpApi` instances are supported.

Do not claim general imported `IHttpApi` support unless route construction is explicitly redesigned to support it.

## Backward compatibility

Existing `ResourceBuilder` behavior is compatibility-sensitive.

Before modifying `ResourceBuilder`, determine whether the change affects existing direct callers.

Do not silently change existing low-level behavior to simplify a new high-level API.

When a new behavior conflicts with legacy behavior, prefer an explicit compatibility boundary.

## Scope discipline

Implement only the feature requested by the current task.

Do not opportunistically implement future roadmap items.

In particular, do not mix unrelated changes involving:

* source packaging;
* layer discovery;
* permissions;
* resource registries;
* Lambda identity or caching;
* logical-ID redesign;
* decorator syntax;
* supported HTTP methods;
* API Gateway security features.

A task may explicitly authorize one or more of these areas.

## Testing workflow

Tests are part of the public contract.

Do not weaken, delete, skip, or mark tests `xfail` simply to make a change pass.

When a task starts from a red test baseline, preserve the intended assertions while implementing the feature.

Equivalent parametrization is acceptable, but do not silently remove behavioral coverage.

Use real AWS CDK constructs when JSII runtime behavior, construct ownership, or type inference matters.

Mock or monkeypatch narrow boundaries when necessary to avoid Docker or Lambda bundling.

## Required verification

After code changes, run at minimum:

```bash
pytest -q
python -m compileall -q src tests
git diff --check
git status --short
```

When test inventory matters, also run:

```bash
pytest --collect-only -q
```

The existing test suite must remain green unless the current task explicitly establishes a deliberate red baseline.

## Docker and bundling

Unit tests should not require Docker unless the task explicitly concerns bundling behavior that cannot otherwise be tested.

Prefer testing packaging-path calculation and construct orchestration independently from Docker-based bundling.

## Git workflow

Do not push changes to a remote repository unless explicitly requested.

Do not create or update pull requests unless explicitly requested.

Do not create unrelated branches.

Do not amend or rewrite existing commits unless explicitly requested.

If the task explicitly says PLAN ONLY, AUDIT ONLY, REVIEW ONLY, or TESTS ONLY, respect that boundary exactly.

## Planning and audits

For architectural changes, inspect the existing implementation before proposing a design.

Identify:

* current behavior;
* public compatibility constraints;
* affected files;
* tests that protect current behavior;
* proposed API;
* migration or compatibility boundary;
* deferred work.

Do not implement during a PLAN ONLY or AUDIT ONLY task.

## Documentation

The repository README should explain this package clearly and link prominently to the complete project documentation.

Central documentation is the source for complete cross-package architecture and guides.

Avoid duplicating large documentation sections across repositories.

## General engineering guidance

Prefer straightforward code over clever abstractions.

Avoid speculative generalization.

Preserve type clarity.

Keep public APIs intentionally small.

When an implementation detail is not useful to callers, keep it private.

If repository behavior contradicts an assumption in the task, report the conflict rather than silently redesigning unrelated code.
