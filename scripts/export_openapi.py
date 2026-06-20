from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from finwall.api import create_app
from finwall.config import Settings


def export_openapi(output_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="finwall-openapi-") as temp_dir:
        app = create_app(
            app_settings=Settings(
                storage_backend="sqlite",
                database_url="",
                database_path=str(Path(temp_dir) / "openapi-export.db"),
                api_token="openapi-export",
            )
        )
        schema = app.openapi()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the Finwall OpenAPI schema.")
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path to write the OpenAPI JSON schema.",
    )
    args = parser.parse_args()

    export_openapi(args.output)


if __name__ == "__main__":
    main()
