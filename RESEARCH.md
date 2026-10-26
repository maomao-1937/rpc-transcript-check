# Research and scope

## Facts and primary references

The [JSON-RPC 2.0 specification](https://www.jsonrpc.org/specification) defines request/response objects, structured parameters, notifications, response ID correlation, result/error exclusivity and the error object. It says an ID can be a string, number or null, discourages null IDs and fractional number IDs, and describes batch messages. Our non-null string/integer-ID, single-message profile is deliberately narrower; refusing batches and null IDs is not a claim that they violate JSON-RPC generally.

The [official MCP Inspector repository](https://github.com/modelcontextprotocol/inspector) supplies a visual testing/debugging tool for MCP servers. That is a better starting point for interactive server testing. This project's offline, explicit-direction JSONL contract does not replace Inspector's live interactions or MCP checks.

The parent batch source review also records [MCP's dated stdio transport document](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/transports/stdio.mdx) and [official project discussion 753](https://github.com/orgs/modelcontextprotocol/discussions/753). MCP transport/protocol details can change across versions. This implementation intentionally makes no current or historical MCP handshake/compliance claim. Its two-origin requests are generic JSON-RPC behavior; they must not be interpreted as permission under the current MCP stdio transport profile. No external source code was copied, and this isolated implementation task did not perform additional network fetching.

## Inference and fair alternatives

A local CI check over already captured frames may be useful when the developer wants a portable, payload-free report and cannot or does not want to launch a server. That usefulness is a hypothesis, not demonstrated adoption.

- MCP Inspector has broader live-server and visual debugging goals. This tool cannot establish that a running server works.
- [mcp-stdio-guard](https://github.com/1Utkarsh1/mcp-stdio-guard), linked from the official discussion above, covers live handshake and post-initialization server checks. Use such a live tool when lifecycle behavior is the question. We accept an already labeled file and make no handshake claims. Its current code was not independently exercised here.
- A project-specific JSON-RPC client/SDK can validate its own models and correlate live requests. This tool instead consumes a small explicit file contract; collecting or exporting those records remains the caller's work.
- `python -m json.tool` validates ordinary JSON documents, not these line-by-line outer records or request/response lifetimes. This tool adds those checks while deliberately supporting less than the full JSON-RPC protocol.
- A custom log analyzer can preserve method names, IDs and payloads for deeper diagnosis. We omit them from reports for privacy at the cost of less diagnostic detail.

## Bounded observations and unknowns

Validation uses original synthetic transcripts and real CLI subprocesses only. No current SDK/Inspector bug was reproduced, no live server or MCP handshake was exercised, and no production traffic was analyzed. The cited discussion is not evidence of a defect in a current release. Demand, Stars, performance across all Python versions and usefulness in actual incident response remain unmeasured. Resource and parser limits intentionally reject captures outside the documented profile. Remote error outcomes are not classified as product defects.
