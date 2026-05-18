import logging
from threading import Event
from typing import Callable

from .engine_adapter import HotwordEngineAdapter, TriggerEvent


class HotwordListener:
    def __init__(
        self,
        engine: HotwordEngineAdapter,
        stop_event: Event,
        on_trigger: Callable[[TriggerEvent], None],
        on_error: Callable[[str], None] | None,
        logger: logging.Logger,
    ) -> None:
        self._engine = engine
        self._stop_event = stop_event
        self._on_trigger = on_trigger
        self._on_error = on_error
        self._logger = logger

    def run(self) -> None:
        self._logger.info("Listener loop started")
        while not self._stop_event.is_set():
            try:
                trigger = self._engine.wait_for_trigger(self._stop_event)
            except Exception:
                self._logger.exception("Unhandled error while waiting for trigger")
                if self._on_error is not None:
                    self._on_error("Listener konnte nicht auf Mikrofon zugreifen oder Trigger lesen")
                if not self._stop_event.is_set():
                    self._stop_event.wait(timeout=1.0)
                continue
            if trigger is None:
                continue
            self._handle_trigger(trigger)
        self._logger.info("Listener loop stopped")

    def _handle_trigger(self, trigger: TriggerEvent) -> None:
        self._logger.info("Trigger received from %s", trigger.source)
        try:
            self._on_trigger(trigger)
        except Exception:
            self._logger.exception("Unhandled error while processing trigger")
