import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_connection, init_db
from app.main import app
from app.services.policy_seed import seed_demo_policies

GOLDEN_TEXT = (
    "From next quarter, all purchase orders above £25,000 must require finance approval "
    "before supplier confirmation. The system must log who approved it and block "
    "confirmation if approval is missing."
)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    connection = get_connection()
    connection.execute("DELETE FROM change_sessions")
    connection.execute("DELETE FROM file_index")
    connection.execute("DELETE FROM index_meta")
    connection.commit()
    connection.close()
    seed_demo_policies()
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_agent_start_pauses_at_human_gate(client):
    from app.orchestration.agent_runner import run_agent_start

    result = run_agent_start(GOLDEN_TEXT)
    assert result.status == "paused"
    assert result.pause_gate == "human_approval"
    assert result.contract_yaml
    assert result.domain == "procurement"
    assert len(result.trace) >= 2


@pytest.mark.asyncio
async def test_agent_resume_completes_golden_path(client):
    from app.orchestration.agent_runner import run_agent_resume, run_agent_start

    start = run_agent_start(GOLDEN_TEXT)
    result = run_agent_resume(start.session_id)
    assert result.status == "completed"
    assert result.pack_filename
    assert result.graph_node_count > 0
    assert result.governance_passed is True
