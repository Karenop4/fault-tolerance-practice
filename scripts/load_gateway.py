import argparse
import concurrent.futures
import json
import time

import requests


def make_request(index, url):
    payload = {
        "user_id": f"user-{index}",
        "event_id": "concert-01",
        "quantity": 1,
        "price": 50,
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code, response.json()
    except Exception as exc:  # noqa: BLE001 - demo script
        return "error", str(exc)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5000/api/reserve")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    started = time.time()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(make_request, i, args.url) for i in range(args.requests)]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    elapsed = time.time() - started
    summary = {}
    for status, _ in results:
        summary[status] = summary.get(status, 0) + 1

    print(json.dumps({"elapsed": elapsed, "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
