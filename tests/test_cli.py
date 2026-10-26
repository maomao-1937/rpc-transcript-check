import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "rpc_transcript_check.py"


def frame(message, direction="client_to_server"):
    return {"direction": direction, "message": message}


def request(identifier=1, **fields):
    return {"jsonrpc": "2.0", "method": "private-method", "id": identifier, **fields}


def response(identifier=1, **fields):
    return {"jsonrpc": "2.0", "id": identifier, "result": {}, **fields}


class CheckerTests(unittest.TestCase):
    def invoke(self, raw, *args):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "private-capture-name.jsonl"
            source.write_bytes(raw)
            completed = subprocess.run([sys.executable, str(CLI), str(source), *args],
                                       capture_output=True, timeout=15)
        return completed

    def check(self, rows, expected=0):
        raw = b"".join((json.dumps(row) + "\n").encode() for row in rows)
        result = self.invoke(raw)
        self.assertEqual(result.returncode, expected, result.stderr.decode(errors="replace"))
        self.assertEqual(result.stderr, b"")
        return json.loads(result.stdout)

    def codes(self, report):
        return [item["code"] for item in report["findings"]]

    def test_out_of_order_and_notification(self):
        report = self.check([frame(request(1)), frame(request(2)),
            frame({"jsonrpc":"2.0", "method":"notify", "params":[]}),
            frame(response(2), "server_to_client"), frame(response(1), "server_to_client")])
        self.assertEqual(report["counters"]["matched_responses"], 2)
        self.assertEqual(report["counters"]["notifications"], 1)
        self.assertEqual(report["findings"], [])

    def test_direction_and_typed_ids_are_separate(self):
        self.check([frame(request(1)), frame(request("1")),
            frame(request(1), "server_to_client"),
            frame(response(1)), frame(response("1"), "server_to_client"),
            frame(response(1), "server_to_client")])

    def test_duplicate_pending_does_not_replace_original(self):
        report = self.check([frame(request()), frame(request()),
                            frame(response(), "server_to_client")], 1)
        self.assertEqual(report["findings"], [{"code":"DUPLICATE_PENDING_ID", "line":2, "request_line":1}])

    def test_completed_id_may_be_reused(self):
        self.check([frame(request()), frame(response(), "server_to_client"),
                    frame(request()), frame(response(), "server_to_client")])

    def test_duplicate_response_is_orphan(self):
        report = self.check([frame(request()), frame(response(), "server_to_client"),
                            frame(response(), "server_to_client")], 1)
        self.assertEqual(self.codes(report), ["ORPHAN_RESPONSE"])

    def test_wrong_direction_does_not_resolve(self):
        report = self.check([frame(request()), frame(response())], 1)
        self.assertEqual(self.codes(report), ["ORPHAN_RESPONSE", "PENDING_REQUEST"])
        self.assertEqual(report["findings"][-1]["line"], 1)

    def test_error_response_resolves_and_is_finding(self):
        report = self.check([frame(request()), frame({"jsonrpc":"2.0", "id":1,
            "error":{"code":-32601, "message":"private-error", "data":{"secret":"private"}}},
            "server_to_client")], 1)
        self.assertEqual(self.codes(report), ["ERROR_RESPONSE"])
        self.assertEqual(report["counters"]["pending_requests"], 0)

    def test_orphan_error_has_both_findings(self):
        report = self.check([frame({"jsonrpc":"2.0", "id":1,
            "error":{"code":1,"message":"x"}}, "server_to_client")], 1)
        self.assertEqual(self.codes(report), ["ORPHAN_RESPONSE", "ERROR_RESPONSE"])

    def test_invalid_ids_are_message_findings(self):
        for identifier in [None, True, False, 1.0, 1.5, [], {}]:
            with self.subTest(identifier=identifier):
                report = self.check([frame(request(identifier))], 1)
                self.assertEqual(self.codes(report), ["INVALID_MESSAGE"])
                self.assertEqual(report["counters"]["requests"], 0)

    def test_invalid_envelopes_are_findings(self):
        messages = [{}, {"jsonrpc":"1.0","method":"x"},
            {"jsonrpc":"2.0","method":1}, request(params="bad"),
            request(params=None), request(result=1), request(error={}),
            {"jsonrpc":"2.0", "id":1}, response(error={}),
            response(params=[]), {"jsonrpc":"2.0","result":1},
            {"jsonrpc":"2.0","id":1,"error":{"code":True,"message":"bad"}},
            {"jsonrpc":"2.0","id":1,"error":{"code":1,"message":4}},
            {"jsonrpc":"2.0","id":1,"error":[]},
            {"jsonrpc":"2.0","id":1,"error":{"code":1}},
            {"jsonrpc":"2.0","result":1,"id":None}]
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual(self.codes(self.check([frame(message)], 1)), ["INVALID_MESSAGE"])

    def test_structured_params_and_extension_members(self):
        self.check([frame({"jsonrpc":"2.0","method":"n","params":{},"extension":True}),
                    frame({"jsonrpc":"2.0","method":"n","params":[1]})])

    def test_malformed_outer_records(self):
        for value in [[], {}, {"direction":"up", "message":{}},
                      {"direction":"client_to_server","message":[]},
                      {**frame({}),"extra":1}]:
            with self.subTest(value=value):
                result = self.invoke(json.dumps(value).encode())
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["errors"][0]["code"], "INVALID_RECORD")

    def test_invalid_json_utf8_and_blank_lines(self):
        for raw in [b"", b"\n", b"{", b"\xff", b"\xef\xbb\xbf{}", b"{} {}"]:
            with self.subTest(raw=raw):
                self.assertEqual(self.invoke(raw).returncode, 2)

    def test_duplicate_keys_and_nonfinite_numbers_anywhere(self):
        for raw in [b'{"direction":"client_to_server","direction":"server_to_client","message":{}}',
            b'{"direction":"client_to_server","message":{"jsonrpc":"2.0","method":"n","params":{"x":1,"x":2}}}',
            b'{"direction":"client_to_server","message":{"jsonrpc":"2.0","method":"n","params":[NaN]}}',
            b'{"direction":"client_to_server","message":{"jsonrpc":"2.0","method":"n","params":[Infinity]}}']:
            with self.subTest(raw=raw):
                self.assertEqual(self.invoke(raw).returncode, 2)

    def test_negative_zero_and_huge_integer_ids(self):
        raw = ('{"direction":"client_to_server","message":{"jsonrpc":"2.0","method":"x","id":-0}}\n'
               '{"direction":"server_to_client","message":{"jsonrpc":"2.0","id":0,"result":null}}\n')
        self.assertEqual(self.invoke(raw.encode()).returncode, 0)
        number = "9" * 5000
        raw = ('{"direction":"client_to_server","message":{"jsonrpc":"2.0","method":"x","id":'+number+'}}\n'
               '{"direction":"server_to_client","message":{"jsonrpc":"2.0","id":'+number+',"result":null}}\n')
        self.assertEqual(self.invoke(raw.encode()).returncode, 0)

    def test_very_large_finite_parameter_number(self):
        raw = b'{"direction":"client_to_server","message":{"jsonrpc":"2.0","method":"n","params":[1e9999]}}'
        self.assertEqual(self.invoke(raw).returncode, 0)

    def test_final_newline_optional_and_crlf(self):
        raw = json.dumps(frame({"jsonrpc":"2.0","method":"n"})).encode()
        self.assertEqual(self.invoke(raw).returncode, 0)
        self.assertEqual(self.invoke(raw+b"\r\n").returncode, 0)

    def test_capture_error_takes_precedence(self):
        result = self.invoke((json.dumps(frame(request()))+"\n{bad").encode())
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertEqual(report["errors"][0]["line"], 2)
        self.assertNotIn("PENDING_REQUEST", self.codes(report))

    def test_line_record_total_and_depth_limits(self):
        line = json.dumps(frame({"jsonrpc":"2.0","method":"n"})).encode()+b"\n"
        cases = [(b" "*(1024*1024+1), "LINE_LIMIT"),
                 (line*10001, "RECORD_LIMIT"),
                 ((b" "*900000+line)*19, "BYTE_LIMIT"),
                 (b"["*2000+b"0"+b"]"*2000, "INVALID_JSON")]
        for raw, code in cases:
            with self.subTest(code=code):
                result = self.invoke(raw)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["errors"][0]["code"], code)

    def test_exact_record_limit(self):
        line = json.dumps(frame({"jsonrpc":"2.0","method":"n"})).encode()+b"\n"
        report = json.loads(self.invoke(line*10000).stdout)
        self.assertEqual(report["counters"]["records"], 10000)
        self.assertEqual(report["errors"], [])

    def test_privacy_json_and_text(self):
        rows = [frame(request("secret-id", params={"secret-param":"secret-value"})),
                frame({"jsonrpc":"2.0","id":"secret-id","error":{"code":1,"message":"secret-message"}}, "server_to_client")]
        raw = b"".join((json.dumps(row)+"\n").encode() for row in rows)
        for fmt in ["json", "text"]:
            result = self.invoke(raw, "--format", fmt)
            output = (result.stdout+result.stderr).decode()
            for token in ["secret", "private-method", "private-capture-name", "Traceback"]:
                self.assertNotIn(token, output)

    def test_missing_file_and_bad_arguments_do_not_echo(self):
        for args in [["secret-missing-path"], ["--private-secret"], [],
                     ["secret-path","--format","secret-format"]]:
            result = subprocess.run([sys.executable,str(CLI),*args], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(b"secret", result.stdout+result.stderr)
            json.loads(result.stdout)

    def test_exact_byte_and_line_boundaries(self):
        base = json.dumps(frame({"jsonrpc":"2.0","method":"n"})).encode()+b"\n"
        line = b" "*(1024*1024-len(base))+base
        one = self.invoke(line)
        self.assertEqual(one.returncode, 0)
        exact = self.invoke(line*16)
        self.assertEqual(exact.returncode, 0)
        self.assertEqual(json.loads(exact.stdout)["counters"]["records"], 16)
        over = self.invoke(line*16+b"\n")
        self.assertEqual(over.returncode, 2)
        self.assertEqual(json.loads(over.stdout)["errors"], [{"code":"BYTE_LIMIT","line":17}])

    def test_invalid_response_does_not_consume_request(self):
        report = self.check([frame(request()),
            frame(response(error={}), "server_to_client")], 1)
        self.assertEqual(self.codes(report), ["INVALID_MESSAGE", "PENDING_REQUEST"])
        self.assertEqual(report["counters"]["pending_requests"], 1)

    def test_response_to_notification_is_orphan(self):
        report = self.check([frame({"jsonrpc":"2.0","method":"n"}),
                            frame(response(), "server_to_client")], 1)
        self.assertEqual(self.codes(report), ["ORPHAN_RESPONSE"])

    def test_string_identity_unicode_empty_and_null_result(self):
        for identifier in ["", "雪", "01"]:
            with self.subTest(identifier=identifier):
                self.check([frame(request(identifier)),
                    frame(response(identifier, result=None), "server_to_client")])

    def test_stdin_and_help(self):
        result = subprocess.run([sys.executable,str(CLI),"-"],
            input=(json.dumps(frame({"jsonrpc":"2.0","method":"n"}))+"\n").encode(),
            capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        result = subprocess.run([sys.executable,str(CLI),"--help"], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"usage:",result.stdout)


if __name__ == "__main__":
    unittest.main()
