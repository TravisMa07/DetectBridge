# Compiler compatibility matrix

Scope: P09 legacy semantic mode and P10 source-mapped mode. All executable cases
are original synthetic material; no broad SigmaHQ corpus coverage rate is claimed.
See [P10 design](p10-design.md) for provenance, quality precedence and limitations.

| Feature | Behavior | Executable evidence |
| --- | --- | --- |
| Named nonempty map selections | Supported | `tools/tests/test_detection.py`, legacy semantic cases |
| AND, OR, NOT, parentheses | Supported; missing positive=false, NOT may match absence | legacy semantic cases; P10 mapping cases |
| String/integer scalar rule values | Supported; signed 64-bit exact integers, no coercion | compiler precision tests and Java predicate tests |
| Rule value lists | OR; empty list rejected | compiler rejection tests; legacy semantic cases |
| Event arrays | Predicate any-element internally; only schema-permitted event fields accepted | `EvaluatorTest.missingNegationTypesAndArrays` |
| Wildcards and escapes | Code-point glob; Java simple case fold, no Unicode normalization | legacy semantic cases; `EvaluatorTest.globSemanticsIndependent` |
| contains, startswith, endswith | One modifier, string fields only | legacy semantic cases; compiler rejection tests |
| Boolean literals, floats, null literals | Rejected, including unused selections | `CompilerTests.test_unsupported_even_when_unused` |
| Regex, quantifiers, chained/unknown modifiers | Rejected explicitly | compiler rejection tests; candidate analysis tests |
| Unknown attributes, selections and fields | Rejected explicitly | compiler structure/rejection tests |
| Null/invalid ECS fields or broken evidence | Input rejection, never nonmatch | Java normalized validation and P10 invalid-before-inapplicable case |
| Image, CommandLine, ProcessId, User | Fixed typed scalar aliases; sparse source support explicit | `tools/tests/test_mapping.py`; `MappingProfilesTest` |
| Conditional absent optional field | Positive=false; NOT may match | P10 conditional-missing cases |
| Required alias unsupported by source | Rule/source configuration_blocked, even within OR | P10 unsupported/OR cases |
| Known mismatching logsource | Inapplicable before capability/quality | P10 source-before-capability case |
| Unknown source / insufficient event quality | Configuration-blocked / quality-skipped, distinct | P10 mapping cases; legacy fixture cases |
| Optimized source selection | P10b loader-built source index; exhaustive reference retained | `SelectionTest`; mapped YAML-to-Java equivalence cases |
| Bounded offline Windows/Linux parsing | P11/P12 implemented and owner-accepted within selected scope; production wiring remains P13b | [Windows](windows-adapters.md), [Linux acceptance](p12-acceptance.md) |
| Compact mapped results | Same six counts and ordered matches; at most three immutable rule-membership groups | `SelectionTest`, independent YAML-to-Java cases via `--compact` |
| Attributed integration outputs | Separate 1.0.0 tagged/detection/diagnostic wrappers; unchanged P03 events and legacy results | `IntegrationOutputsTest`, actual Windows/AuthReplay/AuditReplay integrated consumer tests |

Legacy independent cases and rationales:
[semantic-cases.json](../contracts/detection/v1/fixtures/semantic-cases.json).
New source/capability cases and rationales:
[compatibility-cases.json](../contracts/detection/v2/fixtures/compatibility-cases.json).
The full gate is run by `uv run --locked python tools/dev.py java`.
Independent owner review is pending; passing executable cases does not replace it.
