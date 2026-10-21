"""Every unlock DSiRPC has seen (core/unlocks.py) and how the console's sets
use it (app/engine.py): a console's unlock handed over at one sync is still
earned in the set the next sync sends, before RetroAchievements has answered
(it used to vanish from the console until the next start); the started game
checked with RetroAchievements first (its unlocks come here, the ones it
lacks go there when sending is on, and without an answer what's known here
stands in); an unlock DSiRPC already saw isn't logged or sent twice."""

import types

import pytest

import app.engine as engine_module
from core import offline, ra_set
from core.unlocks import UnlockLedger
from helpers import gen_set

T0 = 1_700_000_000


@pytest.fixture
def game(rcheevos):
    return ra_set.RaSet(gen_set.make_set(30, seed=3))


class FakeLink:
    """RALink's side: unlocked.json for the game, and what RetroAchievements
    answers (None: out of reach)."""

    def __init__(self, s, known=None, upstream=None):
        self.s, self.known, self.upstream, self.sent, self.signed_in = s, dict(known or {}), upstream, [], True

    def set_for_code(self, code):
        return self.s

    def known_unlock_times(self, game_id):
        return dict(self.known)

    def known_unlocks(self, game_id):
        return set(self.known)

    def refresh_unlocks(self, game_id, timeout=None):
        if self.upstream is None:
            return None
        self.known = dict(self.upstream)
        return dict(self.upstream)

    def pending(self, achievement_id):
        return any(aid == achievement_id for aid, _ in self.sent)

    def award_offline(self, achievement_id, when, title, game_id=0):
        self.sent.append((achievement_id, when))


@pytest.fixture
def make_engine(tmp_path, monkeypatch, game):
    monkeypatch.setattr(ra_set, "codes", lambda *a, **k: ["TEST"])
    monkeypatch.setattr(ra_set, "for_game", lambda code, *a, **k: game if code == "TEST" else None)
    monkeypatch.setattr(offline, "remember_set", lambda *a, **k: None)
    monkeypatch.setattr(engine_module, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(engine_module, "ACHIEVEMENTS_LOG", str(tmp_path / "achievements.log"))

    made = []

    def make(link, submit=True, profile=True):
        made.append(link)   # each its own ledger
        e = types.SimpleNamespace(clear_ra=False, _cleared=False, _clearing=False, ra_link=link, ra_enabled=True,
                                  blank_ra=False, dry_run=False, on_change=None,
                                  unlocks=UnlockLedger(str(tmp_path / f"local_unlocks{len(made)}.json")),
                                  ra_settings=types.SimpleNamespace(profile=profile, submit=submit),
                                  cfg=types.SimpleNamespace(ra_submit=submit))
        e._reconcile = types.MethodType(engine_module.Engine._reconcile, e)
        e.sets_for = types.MethodType(engine_module.Engine._offline_sets, e)
        e.take = types.MethodType(engine_module.Engine._offline_unlocks, e)
        return e
    return make


def earned(data):
    return {x["id"] for x in offline.read_set(data)["list"] if x["flags"] & offline.LIST_EARNED}


def unlock(aid, when=T0):
    return {"id": aid, "code": "TEST", "when": when, "seq": 1}


def test_the_ledger(tmp_path):
    ledger = UnlockLedger(str(tmp_path / "cache" / "local_unlocks.json"))
    assert ledger.times() == {}
    assert ledger.add({5: T0 + 50, 6: 0}) == {5, 6}
    assert ledger.add({5: T0, 6: T0 + 9, 7: 0}) == {7}            # earlier wins, any time over none
    assert ledger.times() == {5: T0, 6: T0 + 9, 7: 0}
    assert ledger.times({6, 99}) == {6: T0 + 9}
    (tmp_path / "cache" / "local_unlocks.json").write_text("not json")
    assert ledger.times() == {}


def test_a_console_unlock_stays_earned_at_the_next_sync(make_engine, game):
    """The launcher syncs as it connects (handing over the unlock) and again
    as it starts the game; RetroAchievements hasn't answered in between."""
    x = game.playable_achievements[0]["id"]
    e = make_engine(FakeLink(game))
    first = dict(e.sets_for(None, {}, [unlock(x)]))
    e.take([unlock(x)])
    assert x in earned(first["TEST"])
    # The console has that set now; nothing makes the next one different
    again = e.sets_for("TEST", {"TEST": offline.set_stamp(first["TEST"])}, [])
    assert again == []


def test_the_started_game_is_checked_with_retroachievements(make_engine, game):
    x, y, z = (a["id"] for a in game.playable_achievements[:3])
    link = FakeLink(game, upstream={y: T0 - 100})       # y was earned elsewhere
    e = make_engine(link)
    e.unlocks.add({x: T0})                             # x on the console, not upstream yet
    (code, data), = e.sets_for("TEST", {}, [])
    assert code == "TEST" and earned(data) == {x, y}
    assert link.sent == [(x, T0)]                       # sent, with when it happened
    assert e.unlocks.times() == {x: T0, y: T0 - 100}    # and y is known here now

    # Asked again: x is on its way, so it isn't sent twice
    e.sets_for("TEST", {}, [])
    assert link.sent == [(x, T0)]

    # Sending off: nothing goes upstream, the set is the same
    off = FakeLink(game, upstream={y: T0 - 100})
    e2 = make_engine(off, submit=False)
    e2.unlocks.add({x: T0, z: 0})
    assert earned(dict(e2.sets_for("TEST", {}, []))["TEST"]) == {x, y, z} and off.sent == []

    # Out of reach: what's known here stands in
    away = FakeLink(game, known={y: T0 - 100}, upstream=None)
    e3 = make_engine(away)
    e3.unlocks.add({x: T0})
    assert earned(dict(e3.sets_for("TEST", {}, []))["TEST"]) == {x, y} and away.sent == []


def test_an_unlock_already_seen_isnt_counted_twice(make_engine, game, tmp_path):
    x, y = (a["id"] for a in game.playable_achievements[:2])
    link = FakeLink(game)
    e = make_engine(link)
    e.unlocks.add({x: T0})                              # unlocked while connected: logged then
    assert e.take([unlock(x), unlock(y, T0 + 5)]) == 1
    assert link.sent == [(y, T0 + 5)]
    log = (tmp_path / "achievements.log").read_text()
    assert f"\t{y}\t" in log and f"\t{x}\t" not in log
