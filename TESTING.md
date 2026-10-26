# Testing evidence

Executed 2026-10-26 on Windows (`Windows-10-10.0.26300-SP0` as reported by Python), CPython 3.11.15. Standard library only. No network, credentials, paid API, external server or production transcript was used. Windows version naming here is Python's platform string, not a product-edition claim.

## Test-first evidence

The 23 initial subprocess test methods were written before `rpc_transcript_check.py`. An initial discovery run failed because the executable was absent. A focused RED command, `python -m unittest discover -s tests -k test_out_of_order_and_notification`, then produced exactly one assertion failure: observed process exit 2 versus expected 0, with the interpreter reporting the missing CLI. This establishes the missing-implementation failure, not a protocol bug in an existing program. After implementing the CLI, `python -m unittest discover -s tests -v` passed all 23 methods. Four additional boundary/correlation test methods bring the final suite to 27.

## Fresh source-only verification

A temporary directory received a copy of source, tests, examples and documentation, excluding `.git`, `.venv`, `__pycache__` and `*.pyc`. From that copy:

```sh
python -I -S -m unittest discover -s tests -v
```

Result: **27 tests, OK**, 7.812 seconds in the recorded fresh-copy run. The launching interpreter identified itself as CPython 3.11.15. `-I -S` disables environment/user-site injection and site initialization for this direct verification command. Tests invoke real CLI child processes through the same interpreter. This is not a claim that every possible Python installation was tested.

Every `checks.json` entry was then run as `[python, -I, -S, *args]` from the same fresh copy:

| Check | Expected exit | Observed exit | stderr |
| --- | --- | --- | --- |
| clean JSON | 0 | 0 | empty |
| clean text | 0 | 0 | empty |
| correlation/error findings | 1 | 1 | empty |
| invalid message envelope | 1 | 1 | empty |
| invalid capture outer record | 2 | 2 | empty |
| help | 0 | 0 | empty |

The source-only copy used no installed project or editable package. File inspection found no CR bytes in owned source, examples or documents, including the preserved `.gitattributes`; all text is UTF-8 and was written with explicit LF handling.

## Covered behaviors

- Out-of-order responses, opposite-direction calls, type-sensitive IDs, reuse after completion, duplicate pending IDs retaining the original line, repeated/orphan responses and pending requests.
- Notifications and unexpected responses to notifications; success/error responses, orphan errors, invalid responses retaining pending state, explicit error outcome findings.
- Invalid/null/boolean/fractional IDs, Unicode/empty string IDs, integer negative zero and 5,000-digit integer IDs, finite parameter number `1e9999` without floating-point overflow.
- Structured parameters, extension members, missing versions/methods/results/error members, result/error exclusivity and integer error-code/string-message requirements.
- Exact outer shape, non-object messages, batches, bad directions, duplicate keys including nested objects, NaN/Infinity, empty input, blank lines, BOM, invalid UTF-8, invalid JSON and parser recursion rejection.
- CRLF and optional final newline, exact 1 MiB line and 16 MiB total accepted boundaries, next-byte rejection, exact 10,000 accepted records, over-limit records and oversized lines.
- Stdin, help, JSON/text output privacy, safe bad-argument and unreadable-path diagnostics, incomplete-prefix/error precedence.

Each unittest method can contain multiple subcases and CLI launches; 27 is the method count, not a branch coverage percentage. Subprocesses use timeouts in the test harness.

## Limits of this evidence

This agent exercised Windows CPython 3.11.15 only. Ubuntu/Windows hosted CI is a separate parent-batch gate and has not yet been represented as passed in this document. No live MCP/JSON-RPC server, protocol handshake, SDK compatibility, transport capture/exporter, real operational log or real user workflow was tested. No performance benchmark, adoption measurement, fuzzing campaign or security certification is claimed. The input byte caps do not implement a wall-clock deadline for a live stdin producer.
