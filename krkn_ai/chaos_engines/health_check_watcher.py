import asyncio
from collections import defaultdict
import threading
import time
from typing import List, Dict, Optional
import numpy as np
import httpx

from krkn_ai.utils.logger import get_logger
from krkn_ai.models.config import (
    HealthCheckApplicationConfig,
    HealthCheckConfig,
    HealthCheckResult,
)

logger = get_logger(__name__)


class HealthCheckWatcher:
    def __init__(self, config: HealthCheckConfig):
        self.config = config
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._thread: Optional[threading.Thread] = None
        self._results: Dict[str, List[HealthCheckResult]] = defaultdict(list)
        self._lock = threading.Lock()

    def run(self):
        """Starts the health check watcher in a background thread with an asyncio loop."""
        logger.debug(
            f"Starting health check watcher for {len(self.config.applications)} applications"
        )
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()

    def _run_event_loop(self):
        """Internal method to run the asyncio event loop in a background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()

        try:
            self._loop.run_until_complete(self._main())
        finally:
            self._loop.close()

    async def _main(self):
        """Main async entry point for the watcher."""
        async with httpx.AsyncClient() as client:
            tasks = []
            for app_config in self.config.applications:
                tasks.append(self._watch_application(client, app_config))

            # Run all watchers concurrently
            await asyncio.gather(*tasks)

    async def _watch_application(
        self, client: httpx.AsyncClient, app_config: HealthCheckApplicationConfig
    ):
        """Asynchronous polling loop for a single application."""
        while not self._stop_event.is_set():
            try:
                start_time = time.monotonic()
                resp = await client.get(app_config.url, timeout=app_config.timeout)
                elapsed = time.monotonic() - start_time
                status = resp.status_code
                success = status == app_config.status_code
                error = None
            except httpx.RequestError as e:
                status = -1
                success = False
                elapsed = -1
                error = str(e)
            except Exception as e:
                status = -1
                success = False
                elapsed = -1
                error = f"Unexpected error: {str(e)}"

            result = HealthCheckResult(
                name=app_config.name,
                status_code=status,
                success=success,
                error=error,
                response_time=elapsed,
            )

            with self._lock:
                self._results[app_config.url].append(result)

            if not success and self.config.stop_watcher_on_failure:
                logger.warning(
                    f"Health check failed for {app_config.name} ({app_config.url}). Stopping watcher."
                )
                self._stop_event.set()
                break

            try:
                # Wait for the interval or until stopped
                await asyncio.wait_for(self._stop_event.wait(), timeout=app_config.interval)
                break  # If wait() returns, it means stop_event is set
            except asyncio.TimeoutError:
                continue  # Interval reached, continue loop

    def stop(self):
        """Stops the health check watcher and waits for the thread to finish."""
        if self._loop and self._stop_event:
            logger.debug("Stopping health check watcher")
            self._loop.call_soon_threadsafe(self._stop_event.set)
            if self._thread:
                self._thread.join(timeout=5)

    def get_results(self) -> Dict[str, List[HealthCheckResult]]:
        """Returns the collected results."""
        with self._lock:
            return dict(self._results)

    def summarize_success_rate(
        self, results: Dict[str, List[HealthCheckResult]]
    ) -> float:
        """Overall fail score across different URL results"""
        all_results = []
        for result_list in results.values():
            all_results.extend(result_list)

        total = len(all_results)
        if total == 0:
            return 0
        failed = sum(1 for r in all_results if not r.success)
        score = (failed / total) * 10
        logger.debug(f"Health check failure rate score: {score}")
        return score

    def summarize_response_time(
        self, health_check_results: Dict[str, List[HealthCheckResult]]
    ) -> float:
        """Calculates response time outlier score using IQR."""
        score: float = 0.0
        total = 0
        for _, results in health_check_results.items():
            response_times = [r.response_time for r in results if r.success]

            if len(response_times) < 4:
                continue

            q1 = np.percentile(response_times, 25)
            q3 = np.percentile(response_times, 75)
            iqr = q3 - q1
            upper_bound = q3 + (1.5 * iqr)

            outliers = [t for t in response_times if t > upper_bound]
            score += len(outliers)
            total += len(results)

        if total == 0:
            return 0.0
        score = (score / total) * 10.0
        logger.debug(f"Response time outlier score: {score}")
        return score
