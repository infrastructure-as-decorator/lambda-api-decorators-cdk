import json
from pathlib import Path


def test_public_contract_is_present_and_version_free():
    contract_path = Path(__file__).parents[1] / "src/lambda_api_decorators_cdk/_agent/api-contract.json"
    contract = json.loads(contract_path.read_text())
    assert contract["schema_version"] == "1.0"
    assert "version" not in contract
    assert contract["exports"] == ["ApiType", "SourceLayout", "LambdaApi", "LambdaApiConfig", "ResourceBuilder"]
    assert contract_path.with_name("behavior.md").read_text().strip()
