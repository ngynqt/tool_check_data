"""
Comprehensive test suite for the FastGreet pipeline.

Covers:
  1. API endpoint validation (valid + invalid payloads)
  2. Async queue/worker integration (mocked automation layer)
  3. Playwright browser lifecycle (headless launch against a real URL)
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.makedirs("logs", exist_ok=True)

from src.main import app
from src.pipeline import link_queue, link_worker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    """Async HTTP client bound to the FastAPI app (no real server needed)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(autouse=True)
def drain_queue():
    """Drain the shared queue before every test to avoid cross-contamination."""
    while not link_queue.empty():
        link_queue.get_nowait()
        link_queue.task_done()
    yield
    while not link_queue.empty():
        link_queue.get_nowait()
        link_queue.task_done()


# ===========================================================================
# 1. API ENDPOINT TESTS
# ===========================================================================

class TestIngestLinksEndpoint:
    """Unit tests for POST /ingest-links."""

    async def test_valid_payload_returns_202(self, client):
        """Valid URL list should return HTTP 202 with correct count."""
        payload = {
            "links": [
                "https://www.facebook.com/user.one",
                "https://www.facebook.com/user.two",
                "https://www.facebook.com/user.three",
            ]
        }
        response = await client.post("/ingest-links", json=payload)

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "Success"
        assert "3" in body["message"]

    async def test_valid_payload_enqueues_links(self, client):
        """Links from a valid payload must appear in the asyncio.Queue."""
        urls = [
            "https://www.facebook.com/alpha",
            "https://www.facebook.com/bravo",
        ]
        await client.post("/ingest-links", json={"links": urls})

        assert link_queue.qsize() == 2

        queued = []
        while not link_queue.empty():
            queued.append(link_queue.get_nowait())
            link_queue.task_done()

        for url in urls:
            assert any(url in q for q in queued), f"{url} not found in queue"

    async def test_invalid_url_returns_422(self, client):
        """Non-URL strings should trigger Pydantic validation -> HTTP 422."""
        payload = {"links": ["not_a_url", "also_bad"]}
        response = await client.post("/ingest-links", json=payload)
        assert response.status_code == 422

    async def test_missing_field_returns_422(self, client):
        """Omitting the required 'links' field should return HTTP 422."""
        response = await client.post("/ingest-links", json={"wrong_key": []})
        assert response.status_code == 422

    async def test_empty_links_returns_202(self, client):
        """An empty list is structurally valid; expect HTTP 202 with count 0."""
        response = await client.post("/ingest-links", json={"links": []})
        assert response.status_code == 202
        assert "0" in response.json()["message"]
        assert link_queue.qsize() == 0

    async def test_health_endpoint(self, client):
        """GET /health should return service status and queue size."""
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert "queue_size" in body


# ===========================================================================
# 2. QUEUE & WORKER INTEGRATION TESTS
# ===========================================================================

class TestWorkerIntegration:
    """Integration tests verifying the background worker picks up queued links."""

    async def test_worker_calls_send_facebook_message(self, client):
        """
        After ingesting links, the background worker should invoke
        send_facebook_message_with_context with the exact URLs that were queued.
        """
        mock_playwright = MagicMock()
        mock_playwright.return_value = AsyncMock()
        mock_send = AsyncMock()
        urls = [
            "https://www.facebook.com/test.user.1",
            "https://www.facebook.com/test.user.2",
        ]

        with patch("src.pipeline.async_playwright", mock_playwright), \
             patch("src.pipeline.send_facebook_message_with_context", mock_send):
            await client.post("/ingest-links", json={"links": urls})

            worker_task = asyncio.create_task(link_worker())
            await asyncio.sleep(0.3)
            worker_task.cancel()

        assert mock_send.call_count == 2
        # Note: call.args[0] is the persistent browser context, call.args[1] is the fb_link
        called_args = [call.args[1] for call in mock_send.call_args_list]
        for url in urls:
            assert any(url in arg for arg in called_args), (
                f"send_facebook_message_with_context was never called with {url}"
            )

    async def test_worker_handles_exception_gracefully(self, client):
        """
        If send_facebook_message_with_context raises, the worker should log the error
        and continue processing without crashing.
        """
        mock_playwright = MagicMock()
        mock_playwright.return_value = AsyncMock()
        call_count = 0

        async def flaky_send(context, link: str):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated browser crash")

        with patch("src.pipeline.async_playwright", mock_playwright), \
             patch("src.pipeline.send_facebook_message_with_context", side_effect=flaky_send):
            await client.post("/ingest-links", json={
                "links": [
                    "https://www.facebook.com/will.fail",
                    "https://www.facebook.com/will.succeed",
                ]
            })

            worker_task = asyncio.create_task(link_worker())
            await asyncio.sleep(0.3)
            worker_task.cancel()

        assert call_count == 2, "Worker must continue after an exception"

    async def test_queue_is_drained_after_processing(self, client):
        """After the worker finishes, the queue should be empty."""
        mock_playwright = MagicMock()
        mock_playwright.return_value = AsyncMock()
        mock_send = AsyncMock()

        with patch("src.pipeline.async_playwright", mock_playwright), \
             patch("src.pipeline.send_facebook_message_with_context", mock_send):
            await client.post("/ingest-links", json={
                "links": ["https://www.facebook.com/drain.test"]
            })

            worker_task = asyncio.create_task(link_worker())
            await asyncio.sleep(0.3)
            worker_task.cancel()

        assert link_queue.empty(), "Queue should be empty after worker processes all links"


# ===========================================================================
# 3. PLAYWRIGHT BROWSER LIFECYCLE TEST
# ===========================================================================

class TestPlaywrightBrowser:
    """
    Standalone UI tests that validate Playwright can launch, navigate,
    and shut down cleanly without relying on the FastAPI server.
    """

    async def test_headless_launch_and_navigation(self):
        """
        Launch Chromium in headless mode, navigate to a known-good URL,
        verify the page loaded, then close gracefully.
        """
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            response = await page.goto("https://httpbin.org/get")
            assert response is not None
            assert response.status == 200

            content = await page.content()
            assert "httpbin" in content.lower() or "origin" in content.lower()

            await browser.close()

    async def test_browser_closes_on_navigation_error(self):
        """
        Navigating to an unreachable URL should raise an exception,
        but the browser must still close cleanly in the finally block.
        """
        from playwright.async_api import async_playwright

        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                with pytest.raises(Exception):
                    await page.goto(
                        "https://this-domain-does-not-exist-fastgreet-test.invalid",
                        timeout=5000,
                    )
        finally:
            if browser:
                await browser.close()


class TestTaskTrackerEndpoints:
    """Unit tests for the new task tracking REST endpoints."""

    async def test_get_tasks_returns_list(self, client):
        """GET /tasks should return a list of all tasks currently in the tracker."""
        response = await client.get("/tasks")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)

    async def test_ingested_links_have_tasks(self, client):
        """Ingesting links should create matching tasks with 'queued' status."""
        links = ["https://www.facebook.com/tracker.test.1"]
        resp_post = await client.post("/ingest-links", json={"links": links})
        assert resp_post.status_code == 202
        body_post = resp_post.json()
        
        task_ids = body_post["task_ids"]
        assert len(task_ids) == 1
        
        task_id = list(task_ids.values())[0]
        
        # Verify specific task retrieval
        resp_get = await client.get(f"/tasks/{task_id}")
        assert resp_get.status_code == 200
        task_data = resp_get.json()
        assert task_data["task_id"] == task_id
        assert task_data["link"] == links[0]
        assert task_data["status"] == "queued"

    async def test_get_nonexistent_task_returns_404(self, client):
        """Querying a fake/nonexistent task_id should return HTTP 404."""
        response = await client.get("/tasks/non_existent_id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
