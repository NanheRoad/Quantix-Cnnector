from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.database.connection import close_db, init_db
from backend.database.models import Device, ProtocolTemplate


def export_data(output_path: Path) -> None:
    payload = {
        "protocol_templates": [row.to_dict() for row in ProtocolTemplate.select().order_by(ProtocolTemplate.id.asc())],
        "devices": [row.to_dict() for row in Device.select().order_by(Device.id.asc())],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported to {output_path}")


def import_data(input_path: Path) -> None:
    payload = json.loads(input_path.read_text(encoding="utf-8"))

    template_name_to_id: dict[str, int] = {}
    for item in payload.get("protocol_templates", []):
        row, _created = ProtocolTemplate.get_or_create(
            name=item["name"],
            defaults={
                "description": item.get("description"),
                "protocol_type": item.get("protocol_type", "modbus_tcp"),
                "template": item.get("template", {}),
                "is_system": item.get("is_system", False),
            },
        )
        row.description = item.get("description")
        row.protocol_type = item.get("protocol_type", row.protocol_type)
        row.template = item.get("template", row.template)
        row.is_system = item.get("is_system", row.is_system)
        row.save()
        template_name_to_id[row.name] = row.id

    for item in payload.get("devices", []):
        template_id = item.get("protocol_template_id")
        template = ProtocolTemplate.get_or_none(ProtocolTemplate.id == template_id)
        if template is None:
            continue

        row, _created = Device.get_or_create(
            name=item["name"],
            defaults={
                "protocol_template": template.id,
                "connection_params": item.get("connection_params", {}),
                "template_variables": item.get("template_variables", {}),
                "poll_interval": item.get("poll_interval", 1.0),
                "enabled": item.get("enabled", True),
            },
        )
        row.protocol_template = template.id
        row.connection_params = item.get("connection_params", {})
        row.template_variables = item.get("template_variables", {})
        row.poll_interval = item.get("poll_interval", 1.0)
        row.enabled = item.get("enabled", True)
        row.save()

    print(f"Imported from {input_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Quantix database data")
    parser.add_argument("--export", dest="export_path", help="Export database data to JSON file")
    parser.add_argument("--import", dest="import_path", help="Import database data from JSON file")
    args = parser.parse_args()

    if bool(args.export_path) == bool(args.import_path):
        raise SystemExit("Provide either --export or --import")

    init_db(seed=False)
    try:
        if args.export_path:
            export_data(Path(args.export_path))
        else:
            import_data(Path(args.import_path))
    finally:
        close_db()


if __name__ == "__main__":
    main()
