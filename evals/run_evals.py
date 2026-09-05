import json
import os
import subprocess
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


TEST_CASES = [
    {
        "name": "apod_facts",
        "prompt": (
            "Use NASA APOD data for 2026-09-05. "
            "State the date, title, and media type."
        ),
        "required_all": [
            "2026-09-05",
            "chasing the moon",
            "image",
        ],
    },
    {
        "name": "closest_asteroid",
        "prompt": (
            "Using NASA data, name the closest asteroid approach "
            "on 2026-09-05 and state its miss distance in kilometres."
        ),
        "required_all": ["2018 bx"],
        "required_any": ["45.4 million", "45,436"],
    },
    {
        "name": "asteroid_count_and_names",
        "prompt": (
            "Using NASA data for 2026-09-05, state the number of "
            "Earth close approaches and list their names."
        ),
        "required_all": [
            "2018 bx",
            "2019 ql7",
            "2006 hc2",
        ],
        "required_any": ["3", "three"],
    },
    {
        "name": "asteroid_diameter",
        "prompt": (
            "Using NASA data, give only the estimated diameter range "
            "in metres for asteroid 2006 HC2 on 2026-09-05."
        ),
        "required_all": ["117.6", "263.1"],
    },
    {
        "name": "missing_copyright",
        "prompt": (
            "Does the NASA APOD response for 2026-09-05 provide a "
            "copyright owner? If it is missing, clearly say so."
        ),
        "required_any": [
            "not provided",
            "not listed",
            "not available",
            "missing",
            "null",
        ],
        "forbidden": ["public domain"],
    },
]


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()

    unicode_dashes = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
    for dash in unicode_dashes:
        value = value.replace(dash, "-")

    return " ".join(value.split())

def invoke_agent(prompt: str) -> tuple[str, float, str]:
    if os.name == "nt":
        command = [
            "cmd.exe",
            "/d",
            "/s",
            "/c",
            "agentcore",
            "invoke",
            "--json",
            prompt,
        ]
    else:
        command = ["agentcore", "invoke", "--json", prompt]

    started = time.perf_counter()

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )

    latency = time.perf_counter() - started

    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip())

    outer_response = json.loads(completed.stdout)
    if not outer_response.get("success"):
        raise RuntimeError(str(outer_response))

    runtime_response = json.loads(outer_response["response"])

    return (
        runtime_response["response"],
        latency,
        outer_response["sessionId"],
    )


def evaluate(case: dict, answer: str) -> dict:
    normalized_answer = normalize(answer)

    missing = [
        item
        for item in case.get("required_all", [])
        if normalize(item) not in normalized_answer
    ]

    alternatives = case.get("required_any", [])
    alternative_found = (
        not alternatives
        or any(normalize(item) in normalized_answer for item in alternatives)
    )

    forbidden_found = [
        item
        for item in case.get("forbidden", [])
        if normalize(item) in normalized_answer
    ]

    return {
        "quality_pass": (
            not missing
            and alternative_found
            and not forbidden_found
        ),
        "missing_required": missing,
        "required_alternative_found": alternative_found,
        "forbidden_found": forbidden_found,
    }


def main() -> None:
    results = []

    for case in TEST_CASES:
        try:
            answer, latency, session_id = invoke_agent(case["prompt"])
            checks = evaluate(case, answer)

            result = {
                "name": case["name"],
                "prompt": case["prompt"],
                "answer": answer,
                "latency_seconds": round(latency, 2),
                "latency_under_30s": latency < 30,
                "session_id": session_id,
                **checks,
            }
        except Exception as error:
            result = {
                "name": case["name"],
                "quality_pass": False,
                "error": str(error),
            }

        results.append(result)

        status = "PASS" if result["quality_pass"] else "FAIL"
        latency = result.get("latency_seconds", "N/A")
        print(f"{status}: {case['name']} | latency={latency}s")

    passed = sum(result["quality_pass"] for result in results)

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "total": len(results),
        "pass_rate": passed / len(results),
        "results": results,
    }

    output_directory = Path("evals/results")
    output_directory.mkdir(parents=True, exist_ok=True)

    filename = (
        output_directory
        / f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    filename.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nQuality: {passed}/{len(results)} passed")
    print(f"Report: {filename}")


if __name__ == "__main__":
    main()