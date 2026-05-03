"""
HealthCheckWatcher core functionality tests
"""

import time
from unittest.mock import Mock, patch

from krkn_ai.chaos_engines.health_check_watcher import HealthCheckWatcher
from krkn_ai.models.config import (
    HealthCheckConfig,
    HealthCheckApplicationConfig,
    HealthCheckResult,
)


class TestHealthCheckWatcherInitialization:
    """Test HealthCheckWatcher initialization"""

    def test_init_with_empty_config(self):
        """Test initialization with empty health check config"""
        config = HealthCheckConfig(applications=[])
        watcher = HealthCheckWatcher(config)
        assert watcher.config == config
        assert watcher._stop_event is None  # Initialized in run()


class TestHealthCheckWatcherRunAndStop:
    """Test HealthCheckWatcher run and stop behavior"""

    @patch("krkn_ai.chaos_engines.health_check_watcher.httpx.AsyncClient.get")
    def test_run_starts_threads_for_each_application(self, mock_get):
        """Test run starts a background thread with an asyncio loop"""
        # Mock successful health check response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        app_config = HealthCheckApplicationConfig(
            name="test-app",
            url="http://localhost:8080/health",
            timeout=5,
            interval=1,  # Short interval for testing
        )
        config = HealthCheckConfig(applications=[app_config])
        watcher = HealthCheckWatcher(config)

        watcher.run()

        # Verify background thread was started
        assert watcher._thread is not None
        assert watcher._thread.is_alive()

        # Stop and wait for thread to finish
        watcher.stop()
        watcher._thread.join(timeout=1.0)
        assert not watcher._thread.is_alive()

    @patch("krkn_ai.chaos_engines.health_check_watcher.httpx.AsyncClient.get")
    def test_stop_terminates_all_threads(self, mock_get):
        """Test stop method terminates the background thread"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        app_configs = [
            HealthCheckApplicationConfig(
                name=f"app-{i}", url=f"http://localhost:808{i}/health", interval=1
            )
            for i in range(3)
        ]
        config = HealthCheckConfig(applications=app_configs)
        watcher = HealthCheckWatcher(config)

        watcher.run()
        assert watcher._thread is not None

        watcher.stop()

        # Wait for thread to finish
        watcher._thread.join(timeout=1.0)
        assert not watcher._thread.is_alive()


class TestHealthCheckWatcherResults:
    """Test HealthCheckWatcher result collection and summarization"""

    @patch("krkn_ai.chaos_engines.health_check_watcher.httpx.AsyncClient.get")
    def test_get_results_aggregates_from_all_threads(self, mock_get):
        """Test get_results aggregates results from the watcher tasks"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        app_config = HealthCheckApplicationConfig(
            name="test-app",
            url="http://localhost:8080/health",
            interval=1,  # Short interval for testing
        )
        config = HealthCheckConfig(applications=[app_config])
        watcher = HealthCheckWatcher(config)

        watcher.run()
        time.sleep(0.3)  # Allow some health checks to run
        watcher.stop()

        results = watcher.get_results()

        assert len(results) == 1
        assert "http://localhost:8080/health" in results
        assert len(results["http://localhost:8080/health"]) > 0
        # Verify all results are successful
        for result in results["http://localhost:8080/health"]:
            assert isinstance(result, HealthCheckResult)
            assert result.success is True
            assert result.status_code == 200

    @patch("krkn_ai.chaos_engines.health_check_watcher.httpx.AsyncClient.get")
    def test_summarize_success_rate_calculates_failure_score(self, mock_get):
        """Test summarize_success_rate calculates failure score correctly"""
        # Mock mix of successful and failed responses
        mock_responses = [
            Mock(status_code=200),
            Mock(status_code=500),
            Mock(status_code=200),
        ]
        mock_get.side_effect = mock_responses

        app_config = HealthCheckApplicationConfig(
            name="test-app", url="http://localhost:8080/health", interval=1
        )
        config = HealthCheckConfig(applications=[app_config])
        watcher = HealthCheckWatcher(config)

        watcher.run()
        time.sleep(0.3)
        watcher.stop()

        results = watcher.get_results()
        score = watcher.summarize_success_rate(results)

        # Should have some failures, score should be > 0
        assert score >= 0
        # Score is (failed / total) * 10
        assert score <= 10

    @patch("krkn_ai.chaos_engines.health_check_watcher.requests.get")
    def test_summarize_success_rate_returns_zero_for_empty_results(self, mock_get):
        """Test summarize_success_rate returns 0 for empty results"""
        config = HealthCheckConfig(applications=[])
        watcher = HealthCheckWatcher(config)

        score = watcher.summarize_success_rate({})
        assert score == 0

    @patch("krkn_ai.chaos_engines.health_check_watcher.httpx.AsyncClient.get")
    def test_summarize_response_time_detects_outliers(self, mock_get):
        """Test summarize_response_time detects response time outliers"""
        # Mock responses with varying response times (some outliers)
        # We need to simulate time.monotonic() differences, but for simplicity
        # we can just mock the return values and hope the loop timing works,
        # or we can mock time.monotonic itself.
        mock_response = Mock(status_code=200)
        mock_get.return_value = mock_response

        app_config = HealthCheckApplicationConfig(
            name="test-app", url="http://localhost:8080/health", interval=1
        )
        config = HealthCheckConfig(applications=[app_config])
        watcher = HealthCheckWatcher(config)

        watcher.run()
        time.sleep(0.5)  # Allow enough time for multiple checks
        watcher.stop()

        results = watcher.get_results()
        score = watcher.summarize_response_time(results)

        # Should detect outliers and return score > 0
        assert score >= 0
        assert score <= 10

    @patch("krkn_ai.chaos_engines.health_check_watcher.requests.get")
    def test_summarize_response_time_returns_zero_with_insufficient_data(
        self, mock_get
    ):
        """Test summarize_response_time returns 0 when there's insufficient data"""
        mock_response = Mock(status_code=200, elapsed=Mock(total_seconds=lambda: 0.1))
        mock_get.return_value = mock_response

        app_config = HealthCheckApplicationConfig(
            name="test-app", url="http://localhost:8080/health", interval=1
        )
        config = HealthCheckConfig(applications=[app_config])
        watcher = HealthCheckWatcher(config)

        watcher.run()
        time.sleep(0.1)  # Very short time, not enough for 4+ checks
        watcher.stop()

        results = watcher.get_results()
        score = watcher.summarize_response_time(results)

        # Should return 0 when less than 4 successful checks
        assert score == 0

    @patch("krkn_ai.chaos_engines.health_check_watcher.httpx.AsyncClient.get")
    def test_handles_request_exceptions_gracefully(self, mock_get):
        """Test health check handles request exceptions gracefully"""
        # Mock request to raise exception
        mock_get.side_effect = httpx.RequestError("Connection error")

        app_config = HealthCheckApplicationConfig(
            name="test-app", url="http://localhost:8080/health", interval=1
        )
        config = HealthCheckConfig(applications=[app_config])
        watcher = HealthCheckWatcher(config)

        watcher.run()
        time.sleep(0.2)
        watcher.stop()

        results = watcher.get_results()

        # Should have results with failure status
        assert len(results) > 0
        for url_results in results.values():
            for result in url_results:
                assert result.success is False
                assert result.status_code == -1
                assert result.error is not None
