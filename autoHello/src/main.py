import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from pydantic import BaseModel, HttpUrl
from src.pipeline import link_queue, link_worker
from src.tracker import tracker, TaskStatus

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/system.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("FastGreet")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manages startup and shutdown lifecycle of the background worker."""
    worker_task = asyncio.create_task(link_worker())
    logger.info("FastGreet pipeline is online.")
    yield
    worker_task.cancel()
    logger.info("FastGreet pipeline shutting down.")


app = FastAPI(
    title="FastGreet API",
    version="1.0.0",
    description="Lightweight automated Facebook messaging pipeline backend.",
    lifespan=lifespan,
)


class LinkPayload(BaseModel):
    links: list[HttpUrl]


class IngestLinksResponse(BaseModel):
    status: str
    message: str
    task_ids: dict[str, str]


class HealthCheckResponse(BaseModel):
    status: str
    queue_size: int


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Returns service status and current queue depth."""
    return {
        "status": "healthy",
        "queue_size": link_queue.qsize(),
    }


@app.post("/ingest-links", status_code=status.HTTP_202_ACCEPTED, response_model=IngestLinksResponse)
async def ingest_links(payload: LinkPayload):
    """Ingests Facebook profile links and queues them for background processing."""
    added_count = 0
    task_ids = {}
    for link in payload.links:
        link_str = str(link)
        task_id = tracker.create_task(link_str)
        task_ids[link_str] = task_id
        await link_queue.put((task_id, link_str))
        added_count += 1

    return {
        "status": "Success",
        "message": f"Successfully queued {added_count} profile link(s) for execution.",
        "task_ids": task_ids,
    }


@app.get("/tasks", response_model=list[TaskStatus])
async def get_tasks():
    """Returns the list of all queued, running, completed, or failed tasks."""
    return tracker.get_all_tasks()


@app.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_by_id(task_id: str):
    """Returns the status of a specific task by its short ID."""
    from fastapi import HTTPException
    task = tracker.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found."
        )
    return task