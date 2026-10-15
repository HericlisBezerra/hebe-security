#!/usr/bin/env python3
"""Bounded semantic advice from Jev. Never executes the returned suggestion."""
import getpass
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

URL = "https://api.typesafe.ai/v1/systemone"
MAX_INPUT = 24000
MAX_RESPONSE = 131072


def number(value):
    return (type(value) in (int, float) and 0 <= value <= 1
            and math.isfinite(value))


def prepare(data):
    if not isinstance(data, dict) or set(data) != {"state", "questions"}:
        raise ValueError("expected state and questions only")
    state = data["state"]
    if not isinstance(state, dict) or not state.get("goal") or not state.get("scope"):
        raise ValueError("state requires a non-secret goal and scope")
    encoded = json.dumps(state, ensure_ascii=False, allow_nan=False)
    if len(encoded) > 12000:
        raise ValueError("state exceeds 12000 characters; narrow it without hiding uncertainty")
    entries = data["questions"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 8:
        raise ValueError("expected 1 to 8 questions")
    questions = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid question")
        name = entry.get("id")
        prompt = entry.get("question")
        kind = entry.get("type")
        if (not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_-]{1,48}", name)
                or name in questions or not isinstance(prompt, str)
                or not 1 <= len(prompt.strip()) <= 1600):
            raise ValueError("invalid or duplicate question identifier or prompt")
        if kind == "boolean":
            questions[name] = {"type": "noul", "instructions": prompt}
        elif kind == "choice":
            options = entry.get("options")
            if (not isinstance(options, list) or not 2 <= len(options) <= 10
                    or any(not isinstance(x, str) or not 1 <= len(x) <= 160 for x in options)
                    or len(set(options)) != len(options) or "unknown" not in options):
                raise ValueError("choice needs 2 to 10 unique options including unknown")
            questions[name] = {"type": "choice", "instructions": prompt,
                               "criteria": dict.fromkeys(options)}
        else:
            raise ValueError("question type must be boolean or choice")
    return {"model": "jev-latest", "state": encoded, "questions": questions}


def validate_reply(body, request):
    if not isinstance(body, dict) or not isinstance(body.get("model"), str):
        raise ValueError("provider did not identify the model")
    answers = body.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(request["questions"]):
        raise ValueError("missing or unexpected answers")
    result = {}
    for name, spec in request["questions"].items():
        item = answers[name]
        if not isinstance(item, dict):
            raise ValueError("invalid answer")
        if spec["type"] == "noul":
            p = item.get("noul")
            if not number(p):
                raise ValueError("invalid probability")
            result[name] = {"probability": p, "uncertain": 0.2 < p < 0.8}
        else:
            choice = item.get("choice")
            probs = item.get("probabilities")
            if (not isinstance(choice, str) or choice not in spec["criteria"]
                    or not isinstance(probs, dict) or set(probs) != set(spec["criteria"])
                    or not all(number(x) for x in probs.values())
                    or abs(sum(probs.values()) - 1) > 0.02
                    or probs[choice] < max(probs.values()) - 0.001):
                raise ValueError("invalid choice distribution")
            ranked = sorted(probs.values(), reverse=True)
            result[name] = {"suggestion": choice, "probabilities": probs,
                            "uncertain": choice == "unknown" or ranked[0] < 0.8
                            or ranked[0] - ranked[1] < 0.2}
    usage = body.get("usage", {}).get("input_tokens") if isinstance(body.get("usage"), dict) else None
    return {"status": "advice", "model": body["model"], "answers": result,
            "input_tokens": usage if type(usage) is int and usage >= 0 else None,
            "authority": "advisory_only", "executed_actions": []}


def credential():
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key
    if sys.platform == "darwin":
        # Existing user-configured TypeSafe entry; no new secret file is created.
        service = os.environ.get("HEBE_SECURITY_JEV_KEYCHAIN_SERVICE", "ai.typesafe.hebe-fast-jev")
        try:
            result = subprocess.run(["/usr/bin/security", "find-generic-password", "-s", service,
                                     "-a", getpass.getuser(), "-w"],
                                    capture_output=True, timeout=3, check=False)
            if result.returncode == 0:
                return result.stdout.decode().strip()
        except (OSError, subprocess.TimeoutExpired, UnicodeError):
            pass
    return ""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValueError("input exceeds 24000 bytes")
        request = prepare(json.loads(raw))
    except (ValueError, TypeError, UnicodeError):
        print(json.dumps({"status": "invalid_input", "reason": "invalid bounded decision request",
                          "authority": "none", "executed_actions": []}))
        return 2
    key = credential()
    if not key:
        print(json.dumps({"status": "unavailable", "reason": "TypeSafe credential unavailable",
                          "authority": "none", "executed_actions": []}))
        return 1
    req = urllib.request.Request(URL, data=json.dumps(request).encode(),
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json"}, method="POST")
    try:
        # Fixed TLS endpoint, no redirect or ambient proxy, one call, no retries.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(req, timeout=8) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("response exceeds limit")
        output = validate_reply(json.loads(raw), request)
    except (ValueError, TypeError, OSError, urllib.error.URLError):
        print(json.dumps({"status": "unavailable", "reason": "provider call or response validation failed",
                          "authority": "none", "executed_actions": []}))
        return 1
    print(json.dumps(output, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
