import concurrent.futures
import json

import requests

INVENTORY_RESET_URL = "http://localhost:5002/admin/reset"
RESERVE_URL = "http://localhost:5000/api/reserve"

payload = {
    "user_id": "race-user",
    "event_id": "concert-02",
    "quantity": 1,
    "price": 80,
}


def main():
    requests.post(INVENTORY_RESET_URL, json={"event_id": "concert-02", "seats": 1}, timeout=3)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(requests.post, RESERVE_URL, json=payload, timeout=5) for _ in range(2)]
        results = []
        for future in futures:
            response = future.result()
            results.append({"status": response.status_code, "body": response.json()})

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
