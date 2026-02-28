from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from backend.database.models import Device, ProtocolTemplate
from backend.drivers import build_driver
from backend.drivers.mqtt_driver import MqttDriver
from backend.services.data_collector import RuntimeState
from backend.services.event_bus import EventBus
from backend.services.protocol_executor import ProtocolExecutor

logger = logging.getLogger(__name__)


@dataclass
class DeviceRuntime:
    device: Device
    template: ProtocolTemplate
    driver: Any
    state: RuntimeState
    stop_event: asyncio.Event
    task: asyncio.Task[Any] | None = None


class DeviceManager:
    def __init__(self) -> None:
        self._executor = ProtocolExecutor()
        self._event_bus = EventBus()
        self._runtimes: dict[int, DeviceRuntime] = {}
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        enabled_devices = list(Device.select().where(Device.enabled == True))  # noqa: E712
        for device in enabled_devices:
            await self.start_device(device.id)

    async def shutdown(self) -> None:
        async with self._lock:
            device_ids = list(self._runtimes.keys())
        for device_id in device_ids:
            await self.stop_device(device_id)

    async def start_device(self, device_id: int) -> None:
        device = Device.get_or_none(Device.id == device_id)
        if device is None:
            return

        template = ProtocolTemplate.get_or_none(ProtocolTemplate.id == device.protocol_template_id)
        if template is None:
            logger.error("Missing protocol template for device_id=%s", device_id)
            return

        await self.stop_device(device_id)

        runtime = DeviceRuntime(
            device=device,
            template=template,
            driver=build_driver(template.protocol_type, device.connection_params),
            state=RuntimeState(device_id=device.id, device_name=device.name, device_code=device.device_code),
            stop_event=asyncio.Event(),
        )

        runtime.task = asyncio.create_task(self._run_runtime(runtime), name=f"device-runtime-{device.id}")
        async with self._lock:
            self._runtimes[device.id] = runtime

    async def stop_device(self, device_id: int) -> None:
        async with self._lock:
            runtime = self._runtimes.pop(device_id, None)
        if runtime is None:
            return

        runtime.stop_event.set()
        if runtime.task:
            runtime.task.cancel()
            try:
                await runtime.task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # pragma: no cover
                logger.exception("Runtime cancellation failed: %s", exc)

        await runtime.driver.disconnect()
        runtime.state.mark_offline("stopped")
        await self._event_bus.publish(runtime.state.to_message())

    async def reload_device(self, device_id: int) -> None:
        device = Device.get_or_none(Device.id == device_id)
        if device is None:
            await self.stop_device(device_id)
            return

        if not device.enabled:
            await self.stop_device(device_id)
            return

        await self.start_device(device_id)

    async def remove_device(self, device_id: int) -> None:
        await self.stop_device(device_id)

    async def execute_manual_step(
        self,
        device_id: int,
        step_id: str,
        params_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        runtime = await self.get_runtime(device_id)
        if runtime is None:
            raise ValueError("Device runtime not found or not enabled")

        result = await self._executor.run_manual_step(
            template=runtime.template.template,
            driver=runtime.driver,
            step_id=step_id,
            variables=runtime.device.template_variables,
            params_override=params_override,
            previous_steps=runtime.state.step_results,
        )
        return result

    async def get_runtime(self, device_id: int) -> DeviceRuntime | None:
        async with self._lock:
            return self._runtimes.get(device_id)

    async def subscribe(self):
        return await self._event_bus.subscribe()

    async def unsubscribe(self, queue):
        await self._event_bus.unsubscribe(queue)

    async def runtime_snapshot(self, device_id: int) -> dict[str, Any]:
        runtime = await self.get_runtime(device_id)
        if runtime is None:
            return {"status": "offline", "weight": None, "unit": "kg", "timestamp": None, "error": None}
        return runtime.state.to_message()

    async def _run_runtime(self, runtime: DeviceRuntime) -> None:
        backoff = 1.0
        setup_done = False

        if isinstance(runtime.driver, MqttDriver):
            runtime.driver.register_message_handler(
                lambda topic, payload: self._handle_mqtt_message(runtime, topic, payload)
            )

        while not runtime.stop_event.is_set():
            try:
                if not await runtime.driver.is_connected():
                    connected = await runtime.driver.connect()
                    if not connected:
                        connect_error = "connect failed"
                        get_last_error = getattr(runtime.driver, "get_last_error", None)
                        if callable(get_last_error):
                            last_error = get_last_error()
                            if last_error:
                                connect_error = f"connect failed: {last_error}"
                        runtime.state.mark_offline(connect_error)
                        await self._event_bus.publish(runtime.state.to_message())
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 30)
                        continue

                backoff = 1.0

                if not setup_done:
                    setup_results = await self._executor.run_setup_steps(
                        runtime.template.template,
                        runtime.driver,
                        runtime.device.template_variables,
                    )
                    runtime.state.step_results.update(setup_results)
                    setup_done = True

                protocol_type = runtime.template.protocol_type.lower()
                if protocol_type == "mqtt":
                    await asyncio.sleep(max(runtime.device.poll_interval, 1.0))
                    continue

                steps = await self._executor.run_poll_steps(
                    runtime.template.template,
                    runtime.driver,
                    runtime.device.template_variables,
                    previous_steps=runtime.state.step_results,
                )
                runtime.state.step_results = steps

                context = {"steps": steps, **runtime.device.template_variables}
                output = self._executor.render_output(runtime.template.template, context)

                weight = _to_float(output.get("weight"))
                unit = str(output.get("unit", "kg"))
                runtime.state.mark_online(weight, unit)
                await self._event_bus.publish(runtime.state.to_message())
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                runtime.state.mark_error(str(exc))
                await self._event_bus.publish(runtime.state.to_message())
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

            await asyncio.sleep(max(runtime.device.poll_interval, 0.1))

    async def _handle_mqtt_message(self, runtime: DeviceRuntime, topic: str, payload: bytes) -> None:
        try:
            steps, output = await self._executor.run_message_handler(
                runtime.template.template,
                runtime.driver,
                payload,
                runtime.device.template_variables,
                previous_steps=runtime.state.step_results,
            )
            runtime.state.step_results = steps
            weight = _to_float(output.get("weight"))
            unit = str(output.get("unit", "kg"))
            runtime.state.mark_online(weight, unit)
            await self._event_bus.publish(runtime.state.to_message())
        except Exception as exc:
            runtime.state.mark_error(f"mqtt message handling failed: {topic}: {exc}")
            await self._event_bus.publish(runtime.state.to_message())


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


manager = DeviceManager()
