from recon_agent.tools.registry import ToolRegistry


def test_registry_discovers_real_tools():
    ToolRegistry.discover(force=True)
    names = {t.name for t in ToolRegistry.available()}
    assert "load_csv" in names
    assert "fetch_api" in names
    assert "normalize_timezone" in names
    assert "match_records" in names
    assert "classify_discrepancy" in names
    assert "propose_correction" in names
    assert "apply_correction" in names
    assert "verify_reconciliation" in names


def test_registry_disable_filters():
    ToolRegistry.discover(force=True)
    available = ToolRegistry.available(disabled={"fetch_api"})
    names = {t.name for t in available}
    assert "fetch_api" not in names
    assert "load_csv" in names


def test_registry_schemas_for_llm():
    ToolRegistry.discover(force=True)
    schemas = ToolRegistry.schemas_for_llm()
    assert len(schemas) >= 8
    assert all("input_schema" in s for s in schemas)


def test_bind_router_injects_into_llm_tools():
    from unittest.mock import MagicMock
    ToolRegistry.discover(force=True)
    fake_router = MagicMock()
    ToolRegistry.bind_router(fake_router)
    classify_tool = ToolRegistry.get("classify_discrepancy")
    propose_tool = ToolRegistry.get("propose_correction")
    assert classify_tool.router is fake_router
    assert propose_tool.router is fake_router
