import requests
import json
import getpass

KEYCLOAK_DOMAIN = "http://localhost:8180"
REALM = "authentication"
CLIENT_ID = "public-client"

TOKEN_URL = f"{KEYCLOAK_DOMAIN}/realms/{REALM}/protocol/openid-connect/token"


def login():
    print("\n=== Keycloak Login ===")
    username = input("Enter username: ")
    password = getpass.getpass("Enter password: ")

    data = {
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "username": username,
        "password": password
    }

    response = requests.post(TOKEN_URL, data=data)

    if response.status_code != 200:
        print("\n Login failed")
        print(response.text)
        return

    tokens = response.json()
    print("\n Login successful! Tokens:")

    print(json.dumps(tokens, indent=4))

    # Save tokens to a file
    with open("session.json", "w") as f:
        json.dump(tokens, f, indent=4)

    print("\n Tokens saved to session.json")


if __name__ == "__main__":
    login()
