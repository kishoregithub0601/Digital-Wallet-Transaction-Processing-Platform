
import uuid


def create_customer_and_login(client):
    email = f"{uuid.uuid4().hex}@example.com"
    password = "SecurePass123!"

    register_response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Wallet Test User",
            "email": email,
            "password": password,
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_wallet(client):
    headers = create_customer_and_login(client)

    response = client.post(
        "/api/wallets",
        headers=headers,
        json={"currency": "INR"},
    )

    assert response.status_code == 201
    assert response.json()["currency"] == "INR"
    assert response.json()["status"] == "ACTIVE"


def test_wallets_require_authentication(client):
    response = client.get("/api/wallets")
    assert response.status_code == 401
