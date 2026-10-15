# Python Code Style

These rules apply to every Python file in Fuzzy Technologies engineering
repositories, including production code, tests, scripts, and embedded Python
fixtures.

## Language

- Python code, identifiers, docstrings, comments, assertion messages, and
  embedded Python source are English-only.
- Localized website content is outside this Python contract.
- Comments explain a reason, invariant, limitation, or architectural decision;
  they do not narrate obvious statements.

## Naming

Project-owned identifiers use:

- functions and methods: `PascalCase`, including `Main()`;
- classes, protocols, and enums: `PascalCase`;
- variables, parameters, and fields: `snake_case`; a leading underscore is
  allowed for internal implementation details;
- constants: `UPPER_SNAKE_CASE`, with underscores between words;
- test files: `test_*.py`;
- test functions: the required `test_` prefix followed by `PascalCase`.

Preserve names imposed by Python, frameworks, SDKs, schemas, protocols, and
third-party APIs. This includes dunder methods, pytest fixtures and hooks,
callbacks, CLI options, configuration keys, and compatibility contracts.

## Docstrings

- Every production and test module, class, function, and method has a concise
  English docstring.
- A docstring is the first statement in its scope.
- Leave one blank line after a function or method docstring before the
  implementation.

## Vertical Spacing

Use one blank line to expose transitions between logical phases inside a
function or method.

Insert one blank line:

- before a new `if`, `for`, `while`, `try`, `with`, or `match` statement when
  it follows completed work in the same block;
- before an `await` statement, or an assignment whose value is awaited, when it
  starts the next asynchronous operation;
- before `return`, `raise`, or `yield` when it follows completed work in the
  same block;
- after a completed nested or multi-line control-flow block before the next
  independent statement;
- before `elif`, `else`, `except`, and `finally`;
- between class methods;
- before `if __name__ == "__main__":`.

Do not insert a blank line immediately after a `def`, `class`, `try`, `if`,
`elif`, `else`, `except`, `finally`, `for`, `while`, `with`, `match`, or `case`
header. An `await`, `return`, or `raise` that is the first statement inside such
a block remains directly below its header.

Keep tightly related assignments and calls together. The rule separates
logical phases rather than every physical statement.

Use two blank lines between module-level functions and classes.

## Formatting and Linting

`ruff format` is not the canonical formatter and must not be run as an
automatic project-wide rewrite or CI gate. It removes intentional vertical
spacing required by this contract.

Use Ruff for lint and static checks:

```bash
python -m ruff check .
```

Formatting-only changes must not rename protected interfaces, modify behavior,
or collapse logical blocks.

## Validation

Before reporting a Python change ready for review, run the repository's locked
environment and standard gates. A typical project includes:

```bash
python -m compileall -q src tests
python -m ruff check .
python -m mypy
python -m pytest
```

Use the repository wrapper when one exists so IDE, local development, and CI
share the same SDK and dependency graph.

Infrastructure, cleanup, rollback, authorization, resource-management, and
error branches require deterministic tests without calls to real production
infrastructure.

## Assertions and Tests

- Assertion messages identify the violated invariant and likely cause.
- Use branch coverage for control-flow-heavy code.
- Do not hide flaky tests with automatic retries.
- Tests must not depend on execution order or shared mutable state unless they
  are explicitly marked and isolated as serial.

## Git

Commit messages are concise, English, and imperative, for example:

```text
Add regional VPN configurations
Fix configuration migration error
Update deployment validation
```

## Final Principle

Code must be consistent, readable, reproducible, and verifiable.

- explicit behavior over magic;
- evidence over assumptions;
- tests over manual confidence;
- stability over cosmetic refactoring.
