from httpx import AsyncClient


async def test_categories_expose_canonical_marketing_scores(client: AsyncClient) -> None:
    response = await client.get("/api/v1/categories")

    assert response.status_code == 200, response.text
    scores = {category["code"]: category["marketing_score"] for category in response.json()}
    assert scores == {
        "clothing": 1.0,
        "electronics": 0.0,
        "groceries": 0.75,
        "mall": 1.0,
        "online": 0.75,
        "other": 0.25,
        "restaurant": 0.5,
    }
