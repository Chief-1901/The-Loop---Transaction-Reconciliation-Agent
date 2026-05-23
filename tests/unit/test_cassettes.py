from pathlib import Path
from pydantic import BaseModel

from recon_agent.llm.cassettes import CassetteLayer
from recon_agent.llm.providers import RawLLMResponse


class DummySchema(BaseModel):
    x: int


def test_live_mode_does_not_read_or_write(tmp_path):
    c = CassetteLayer(mode="live", path=tmp_path / "test.jsonl")
    h = c.hash("gemini", "gemini-2.5-pro", "plan",
               [{"role": "user", "content": "hi"}], DummySchema)
    assert c.get(h) is None    # nothing exists


def test_hash_is_stable_across_instances(tmp_path):
    c1 = CassetteLayer(mode="replay", path=tmp_path / "a.jsonl")
    c2 = CassetteLayer(mode="replay", path=tmp_path / "a.jsonl")
    msgs = [{"role": "user", "content": "x"}]
    assert c1.hash("g", "m", "p", msgs, DummySchema) \
        == c2.hash("g", "m", "p", msgs, DummySchema)


def test_record_then_replay(tmp_path):
    path = tmp_path / "test.jsonl"
    rec = CassetteLayer(mode="record", path=path)
    msgs = [{"role": "user", "content": "x"}]
    h = rec.hash("g", "m", "p", msgs, DummySchema)
    resp = RawLLMResponse(text='{"x":1}', tokens_in=10, tokens_out=5, latency_ms=100)
    rec.put(h, resp)

    rep = CassetteLayer(mode="replay", path=path)
    found = rep.get(h)
    assert found is not None
    assert found.text == '{"x":1}'
    assert found.tokens_in == 10
