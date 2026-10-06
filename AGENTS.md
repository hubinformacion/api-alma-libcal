# Repository Guidelines

## Project Structure & Module Organization

The current workspace contains no application source, tests, assets, or dependency manifests. The `.agents/`, `.codex/`, `.aws/`, and `.git/` directories are environment metadata; do not use them for application code.

When introducing the initial implementation, establish a clear layout, such as `src/` for source code, `tests/` for automated tests, and `docs/` for integration notes. Document the actual layout here once it exists. Keep integration-specific modules separate from shared configuration and utilities.

## Build, Test, and Development Commands

No build, test, lint, or local development commands are currently configured. Do not assume that commands such as `npm test` or `make build` work.

When adding tooling, provide reproducible setup instructions and commands in a `README.md`. Document required runtime versions, dependency installation, local execution, and verification. Prefer project-defined scripts over undocumented manual steps.

## Coding Style & Naming Conventions

No language, indentation standard, formatter, or linter has been established. Select consistent conventions with the initial implementation and configure the relevant tools. Use descriptive names, keep modules focused, and follow existing conventions as code is added. Avoid unrelated formatting changes.

## Testing Guidelines

No testing framework or coverage threshold is configured. Add automated tests for new behavior and bug fixes. Name tests after the behavior they verify and document their location and execution command. Use fixtures or mocks for external integrations; keep credentials and live service dependencies out of routine tests.

## Commit & Pull Request Guidelines

Git history is unavailable in this workspace, so existing commit conventions cannot be verified. Use short, imperative commit subjects, such as `Add configuration validation`.

Pull requests should describe the change, link relevant issues, and report verification commands and results. Explain configuration changes and any checks that could not be run.

## Security & Agent Instructions

Never commit secrets or populated environment files. Provide placeholder configuration examples when needed.

Use Context7 for current library, framework, SDK, API, CLI, or cloud-service documentation. Resolve the library ID first, then query documentation for each relevant concept. General programming, business-logic debugging, and code review do not require Context7.
