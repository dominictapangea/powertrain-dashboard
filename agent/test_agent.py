"""Offline tests for the agent loop: fake BigQuery and Gemini clients, no network."""

from types import SimpleNamespace

import agent

CFG = agent.Config(api_key="k", model="m", project="my-project", dataset="my_dataset")


class FakeBigQuery:
    def __init__(self, rows=None, fail=None):
        self.rows, self.fail, self.calls = rows or [], fail, []

    def query(self, sql, job_config=None):
        self.calls.append((sql, job_config))
        if self.fail:
            raise self.fail
        return SimpleNamespace(
            total_bytes_processed=1000,
            result=lambda timeout=None, max_results=None: [SimpleNamespace(items=lambda r=r: r.items()) for r in self.rows],
        )


def test_rejected_query_never_reaches_bigquery():
    bq = FakeBigQuery()
    result = agent.run_sql(bq, CFG, "DROP TABLE analytics")
    assert "error" in result and "rejected" in result["error"]
    assert bq.calls == []


def test_valid_query_runs_with_cap_and_limit():
    bq = FakeBigQuery(rows=[{"powertrain_type": "Diesel ICE", "n": 18}])
    result = agent.run_sql(bq, CFG, "SELECT powertrain_type, COUNT(*) AS n FROM analytics GROUP BY 1")
    assert result["rows"] == [{"powertrain_type": "Diesel ICE", "n": 18}]
    assert result["sql"].endswith("LIMIT 100")
    real_run_config = bq.calls[-1][1]
    assert real_run_config.maximum_bytes_billed == agent.MAX_BYTES_BILLED


def test_bigquery_errors_become_a_message():
    from google.api_core.exceptions import BadRequest

    bq = FakeBigQuery(fail=BadRequest("Unrecognized name: foo"))
    result = agent.run_sql(bq, CFG, "SELECT foo FROM analytics")
    assert "Unrecognized name: foo" in result["error"]


def test_unexpected_errors_become_a_message():
    bq = FakeBigQuery(fail=TimeoutError("took too long"))
    result = agent.run_sql(bq, CFG, "SELECT 1 FROM analytics")
    assert "took too long" in result["error"]


class FakeGemini:
    """Replays scripted interactions and records what the agent sends back."""

    def __init__(self, scripted):
        self.scripted, self.sent = list(scripted), []
        self.interactions = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.sent.append(kwargs)
        return self.scripted.pop(0)


def _call(query):
    return SimpleNamespace(type="function_call", id="c1", name="run_sql", arguments={"query": query})


def test_ask_runs_tool_then_returns_answer():
    gemini = FakeGemini([
        SimpleNamespace(id="i1", steps=[_call("SELECT COUNT(*) AS n FROM analytics")], output_text=None),
        SimpleNamespace(id="i2", steps=[], output_text="872 vehicles."),
    ])
    bq = FakeBigQuery(rows=[{"n": 872}])
    answer, last_id = agent.ask(gemini, bq, CFG, "system", "How many vehicles?")
    assert answer == "872 vehicles."
    assert last_id == "i2"
    result_step = gemini.sent[1]["input"][0]
    assert result_step["type"] == "function_result" and result_step["call_id"] == "c1"
    assert gemini.sent[1]["previous_interaction_id"] == "i1"
    assert not result_step["is_error"]


def test_ask_reports_tool_errors_to_the_model_instead_of_crashing():
    gemini = FakeGemini([
        SimpleNamespace(id="i1", steps=[_call("DELETE FROM analytics")], output_text=None),
        SimpleNamespace(id="i2", steps=[], output_text="I can only read data."),
    ])
    answer, _ = agent.ask(gemini, FakeBigQuery(), CFG, "system", "Delete everything")
    assert answer == "I can only read data."
    assert gemini.sent[1]["input"][0]["is_error"] is True


def test_ask_stops_after_too_many_tool_calls_and_resets_conversation():
    endless = [SimpleNamespace(id=f"i{n}", steps=[_call("SELECT 1 FROM other")], output_text=None)
               for n in range(agent.MAX_TOOL_CALLS + 1)]
    answer, last_id = agent.ask(FakeGemini(endless), FakeBigQuery(), CFG, "system", "loop")
    assert "allowed number of queries" in answer
    assert last_id is None


def test_safe_ask_turns_api_failures_into_a_message(capsys):
    class Broken:
        interactions = SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(RuntimeError("401 API key not valid")))

    answer, previous = agent.safe_ask(Broken(), FakeBigQuery(), CFG, "system", "hi", "prev")
    assert answer is None and previous == "prev"
    assert "Gemini API error" in capsys.readouterr().out
