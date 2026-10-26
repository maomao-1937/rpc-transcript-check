# rpc-transcript-check

[![tests](https://github.com/maomao-1937/rpc-transcript-check/actions/workflows/tests.yml/badge.svg)](https://github.com/maomao-1937/rpc-transcript-check/actions/workflows/tests.yml)

Offline, privacy-conscious correlation checks for a bounded two-way JSON-RPC 2.0 transcript. Python 3.11+, standard library only. No installation, capture, process launching, network or server connection.

A successful JSON parse does not prove that a response belongs to a request. This tool accepts explicitly labeled directions, tracks requests independently for each sender, and reports duplicate pending IDs, orphan responses, unfinished requests and remote error outcomes. Results contain fixed codes, counters and line positions; capture paths, IDs, methods and message bodies are never included.

## Quickstart

From this repository directory, using an existing Python 3.11+ interpreter:

```sh
python rpc_transcript_check.py examples/clean.jsonl
python rpc_transcript_check.py examples/findings.jsonl --format text
python rpc_transcript_check.py examples/invalid-capture.jsonl
python -m unittest discover -s tests -v
```

The examples exit 0, 1 and 2 respectively. Use `-` as the capture argument to read binary stdin. PowerShell may use `py -3.11` in place of `python`; use a UTF-8 file directly to avoid shell pipe encoding changes. JSON is the default output. Argument errors also use safe JSON, even when a bad `--format` value is supplied.

## Input contract

Each nonblank UTF-8 JSONL line must contain **exactly** these two members:

```json
{"direction":"client_to_server","message":{"jsonrpc":"2.0","method":"example","id":1,"params":{}}}
{"direction":"server_to_client","message":{"jsonrpc":"2.0","id":1,"result":{}}}
```

- Directions: `client_to_server` or `server_to_client`. `message` must be an object. Arrays/batches are unsupported capture shapes.
- Duplicate keys at any nesting level, NaN/Infinity, UTF-8 BOM, malformed JSON, invalid UTF-8 and blank lines invalidate the capture. CRLF works; the last line need not end in LF. An empty file is invalid.
- Messages require the string `jsonrpc: "2.0"`. Requests/notifications require a string method and, if present, object/array params. A notification has no `id`. A request must have a supported ID.
- Supported IDs are non-null JSON strings or integers. Boolean, null and all fractional/exponent numeric spellings, including `1.0` and `1e0`, are invalid message envelopes. Integer `1` and string `"1"` are different. Integer `-0` equals integer `0`; empty string IDs work. Large integer IDs are handled without converting them to machine integers.
- A response requires a supported ID and exactly one of `result` or `error`, with no method/params. Any JSON result is allowed. An error is an object with integer `code` and string `message`; optional data and extension members are accepted. Request envelopes cannot carry result/error. Other extension members are accepted without semantic checks.
- Responses resolve the opposite sender's pending request. Out-of-order responses and the same ID pending in opposite directions work. A repeated same-origin pending ID is a finding and retains the original request. Reuse after completion is allowed. Notifications create no response obligation.

Numeric tokens are retained lexically, so finite JSON values such as `1e9999` do not overflow a floating-point conversion. Message values are never executed or printed. Deeply nested input that exceeds Python's JSON parser recursion capacity is rejected as `INVALID_JSON`.

## Reports and exit codes

| Exit | Meaning |
| --- | --- |
| 0 | Complete capture, no findings within this profile |
| 1 | Complete capture with message/correlation/error-outcome findings |
| 2 | Bad arguments, inaccessible input, malformed/unsupported capture or exceeded resource bound; analysis is incomplete |

The JSON object has `status` (`clean`, `findings`, `invalid_capture`), `counters`, `findings` and `errors`. Every finding/error contains a fixed `code` and 1-based `line`; setup errors use line 0. Linked duplicate/error findings may add `request_line`. Text mode renders the same fixed information. For example, a lone request yields:

```json
{"code":"PENDING_REQUEST","line":1}
```

| Finding | Meaning |
| --- | --- |
| `INVALID_MESSAGE` | Outer record is valid; the message violates this envelope profile |
| `DUPLICATE_PENDING_ID` | Same sender reused an ID before completion |
| `ORPHAN_RESPONSE` | No matching opposite-sender request is pending |
| `ERROR_RESPONSE` | Structurally valid remote error outcome; resolves a matching request |
| `PENDING_REQUEST` | Request remains unresolved at complete EOF |

Capture/setup errors: `ARGUMENT_ERROR`, `IO_ERROR`, `EMPTY_CAPTURE`, `INVALID_JSON`, `INVALID_RECORD`, `BYTE_LIMIT`, `LINE_LIMIT`, `RECORD_LIMIT`. An invalid response does not resolve a pending request. An orphan error response reports both `ORPHAN_RESPONSE` and `ERROR_RESPONSE`.

`records` counts accepted outer records, including invalid messages. `requests` includes duplicate valid request envelopes. `responses` includes valid success/error responses; `matched_responses` counts resolved originals. `error_responses`, `notifications`, `invalid_messages` and `pending_requests` are separate counters. Duplicate requests do not add a second pending obligation. Findings appear in scan order, followed by pending requests in original line order.

On exit 2, counters/findings describe only the processed prefix. Pending counters may remain nonzero, but no EOF pending findings are synthesized. Do not treat an incomplete report as an audit of the whole file.

## Bounds and limits

Maximum 16 MiB input, 10,000 records and 1 MiB per physical line **including its line terminator**, using binary streaming reads. These are inclusive caps; the next offending line gets a setup error. JSON decoding has the host Python parser recursion limit. The tool limits bytes/records, not elapsed time: stdin or a special file can wait for more data. Report counts are bounded by capture records; input strings exist in memory during parsing/correlation even though reports omit them.

This checks an explicit stricter subset of JSON-RPC 2.0. The specification permits null and discourages fractional IDs; this tool rejects both. It does not verify transport framing, method schemas, reserved method semantics, authentication, timestamps, retries, application correctness, MCP initialization/capabilities/handshake compliance or protocol-era compatibility. A remote error is a finding, not proof of a server defect. A partial capture can legitimately have orphans/pending requests. Direction labels and capture completeness are supplied by the caller. Both-origin calls here describe generic JSON-RPC correlation, not the current MCP stdio transport profile. No production-server or real-user adoption claim is made.

## 中文快速开始

这是离线 JSON-RPC 2.0 双向记录检查工具，只需要 Python 3.11+，没有第三方依赖，也不会启动服务或联网。

```sh
python rpc_transcript_check.py examples/clean.jsonl
python rpc_transcript_check.py examples/findings.jsonl --format text
python -m unittest discover -s tests -v
```

输入为 UTF-8 JSONL，每行只有 `direction` 和 `message` 两个字段。方向必须为 `client_to_server` 或 `server_to_client`，消息必须是单个对象；不支持 batch 数组。ID 仅接受非空值类型中的字符串或整数，空字符串可用；null、布尔值、小数或指数写法均不接受。整数 `1` 与字符串 `"1"` 分开关联。通知不要求响应，响应可以乱序，同一 ID 可以同时存在于两个相反方向。

输出仅含固定状态码、计数和行号，不输出文件路径、方法、ID 或业务内容。退出码 0 表示本检查范围内无发现，1 表示发现消息格式问题、重复/孤立/未完成请求或错误响应，2 表示记录外层或 JSON 损坏、参数/读取错误或超过资源上限。退出 2 时报告只覆盖已处理前缀，不能据此判定整个文件。`INVALID_MESSAGE` 是消息级发现；外层结构错误则是 `INVALID_RECORD` 并退出 2。

最多 16 MiB、10,000 行记录，每行最多 1 MiB（含换行符）。空文件、空行、BOM、重复 JSON 键和 NaN/Infinity 均被拒绝。这里只检查明确的较严格 JSON-RPC 子集，不保证业务语义、MCP 握手、任何 MCP 版本或实际服务可用性。错误响应也可能是正常业务结果，截断记录也可能自然产生未完成请求。

See [RESEARCH.md](RESEARCH.md) for sources and alternatives, [TESTING.md](TESTING.md) for validation boundaries. MIT license.
