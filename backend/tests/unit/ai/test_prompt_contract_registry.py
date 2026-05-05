from __future__ import annotations

from pathlib import Path

from app.ai.prompt_contracts.loader import _PROMPT_CONTRACTS, PromptContractName


def test_prompt_contract_registry_matches_enum_and_resource_files() -> None:
    resource_dir = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "ai"
        / "prompt_contracts"
        / "resources"
    )

    registered_contract_ids = set(_PROMPT_CONTRACTS)
    enum_contract_ids = {contract.value for contract in PromptContractName}
    registered_template_names = {
        contract.template_name for contract in _PROMPT_CONTRACTS.values()
    }
    resource_template_names = {path.name for path in resource_dir.glob("*.md")}

    assert registered_contract_ids == enum_contract_ids
    assert resource_template_names == registered_template_names
