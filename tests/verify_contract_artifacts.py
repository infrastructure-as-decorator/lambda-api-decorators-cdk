"""Verify that built CDK artifacts carry the public contract."""
import json
import sys
import tarfile
import zipfile
from pathlib import Path


def validate(payload):
    required = {"schema_version", "distribution", "import_package", "exports", "functions", "decorators", "classes", "exceptions"}
    assert payload["schema_version"] == "1.0"
    assert required <= payload.keys()
    assert "version" not in payload


def main(dist_dir):
    dist = Path(dist_dir)
    wheels = list(dist.glob("*.whl"))
    sdists = list(dist.glob("*.tar.gz"))
    assert len(wheels) == len(sdists) == 1, (wheels, sdists)
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        contract = [name for name in names if name.endswith("/_agent/api-contract.json")]
        behavior = [name for name in names if name.endswith("/_agent/behavior.md")]
        assert len(contract) == len(behavior) == 1, (contract, behavior)
        validate(json.loads(archive.read(contract[0])))
    with tarfile.open(sdists[0], "r:gz") as archive:
        names = archive.getnames()
        contract = [name for name in names if name.endswith("/_agent/api-contract.json")]
        behavior = [name for name in names if name.endswith("/_agent/behavior.md")]
        assert len(contract) == len(behavior) == 1, (contract, behavior)
        member = archive.extractfile(contract[0])
        assert member is not None
        validate(json.load(member))


if __name__ == "__main__":
    main(sys.argv[1])
