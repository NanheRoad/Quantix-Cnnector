from __future__ import annotations

import re
import struct
from typing import Any

from simpleeval import simple_eval


SAFE_FUNCTIONS = {
    "int": int,
    "float": float,
    "str": str,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "len": len,
}

# 添加 JSON 解析支持
def _json_loads(s: str) -> Any:
    import json
    return json.loads(s)

def _json_get(obj: dict, key: str, default: Any = None) -> Any:
    return obj.get(key, default)

SAFE_FUNCTIONS["json.loads"] = _json_loads
SAFE_FUNCTIONS["json.get"] = _json_get
SAFE_FUNCTIONS["json.loads"] = _json_loads


class ProtocolExecutor:
    PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")

    async def run_setup_steps(
        self,
        template: dict[str, Any],
        driver,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        context = {"steps": {}, **variables}
        for step in template.get("setup_steps", []):
            result = await self._execute_step(driver, step, context)
            context["steps"][step["id"]] = {"result": result}
        return context["steps"]

    async def run_poll_steps(
        self,
        template: dict[str, Any],
        driver,
        variables: dict[str, Any],
        previous_steps: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        steps_results = previous_steps.copy() if previous_steps else {}
        context: dict[str, Any] = {"steps": steps_results, **variables}
        for step in template.get("steps", []):
            trigger = step.get("trigger", "poll")
            if trigger != "poll":
                continue
            result = await self._execute_step(driver, step, context)
            context["steps"][step["id"]] = {"result": result}
        return context["steps"]

    async def run_manual_step(
        self,
        template: dict[str, Any],
        driver,
        step_id: str,
        variables: dict[str, Any],
        params_override: dict[str, Any] | None = None,
        previous_steps: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context: dict[str, Any] = {
            "steps": previous_steps.copy() if previous_steps else {},
            **variables,
        }

        target = None
        for step in template.get("steps", []):
            if step.get("id") == step_id:
                target = step
                break

        if target is None:
            raise ValueError(f"Step not found: {step_id}")

        if target.get("trigger", "poll") != "manual":
            raise PermissionError(f"Step is not manual trigger: {step_id}")

        result = await self._execute_step(driver, target, context, params_override=params_override)
        context["steps"][target["id"]] = {"result": result}
        return {
            "step_id": target["id"],
            "result": result,
            "output": self.render_output(template, context),
        }

    async def run_message_handler(
        self,
        template: dict[str, Any],
        driver,
        payload: bytes,
        variables: dict[str, Any],
        previous_steps: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        handler = template.get("message_handler")
        if not handler:
            raise ValueError("Template has no message_handler")

        text_payload = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)
        steps = previous_steps.copy() if previous_steps else {}
        context: dict[str, Any] = {
            "payload": text_payload,
            "steps": steps,
            **variables,
        }

        # mqtt.on_message is logical action, result comes from parse payload.
        result = await self._execute_step(driver, handler, context, skip_driver=True)
        context["message_handler"] = {"result": result}
        return context["steps"], self.render_output(template, context)

    def render_output(self, template: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        output = template.get("output", {})
        return self._resolve_value(output, context)

    async def execute_one_step(
        self,
        driver,
        step: dict[str, Any],
        context: dict[str, Any],
        params_override: dict[str, Any] | None = None,
        skip_driver: bool = False,
    ) -> Any:
        return await self._execute_step(
            driver=driver,
            step=step,
            context=context,
            params_override=params_override,
            skip_driver=skip_driver,
        )

    async def _execute_step(
        self,
        driver,
        step: dict[str, Any],
        context: dict[str, Any],
        params_override: dict[str, Any] | None = None,
        skip_driver: bool = False,
    ) -> Any:
        action = step.get("action", "")
        params = self._resolve_value(step.get("params", {}), context)
        if params_override:
            params.update(params_override)

        if action == "delay":
            delay_ms = int(params.get("milliseconds", 0))
            import asyncio

            await asyncio.sleep(delay_ms / 1000)
            raw_result: Any = {"delayed_ms": delay_ms}
        elif action.startswith("transform."):
            raw_result = self._run_transform(action, params)
        elif skip_driver:
            raw_result = {"payload": context.get("payload")}
        else:
            raw_result = await driver.execute_action(action, params)

        parse_config = step.get("parse")
        if parse_config:
            return self._parse_result(parse_config, raw_result, context)
        return raw_result

    def _run_transform(self, action: str, params: dict[str, Any]) -> Any:
        source = params.get("input", "")
        text = source.decode("utf-8", errors="ignore") if isinstance(source, bytes) else str(source)

        if action == "transform.base64_decode":
            import base64

            return base64.b64decode(text)
        if action == "transform.hex_decode":
            cleaned = text.replace(" ", "")
            return bytes.fromhex(cleaned)
        if action == "transform.regex_extract":
            match = re.search(params.get("pattern", ""), text)
            if not match:
                return None
            group = int(params.get("group", 1))
            return match.group(group)
        if action == "transform.substring":
            start = int(params.get("start", 0))
            end = int(params.get("end", len(text)))
            return text[start:end]
        if action == "transform.struct_parse":
            fmt = str(params.get("format", ""))
            raw = source if isinstance(source, bytes) else str(source).encode("utf-8")
            fields = params.get("fields", [])
            unpacked = struct.unpack(fmt, raw)
            if fields:
                return {fields[i]: unpacked[i] for i in range(min(len(fields), len(unpacked)))}
            return list(unpacked)

        raise ValueError(f"Unsupported transform action: {action}")

    def _parse_result(
        self,
        parse_config: dict[str, Any],
        raw_result: Any,
        context: dict[str, Any],
    ) -> Any:
        parse_type = parse_config.get("type")

        if parse_type == "expression":
            names = {
                "registers": raw_result.get("registers", []) if isinstance(raw_result, dict) else [],
                "coils": raw_result.get("coils", []) if isinstance(raw_result, dict) else [],
                "payload": self._extract_payload(raw_result),
                "steps": context.get("steps", {}),
                "float": float,
                "int": int,
                "str": str,
            }
            names.update(context)
            return simple_eval(parse_config.get("expression", ""), names=names, functions=SAFE_FUNCTIONS)

        if parse_type == "regex":
            text = self._extract_payload(raw_result)
            match = re.search(parse_config.get("pattern", ""), text)
            if not match:
                return None
            return match.group(int(parse_config.get("group", 1)))

        if parse_type == "substring":
            text = self._extract_payload(raw_result)
            start = int(parse_config.get("start", 0))
            end = int(parse_config.get("end", len(text)))
            return text[start:end]

        if parse_type == "struct":
            fmt = parse_config.get("format", "")
            fields = parse_config.get("fields", [])
            source = raw_result.get("payload", b"") if isinstance(raw_result, dict) else b""
            payload = source if isinstance(source, bytes) else str(source).encode("utf-8")
            unpacked = struct.unpack(fmt, payload)
            if fields:
                return {fields[i]: unpacked[i] for i in range(min(len(fields), len(unpacked)))}
            return list(unpacked)

        raise ValueError(f"Unsupported parse type: {parse_type}")

    def _extract_payload(self, raw_result: Any) -> str:
        if isinstance(raw_result, dict):
            payload = raw_result.get("payload")
            if isinstance(payload, bytes):
                return payload.decode("utf-8", errors="ignore")
            if payload is not None:
                return str(payload)
        if isinstance(raw_result, bytes):
            return raw_result.decode("utf-8", errors="ignore")
        return str(raw_result)

    def _resolve_value(self, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {k: self._resolve_value(v, context) for k, v in value.items()}
        if isinstance(value, list):
            return [self._resolve_value(item, context) for item in value]
        if not isinstance(value, str):
            return value

        matches = self.PLACEHOLDER_PATTERN.findall(value)
        if not matches:
            return value

        # Full-string placeholder: return original type if possible.
        if value.strip() == "${" + matches[0] + "}" and len(matches) == 1:
            return self._get_from_context(matches[0], context)

        rendered = value
        for path in matches:
            resolved = self._get_from_context(path, context)
            rendered = rendered.replace("${" + path + "}", "" if resolved is None else str(resolved))
        return rendered

    def _get_from_context(self, path: str, context: dict[str, Any]) -> Any:
        current: Any = context
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
                continue
            return None
        return current
