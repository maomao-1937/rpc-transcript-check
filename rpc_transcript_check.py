#!/usr/bin/env python3
"""Check a bounded offline two-way JSON-RPC 2.0 single-message capture."""

import argparse
import json
import sys

MAX_BYTES = 16 * 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024
MAX_RECORDS = 10000
DIRECTIONS = ("client_to_server", "server_to_client")


class IntegerToken(str):
    """Preserve JSON integer identity without machine integer conversion limits."""

    def __new__(cls, token):
        return super().__new__(cls, "0" if token == "-0" else token)


class FractionToken(str):
    """Keep valid JSON non-integer numeric lexemes without float overflow."""


class CaptureError(Exception):
    def __init__(self, code, line):
        self.code = code
        self.line = line


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def reject_constant(_token):
    raise ValueError("nonfinite number")


def new_report():
    return {"status": "clean", "counters": {
        "records": 0, "requests": 0, "notifications": 0, "responses": 0,
        "error_responses": 0, "matched_responses": 0, "pending_requests": 0,
        "invalid_messages": 0}, "findings": [], "errors": []}


def identifier_key(value):
    if type(value) is IntegerToken:
        return ("integer", str(value))
    if type(value) is str:
        return ("string", value)
    return None


def message_kind(message):
    if type(message.get("jsonrpc")) is not str or message["jsonrpc"] != "2.0":
        return None
    if "method" in message:
        if type(message["method"]) is not str or "result" in message or "error" in message:
            return None
        if "params" in message and type(message["params"]) not in (dict, list):
            return None
        if "id" not in message:
            return "notification"
        return "request" if identifier_key(message["id"]) is not None else None
    if "params" in message or "id" not in message or identifier_key(message["id"]) is None:
        return None
    if ("result" in message) == ("error" in message):
        return None
    if "error" in message:
        error = message["error"]
        if (type(error) is not dict or type(error.get("code")) is not IntegerToken
                or type(error.get("message")) is not str):
            return None
        return "error_response"
    return "response"


def check_stream(stream, report):
    pending = {direction: {} for direction in DIRECTIONS}
    counters = report["counters"]
    total = 0
    line_number = 0
    while True:
        raw = stream.readline(MAX_LINE_BYTES + 1)
        if not raw:
            break
        line_number += 1
        total += len(raw)
        if total > MAX_BYTES:
            raise CaptureError("BYTE_LIMIT", line_number)
        if len(raw) > MAX_LINE_BYTES:
            raise CaptureError("LINE_LIMIT", line_number)
        if line_number > MAX_RECORDS:
            raise CaptureError("RECORD_LIMIT", line_number)
        try:
            record = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                                parse_int=IntegerToken, parse_float=FractionToken,
                                parse_constant=reject_constant)
        except (ValueError, RecursionError):
            raise CaptureError("INVALID_JSON", line_number) from None
        if (type(record) is not dict or set(record) != {"direction", "message"}
                or type(record["direction"]) is not str
                or record["direction"] not in DIRECTIONS or type(record["message"]) is not dict):
            raise CaptureError("INVALID_RECORD", line_number)
        counters["records"] += 1
        message = record["message"]
        direction = record["direction"]
        kind = message_kind(message)
        if kind is None:
            counters["invalid_messages"] += 1
            report["findings"].append({"code": "INVALID_MESSAGE", "line": line_number})
        elif kind == "notification":
            counters["notifications"] += 1
        elif kind == "request":
            counters["requests"] += 1
            key = identifier_key(message["id"])
            if key in pending[direction]:
                report["findings"].append({"code": "DUPLICATE_PENDING_ID", "line": line_number,
                                           "request_line": pending[direction][key]})
            else:
                pending[direction][key] = line_number
        else:
            counters["responses"] += 1
            origin = DIRECTIONS[1] if direction == DIRECTIONS[0] else DIRECTIONS[0]
            request_line = pending[origin].pop(identifier_key(message["id"]), None)
            if request_line is None:
                report["findings"].append({"code": "ORPHAN_RESPONSE", "line": line_number})
            else:
                counters["matched_responses"] += 1
            if kind == "error_response":
                counters["error_responses"] += 1
                finding = {"code": "ERROR_RESPONSE", "line": line_number}
                if request_line is not None:
                    finding["request_line"] = request_line
                report["findings"].append(finding)
        counters["pending_requests"] = sum(len(items) for items in pending.values())
    if line_number == 0:
        raise CaptureError("EMPTY_CAPTURE", 0)
    for request_line in sorted(line for items in pending.values() for line in items.values()):
        report["findings"].append({"code": "PENDING_REQUEST", "line": request_line})


def emit(report, output_format="json"):
    if output_format == "json":
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    else:
        print("status " + report["status"])
        for counter, value in report["counters"].items():
            print(counter + " " + str(value))
        for item in report["findings"] + report["errors"]:
            fields = [item["code"], "line=" + str(item["line"])]
            if "request_line" in item:
                fields.append("request_line=" + str(item["request_line"]))
            print(" ".join(fields))


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message):
        report = new_report()
        report["status"] = "invalid_capture"
        report["errors"].append({"code": "ARGUMENT_ERROR", "line": 0})
        emit(report)
        self.exit(2)


def main(argv=None):
    parser = SafeArgumentParser(prog="rpc-transcript-check", allow_abbrev=False,
                                description=__doc__)
    parser.add_argument("capture", help="UTF-8 JSONL capture file, or - for stdin")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    options = parser.parse_args(argv)
    report = new_report()
    try:
        if options.capture == "-":
            check_stream(sys.stdin.buffer, report)
        else:
            with open(options.capture, "rb") as stream:
                check_stream(stream, report)
    except CaptureError as error:
        report["errors"].append({"code": error.code, "line": error.line})
    except (OSError, ValueError):
        report["errors"].append({"code": "IO_ERROR", "line": 0})
    if report["errors"]:
        report["status"] = "invalid_capture"
        exit_code = 2
    elif report["findings"]:
        report["status"] = "findings"
        exit_code = 1
    else:
        exit_code = 0
    emit(report, options.format)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
