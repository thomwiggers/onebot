import json
import pickle

import requests

if __name__ == "__main__":
    with open("sites.json", "r") as f:
        sites = json.load(f)

    with requests.Session() as session:
        for url, data in sites.items():
            result = session.post(url, data=data)
            if result.ok:
                print(f"logged in to {url}")

        with open("cookies.jar", "wb") as f:
            pickle.dump(session.cookies, f)
