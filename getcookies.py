import requests
import pickle
import json


if __name__ == "__main__":
    with open('sites.json', 'r') as f:
        sites = json.load(f)

    for url, data in sites.items():
        with requests.Session() as session:
            result = session.post(url, data=data)
            if result.ok:
                print("logged in to {}".format(url))

    with open('cookies.jar', 'wb') as f:
        pickle.dump(session.cookies, f)
