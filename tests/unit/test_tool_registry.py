from recon_agent.tools.registry import ToolRegistry


def test_registry_discovers_noop():
    ToolRegistry.discover()
    tools = ToolRegistry.available()
    names = [t.name for t in tools]
    assert "noop" in names


def test_registry_disable_filters():
    ToolRegistry.discover()
    available = ToolRegistry.available(disabled={"noop"})
    names = [t.name for t in available]
    assert "noop" not in names


def test_registry_schemas_for_llm():
    ToolRegistry.discover()
    schemas = ToolRegistry.schemas_for_llm()
    assert len(schemas) >= 1
    assert all("input_schema" in s for s in schemas)
