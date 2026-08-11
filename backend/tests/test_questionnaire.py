"""Integration tests for POST /api/v1/questionnaire and GET
/api/v1/questionnaire/me — the real, authenticated, server-scored signup
questionnaire (Blocks A-E). Distinct from the smoke-test CRUD router
covered in test_questionnaire_responses.py, which is untouched by this
feature and still accepts client-supplied scores with no auth.
"""

from collections.abc import Callable

import pytest
from httpx import AsyncClient

PASSWORD = "hunter2pass"


async def _register_and_login(client: AsyncClient, unique: Callable[[str], str]) -> str:
    email = f"{unique('quest')}@example.com"
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Grace Hopper",
            "email": email,
            "password": PASSWORD,
            "date_of_birth": "1990-01-01",
        },
    )
    assert register_resp.status_code == 201, register_resp.text

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login_resp.status_code == 200, login_resp.text
    token: str = login_resp.json()["access_token"]
    return token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _payload(value: int = 3, **overrides: int) -> dict[str, int]:
    payload: dict[str, int] = {}
    for i in range(1, 10):
        payload[f"ibt_{i}"] = value
    for i in range(1, 14):
        payload[f"sc_{i}"] = value
    for i in range(1, 12):
        payload[f"hed_{i}"] = value
    for i in range(1, 5):
        payload[f"util_{i}"] = value
    for i in range(1, 9):
        payload[f"norm_{i}"] = value
    payload.update(overrides)
    return payload


async def test_scoring_correctness_all_items_answered_3(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    resp = await client.post(
        "/api/v1/questionnaire", json=_payload(3), headers=_auth_headers(token)
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    # Hand-calculated (see questionnaire_scoring.py's module docstring):
    # reversing the 1-5 scale's midpoint (constant 6) leaves it unchanged,
    # so IBT and SC are both exactly 3.0. The 1-7 scale's midpoint is 4,
    # not 3, so reversing a response of 3 there (constant 8) gives 5 —
    # HED = (10*3 + 5) / 11, UTIL = (2*3 + 2*5) / 4. Regression check:
    # these four are untouched by adding Block E.
    assert body["impulse_tendency_score"] == pytest.approx(3.0)
    assert body["self_control_score"] == pytest.approx(3.0)
    assert body["hedonic_score"] == pytest.approx(35 / 11)
    assert body["utilitarian_score"] == pytest.approx(4.0)

    # Block E averages too, same as the other four: 8 pairs all
    # reverse-coding a midpoint response of 3 to 3 (6 - 3 = 3, same no-op
    # the A/B blocks rely on) gives a mean of exactly 3.0.
    assert body["normative_eval_score"] == pytest.approx(3.0)


async def test_reverse_coding_asymmetric_case_end_to_end(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    """A pure-function test can't catch a bug in how the API wires payload
    fields to item positions (e.g. an off-by-one). This drives the same
    asymmetric case through the real endpoint: Block A's only reversed item
    (8) set to 1 while everything else is 5. If reversal fired correctly,
    scored_8 = 6 - 1 = 5, so all nine scored values are 5 -> average 5.0.
    Backwards or missing reversal would leave item 8 at 1, giving a
    visibly different 4.555...
    """
    token = await _register_and_login(client, unique)
    payload = _payload(5, ibt_8=1)
    resp = await client.post("/api/v1/questionnaire", json=payload, headers=_auth_headers(token))
    assert resp.status_code == 201, resp.text
    assert resp.json()["impulse_tendency_score"] == pytest.approx(5.0)


async def test_normative_eval_reverse_coding_asymmetric_case(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    """Block E's 8 pairs are reverse-coded per-pair, not per-block — only
    pair 2 (wasteful/productive) is NOT reversed, the other 7 are. Setting
    every norm_i to 5 makes this unambiguous: pair 2 stays 5 (not
    reversed), the other 7 become 6 - 5 = 1 each. Mean = (5 + 7*1) / 8 =
    1.5. A backwards or missing reversal on any of the 7 would visibly
    change this away from 1.5.
    """
    token = await _register_and_login(client, unique)
    norm_overrides = {f"norm_{i}": 5 for i in range(1, 9)}
    payload = _payload(3, **norm_overrides)
    resp = await client.post("/api/v1/questionnaire", json=payload, headers=_auth_headers(token))
    assert resp.status_code == 201, resp.text
    assert resp.json()["normative_eval_score"] == pytest.approx(1.5)


async def test_normative_eval_maximum_score_isolates_pair_2(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    """Pins down BLOCK_E_NORM.reverse_items directly, independent of the
    all-5s asymmetric case above. Pair 2 (wasteful/productive) is the only
    pair NOT reversed — set it to 5 (its favourable end) while every other
    pair is set to 1 (their unfavourable end, since favourable is on the
    left for those seven). Reversed: scored_i = 6 - 1 = 5. Correct scoring
    is therefore the maximum possible mean: (5 + 7*5) / 8 = 5.0. If
    reverse_items were missing pair 2's exclusion, or included some other
    item instead, this would come out below 5.0.
    """
    token = await _register_and_login(client, unique)
    norm_overrides = {f"norm_{i}": 1 for i in range(1, 9)}
    norm_overrides["norm_2"] = 5
    payload = _payload(3, **norm_overrides)
    resp = await client.post("/api/v1/questionnaire", json=payload, headers=_auth_headers(token))
    assert resp.status_code == 201, resp.text
    assert resp.json()["normative_eval_score"] == pytest.approx(5.0)


async def test_normative_eval_polarity_stored_in_raw_responses(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    resp = await client.post(
        "/api/v1/questionnaire", json=_payload(3), headers=_auth_headers(token)
    )
    assert resp.status_code == 201, resp.text
    raw = resp.json()["raw_responses"]

    # Every pair except 2 (wasteful/productive) has its favourable
    # adjective on the left, per the fixed frontend layout — see
    # questionnaire_scoring.py's BLOCK_E_NORM comment.
    reversed_pairs = {1, 3, 4, 5, 6, 7, 8}
    for i in range(1, 9):
        expected_side = "left" if i in reversed_pairs else "right"
        assert raw[f"norm_{i}_favourable_side"] == expected_side
        assert raw[f"norm_{i}"] == 3


async def test_normative_eval_out_of_range_zero_returns_422(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    resp = await client.post(
        "/api/v1/questionnaire", json=_payload(3, norm_1=0), headers=_auth_headers(token)
    )
    assert resp.status_code == 422


async def test_normative_eval_out_of_range_six_returns_422(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    resp = await client.post(
        "/api/v1/questionnaire", json=_payload(3, norm_1=6), headers=_auth_headers(token)
    )
    assert resp.status_code == 422


async def test_missing_item_returns_422_not_partial_score(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    payload = _payload(3)
    del payload["sc_7"]
    resp = await client.post("/api/v1/questionnaire", json=payload, headers=_auth_headers(token))
    assert resp.status_code == 422


async def test_out_of_range_zero_returns_422(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    resp = await client.post(
        "/api/v1/questionnaire", json=_payload(3, ibt_1=0), headers=_auth_headers(token)
    )
    assert resp.status_code == 422


async def test_out_of_range_six_on_1_5_scale_returns_422(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    resp = await client.post(
        "/api/v1/questionnaire", json=_payload(3, sc_5=6), headers=_auth_headers(token)
    )
    assert resp.status_code == 422


async def test_out_of_range_eight_on_1_7_scale_returns_422(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    resp = await client.post(
        "/api/v1/questionnaire", json=_payload(3, hed_1=8), headers=_auth_headers(token)
    )
    assert resp.status_code == 422


async def test_submitting_twice_returns_409(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    headers = _auth_headers(token)
    first = await client.post("/api/v1/questionnaire", json=_payload(3), headers=headers)
    assert first.status_code == 201, first.text

    second = await client.post("/api/v1/questionnaire", json=_payload(4), headers=headers)
    assert second.status_code == 409


async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/questionnaire", json=_payload(3))
    assert resp.status_code == 401


async def test_raw_responses_and_instrument_version_stored(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    payload = _payload(3, ibt_1=5)
    resp = await client.post("/api/v1/questionnaire", json=payload, headers=_auth_headers(token))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # raw_responses is the submitted payload plus one added
    # norm_i_favourable_side key per Block E pair — see
    # test_normative_eval_polarity_stored_in_raw_responses for that part.
    for key, value in payload.items():
        assert body["raw_responses"][key] == value
    assert body["instrument_version"] == "v1"
    assert "completed_at" in body


async def test_me_404s_before_submission_and_returns_it_after(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    token = await _register_and_login(client, unique)
    headers = _auth_headers(token)

    before = await client.get("/api/v1/questionnaire/me", headers=headers)
    assert before.status_code == 404

    submit = await client.post("/api/v1/questionnaire", json=_payload(3), headers=headers)
    assert submit.status_code == 201, submit.text

    after = await client.get("/api/v1/questionnaire/me", headers=headers)
    assert after.status_code == 200
    assert after.json()["id"] == submit.json()["id"]


async def test_me_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/questionnaire/me")
    assert resp.status_code == 401
