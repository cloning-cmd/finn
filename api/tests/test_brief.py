import datetime as dt

from fastapi.testclient import TestClient

from api.main import app
from api.models import Card
from api.routers.brief import build_brief, load_fixture_cards


def test_fixtures_validate_and_obey_copy_limits():
    cards = load_fixture_cards()
    assert len(cards) >= 10
    for c in cards:
        assert isinstance(c, Card)
        assert len(c.headline) <= 70
        assert "!" not in c.headline
        assert c.one_liner is None or len(c.one_liner) <= 140


def test_build_brief_orders_and_groups():
    cards = load_fixture_cards()
    now = dt.datetime.now(dt.timezone.utc)
    b = build_brief(cards, now - dt.timedelta(days=7), now)
    pr = [c.priority for c in b.cards]
    assert pr == sorted(pr, reverse=True)
    assert all(c.tier != "buried" for c in b.cards)
    assert b.counts.buried == sum(g.count for g in b.buried)
    assert b.minutes_saved == round(b.counts.buried * 0.5, 1)


def test_brief_endpoint_fixture():
    with TestClient(app) as c:
        r = c.get("/brief?fixture=1&window=7d")
        assert r.status_code == 200
        body = r.json()
        assert "from" in body["window"] and body["counts"]["lead"] >= 1
