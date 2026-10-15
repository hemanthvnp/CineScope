"""Director / actor searches: the planner fetches the person's filmography, not a title search.
Run with:  pytest services/ai-orchestration/tests -v
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.intent import QueryIntent
from orchestrator.tool_planner import build_plan
from tools import tmdb_tool


def _search(**entities):
    intent = QueryIntent(primary_intent="search", interpreted_as="x")
    for key, value in entities.items():
        setattr(intent.entities, key, value)
    return intent


class TestPlanner:
    def test_director_query_fetches_only_the_filmography(self):
        plan = build_plan(_search(director="Christopher Nolan"))
        assert [n.tool for n in plan.nodes] == ["tmdb_person_movies"]
        assert plan.nodes[0].params["name"] == "christopher nolan"
        assert plan.nodes[0].params["role"] == "director"

    def test_actor_query(self):
        plan = build_plan(_search(actor="Shah Rukh Khan"))
        assert plan.nodes[0].params["role"] == "actor"

    def test_filters_go_into_the_filmography_not_a_discover_node(self):
        intent = _search(director="Christopher Nolan", year_from=2010, year_to=2019, hard_filters=True)
        plan = build_plan(intent)
        assert [n.tool for n in plan.nodes] == ["tmdb_person_movies"]
        assert (plan.nodes[0].params["year_from"], plan.nodes[0].params["year_to"]) == (2010, 2019)

    def test_title_search_unchanged(self):
        assert {n.tool for n in build_plan(_search()).nodes} == {"tmdb_search", "semantic_search"}


class _Response:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _FakeTMDB:
    def __init__(self, people, credits):
        self.people, self.credits, self.calls = people, credits, []

    async def get(self, path, params=None):
        self.calls.append(path)
        if path == "/search/person":
            return _Response({"results": self.people})
        return _Response(self.credits)


def _film(id, title, year, votes, **extra):
    return {"id": id, "title": title, "release_date": f"{year}-01-01", "vote_count": votes,
            "vote_average": 8.0, "genre_ids": [18], "original_language": "en", **extra}


def _run(monkeypatch, fake, **params):
    monkeypatch.setattr(tmdb_tool, "_get_client", lambda: fake)
    return asyncio.run(tmdb_tool.tmdb_person_movies(params))


class TestTool:
    NOLAN = [{"id": 525, "name": "Christopher Nolan", "known_for_department": "Directing"}]
    CREDITS = {
        "crew": [
            _film(1, "Inception", 2010, 30000, job="Director"),
            _film(2, "Memento", 2000, 9000, job="Director"),
            _film(2, "Memento", 2000, 9000, job="Director"),           # listed twice: dedupe
            _film(3, "Batman v Superman", 2016, 18000, job="Executive Producer"),
        ],
        "cast": [_film(4, "Nolan doc", 2020, 50, character="Himself")],
    }

    def test_director_credits_only(self, monkeypatch):
        fake = _FakeTMDB(self.NOLAN, self.CREDITS)
        movies = _run(monkeypatch, fake, name="christopher nolan", role="director")
        assert [m["title"] for m in movies] == ["Inception", "Memento"]
        assert fake.calls == ["/search/person", "/person/525/movie_credits"]

    def test_filters_apply_to_the_filmography(self, monkeypatch):
        fake = _FakeTMDB(self.NOLAN, self.CREDITS)
        movies = _run(monkeypatch, fake, name="christopher nolan", role="director", year_from=2005)
        assert [m["title"] for m in movies] == ["Inception"]

    def test_actor_skips_appearances_as_themselves(self, monkeypatch):
        credits = {"cast": [_film(5, "Dunkirk", 2017, 15000, character="Shivering Soldier"),
                            _film(6, "Some doc", 2019, 40, character="Himself")]}
        movies = _run(monkeypatch, _FakeTMDB(self.NOLAN, credits), name="cillian murphy", role="actor")
        assert [m["title"] for m in movies] == ["Dunkirk"]

    def test_prefers_a_person_known_for_the_role(self, monkeypatch):
        people = [{"id": 1, "known_for_department": "Acting"}, {"id": 2, "known_for_department": "Directing"}]
        fake = _FakeTMDB(people, {"crew": []})
        _run(monkeypatch, fake, name="someone", role="director")
        assert fake.calls[-1] == "/person/2/movie_credits"

    def test_unknown_person_returns_nothing(self, monkeypatch):
        fake = _FakeTMDB([], {})
        assert _run(monkeypatch, fake, name="nobody at all", role="director") == []
        assert fake.calls == ["/search/person"]
