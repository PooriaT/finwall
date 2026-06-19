import json
import os
import subprocess
import sys


def test_export_openapi_script_writes_expected_paths(tmp_path):
    output_path = tmp_path / "finwall-openapi.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    subprocess.run(
        [
            sys.executable,
            "scripts/export_openapi.py",
            "--output",
            str(output_path),
        ],
        check=True,
        env=env,
    )

    schema = json.loads(output_path.read_text(encoding="utf-8"))
    assert "/api/v1/portfolio" in schema["paths"]
    assert "/api/v1/portfolio/analysis/charts" in schema["paths"]
    assert "/api/v1/portfolio/audit" in schema["paths"]
