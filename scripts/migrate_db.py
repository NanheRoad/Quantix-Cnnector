from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.database.connection import close_db, init_db
from backend.database.models import Device, ProtocolTemplate, build_default_device_code, normalize_device_code


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

    used_codes: set[str] = {str(row.device_code) for row in Device.select(Device.device_code) if row.device_code}
    for item in payload.get("devices", []):
        template_id = item.get("protocol_template_id")
        template = ProtocolTemplate.get_or_none(ProtocolTemplate.id == template_id)
        if template is None:
            continue

        raw_code = item.get("device_code")
        if not raw_code:
            raw_code = build_default_device_code(int(item.get("id") or 0) or 1)
        try:
            normalized_code = normalize_device_code(raw_code)
        except Exception:
            normalized_code = build_default_device_code(int(item.get("id") or 0) or 1)

        row = Device.get_or_none(Device.device_code == normalized_code)
        if row is None:
            row = Device.get_or_none(Device.name == item["name"])

        if row is not None and row.device_code in used_codes:
            used_codes.remove(row.device_code)

        candidate_code = normalized_code
        suffix = 1
        while candidate_code in used_codes:
            suffix_text = f"-{suffix}"
            max_base_len = 64 - len(suffix_text)
            candidate_code = f"{normalized_code[:max_base_len]}{suffix_text}"
            suffix += 1
        used_codes.add(candidate_code)

        if row is None:
            row = Device.create(
                device_code=candidate_code,
                name=item["name"],
                protocol_template=template.id,
                connection_params=item.get("connection_params", {}),
                template_variables=item.get("template_variables", {}),
                poll_interval=item.get("poll_interval", 1.0),
                enabled=item.get("enabled", True),
            )

        row.device_code = candidate_code
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
