from collections.abc import Callable

from httpx import AsyncClient


async def test_user_crud_lifecycle(client: AsyncClient, unique: Callable[[str], str]) -> None:
    create_resp = await client.post(
        "/api/v1/users",
        json={
            "full_name": "Ada Lovelace",
            "email": f"{unique('ada')}@example.com",
            "password": "hunter2pass",
            "date_of_birth": "1990-01-01",
        },
    )
    assert create_resp.status_code == 201
    user = create_resp.json()
    assert "password_hash" not in user
    user_id = user["id"]

    get_resp = await client.get(f"/api/v1/users/{user_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["full_name"] == "Ada Lovelace"

    patch_resp = await client.patch(f"/api/v1/users/{user_id}", json={"city": "Beirut"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["city"] == "Beirut"

    delete_resp = await client.delete(f"/api/v1/users/{user_id}")
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/users/{user_id}")
    assert missing_resp.status_code == 404
