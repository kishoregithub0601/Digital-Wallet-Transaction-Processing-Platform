
import uuid


def test_register_customer(client):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test Customer",
            "email": f"{uuid.uuid4().hex}@example.com",
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "CUSTOMER"
    assert "password_hash" not in response.json()


def test_login_invalid_credentials(client):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401


def test_me_requires_authentication(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
