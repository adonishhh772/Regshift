from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.config import settings


def generate_change_pack(session: dict[str, Any]) -> dict[str, Any]:
    contract = yaml.safe_load(session.get("contract_yaml") or "{}")
    impact = session.get("impact_json", {})
    risks = session.get("risks_json", {})
    tests = session.get("tests_json", [])
    simulation = session.get("simulation_json", {})
    graph = session.get("graph_json", {})

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    pack_id = f"change_pack_{timestamp}"
    filename = f"{pack_id}.md"
    output_path = settings.generated_packs_dir / filename
    settings.generated_packs_dir.mkdir(parents=True, exist_ok=True)

    markdown = _render_markdown(
        session=session,
        contract=contract,
        impact=impact,
        risks=risks,
        tests=tests,
        simulation=simulation,
        graph=graph,
    )

    output_path.write_text(markdown, encoding="utf-8")

    return {
        "pack_id": pack_id,
        "filename": filename,
        "markdown": markdown,
        "path": str(output_path),
    }


def read_change_pack(pack_id: str) -> str | None:
    path = settings.generated_packs_dir / f"{pack_id}.md"
    if not path.exists():
        alt = settings.generated_packs_dir / pack_id
        if alt.exists():
            path = alt
        else:
            return None
    return path.read_text(encoding="utf-8")


def _render_markdown(
    session: dict[str, Any],
    contract: dict[str, Any],
    impact: dict[str, Any],
    risks: dict[str, Any],
    tests: list[dict[str, Any]],
    simulation: dict[str, Any],
    graph: dict[str, Any],
) -> str:
    files = impact.get("files", []) if isinstance(impact, dict) else []
    nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
    edges = graph.get("edges", []) if isinstance(graph, dict) else []

    file_lines = "\n".join(
        f"- `{file.get('path', file.path if hasattr(file, 'path') else '')}` — score {file.get('score', '')}"
        for file in files[:10]
    ) or "- No files indexed yet"

    test_lines = "\n".join(
        f"- **{test.get('name', '')}** (rule: `{test.get('contract_rule', '')}`)"
        for test in tests
    ) or "- No tests generated"

    before_lines = "\n".join(
        f"| {case.get('label')} | {case.get('amount')} | {case.get('approval')} | {case.get('result')} | {case.get('verdict')} |"
        for case in simulation.get("before", [])
    )
    after_lines = "\n".join(
        f"| {case.get('label')} | {case.get('amount')} | {case.get('approval')} | {case.get('result')} | {case.get('verdict')} |"
        for case in simulation.get("after", [])
    )

    risk_lines = "\n".join(
        f"- **{name.replace('_', ' ').title()}**: {level}"
        for name, level in risks.get("risks", {}).items()
    ) if isinstance(risks, dict) else "- Not scored"

    return f"""# RegShift Change Pack

## Executive Summary
RegShift compiled a business change into a machine-checkable Change Contract, traced impact through ERPNext modules and files, scored risks, generated tests, ran before/after simulation, and produced this approval-ready pack. The agent did not autonomously change production.

## Original Business Change
{session.get('business_text', '')}

## Approved Change Contract
```yaml
{session.get('contract_yaml', '')}
```

## Impacted Business Processes
{chr(10).join(f"- {process}" for process in impact.get('processes', []))}

## Impacted ERP Modules
{chr(10).join(f"- {module}" for module in impact.get('modules', []))}

## Impacted Files / Functions
{file_lines}

## Evidence Snippets
{chr(10).join(f"- `{file.get('path', '')}`: {file.get('evidence_snippet', '')[:120]}" for file in files[:5])}

## Knowledge Graph Summary
- Nodes: {len(nodes)}
- Edges: {len(edges)}
- Trace path: Business Change → Contract → Obligation → Process → Module → File → Risk → Test → Approval

## Risk Assessment
{risk_lines}

## Agent Limits
- can_generate_tests: {risks.get('agent_limits', {}).get('can_generate_tests', True) if isinstance(risks, dict) else True}
- can_generate_patch: {risks.get('agent_limits', {}).get('can_generate_patch', True) if isinstance(risks, dict) else True}
- can_auto_merge: {risks.get('agent_limits', {}).get('can_auto_merge', False) if isinstance(risks, dict) else False}
- requires_human_approval: {risks.get('agent_limits', {}).get('requires_human_approval', True) if isinstance(risks, dict) else True}

**Blocked message:** {risks.get('blocked_message', '') if isinstance(risks, dict) else ''}

## Generated Tests
{test_lines}

## Simulation Results

### Before Proposed Change
| Case | Amount | Approval | Result | Verdict |
|---|---|---|---|---|
{before_lines}

### After Proposed Change
| Case | Amount | Approval | Result | Verdict |
|---|---|---|---|---|
{after_lines}

## Required Approvals
{chr(10).join(f"- [ ] {role}" for role in contract.get('approval_roles', []))}

## Open Questions
- Confirm finance approval role mapping in ERPNext workflow configuration
- Validate audit log retention policy with compliance team
- Confirm supplier confirmation entry point in buying module

## Recommended Next Steps
1. Review and sign off this change pack with Finance Manager and Procurement Owner
2. Implement workflow and validation changes in ranked files
3. Execute generated regression tests in staging
4. Run UAT against simulation scenarios

## Rollback Considerations
- Revert workflow state transitions to previous configuration
- Remove threshold validation hook from purchase order submit path
- Preserve audit log entries created during pilot period
"""
