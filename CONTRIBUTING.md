# Contributing

Contributions are welcome — especially new attack patterns and stack adapters.

## What makes a good contribution

Every check in this skill answers four questions. A new check should too:

1. **How the attacker exploits it** — the concrete input or request sequence.
2. **Where to look in the code** — the pattern, so it can be grepped.
3. **How to reproduce** — steps that prove it, not a theory.
4. **Fix** — before/after code.

A check without a reproduction step is a guess. Please don't add those.

## Adding a category

Categories live in `hebe-security-scan/references/NN-name.md` and are listed in the
table in `references/category-catalog.md`. Keep each reference self-contained: it loads on its own, without
the others in context.

## Adding a stack adapter

`references/stack-adapters.md` maps a technology to its code signatures — how an IDOR,
a missing auth check or a leaked secret actually *looks* in that stack. Short and
concrete beats exhaustive.

## Scope

This is a security skill. Please don't add style rules, formatting preferences or
generic best practices — noise buries the real finding.

## Licence

By contributing, you agree your contribution is licensed under the MIT License.
