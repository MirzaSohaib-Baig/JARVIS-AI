from pathlib import Path

# import subprocess
# import sys
# import threading

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
import uvicorn
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
# from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from schema.chatSchema import ChatRequest, ChatResponse
from schema.backgroundTasksSchema import BackgroundTaskRequest

from brain.orchestrator import handle_message
from tools.background_tasks import get_background_manager, TaskType
from config.browser_automation import browser_manager
from tools.work_matcher_tool import upload_cv

app = FastAPI(title="JARVIS")

CV_DIR = Path(settings.CV_PATH)
CV_DIR.mkdir(parents=True, exist_ok=True)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

HUD_PATH = Path(__file__).parent /"hud"

app.mount("/static", StaticFiles(directory=HUD_PATH), name="static")

background_manager = None

@app.on_event("startup")
async def startup_event():
    """Initialize background task manager on server startup."""
    global background_manager
    background_manager = get_background_manager()
    print("[JARVIS] Background intelligence system initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up background tasks on server shutdown."""
    global background_manager
    if background_manager:
        background_manager.stop()


# ─── Chat Endpoint ───────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = handle_message(request.message, request.history, session_id=request.session_id)
    updated_history = request.history + [
        {"role": "user", "content": request.message}, 
        {"role": "assistant", "content": result["reply"]}
        ]
    return ChatResponse(reply=result["reply"], history=updated_history, cards=result["cards"])

# ─── Background Task Endpoints ───────────────────────────────────────────
@app.post("/background/tasks")
async def create_background_task(request: BackgroundTaskRequest):
    """
    Create a new background task.
    
    Types:
    - job_search: Search for job opportunities
    - freelance: Find freelance work
    - trend_monitor: Monitor trending topics
    - news_digest: Daily news summary
    - tech_watch: Monitor tech trends
    - custom_research: Custom research topic
    """
    global background_manager
    if not background_manager:
        background_manager = get_background_manager()
    
    try:
        task_type = TaskType(request.type)
        task = background_manager.create_task(
            task_type=task_type,
            query=request.query,
            interval_hours=request.interval_hours
        )
        return JSONResponse(content={
            "status": "success",
            "message": f"Background task created: {task.type.value} for '{task.query}'",
            "task": task.to_dict()
        })
    except ValueError:
        valid_types = [t.value for t in TaskType]
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": f"Invalid task type. Valid types: {valid_types}"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to create task: {str(e)}"}
        )


@app.get("/background/tasks")
async def list_background_tasks():
    """List all active background tasks."""
    global background_manager
    if not background_manager:
        background_manager = get_background_manager()
    
    tasks = [task.to_dict() for task in background_manager.tasks.values()]
    return JSONResponse(content={"tasks": tasks})


@app.delete("/background/tasks/{task_id}")
async def delete_background_task(task_id: str):
    """Delete a background task."""
    global background_manager
    if not background_manager:
        background_manager = get_background_manager()
    
    if task_id in background_manager.tasks:
        del background_manager.tasks[task_id]
        return JSONResponse(content={"status": "success", "message": "Task deleted"})
    
    return JSONResponse(
        status_code=404,
        content={"status": "error", "message": "Task not found"}
    )


@app.get("/background/briefing")
async def get_morning_briefing():
    """Get the daily briefing summary."""
    global background_manager
    if not background_manager:
        background_manager = get_background_manager()
    
    briefing = background_manager.get_morning_briefing()
    return JSONResponse(content={"briefing": briefing})

# ─── CV Endpoints ──────────────────────────────────────────────────
@app.post("/cv/upload")
async def upload_cv_file(file: UploadFile = File(...)):
    if file.content_type not in [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]:
        raise HTTPException(status_code=400, detail="Invalid file type")
    file_path = CV_DIR / file.filename
    contents = await file.read()
    file_path.write_bytes(contents)
    result = upload_cv(file_path)
    return JSONResponse(content=result)


# ─── Browser Automation Endpoints ───────────────────────────────────────
@app.get("/open-browser")
async def open_external_browser(
    url: str = Query(...), 
    width: int = Query(600),
    height: int = Query(450),
    left: int = Query(100),
    top: int = Query(100),
    window_id: str | None = Query(None),
):
    try:
        opened_id = await browser_manager.open(url=url, left=left, top=top, width=width, height=height, window_id=window_id)

        return {"status": "success", "window_id": opened_id, "opened": url, "engine": "playwright"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/close-browser")
async def close_external_browser(window_id: str = Query(...)):
    try:
        closed = await browser_manager.close(window_id)
        return {"status": "success" if closed else "not_found", "closed": window_id, "engine": "playwright"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/close-all-browsers")
async def close_all_external_browsers():
    try:
        await browser_manager.close_all()
        return {"status": "success", "message": "Closed all windows", "engine": "playwright"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ## ─── Video Player Endpoint ─────────────────────────────────────────────
# @app.get("/video-player")
# async def video_player(embed_url: str = "", title: str = "JARVIS Video Player"):
#     """Serve a video player page for native windows."""
#     # Extract video ID for clean embed URL
#     video_id = ""
#     if "youtube.com/embed/" in embed_url:
#         video_id = embed_url.split("youtube.com/embed/")[-1].split("?")[0]
#     elif "watch?v=" in embed_url:
#         video_id = embed_url.split("watch?v=")[-1].split("&")[0]
#     elif "youtu.be/" in embed_url:
#         video_id = embed_url.split("youtu.be/")[-1].split("?")[0]
    
#     if video_id:
#         embed_src = f"https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0&modestbranding=1&enablejsapi=1"
#     else:
#         embed_src = embed_url
    
#     html = f"""<!DOCTYPE html>
# <html>
# <head>
#     <meta charset="UTF-8">
#     <style>
#         * {{ margin: 0; padding: 0; box-sizing: border-box; }}
#         body {{ 
#             background: #000; 
#             display: flex; 
#             align-items: center; 
#             justify-content: center;
#             height: 100vh;
#             overflow: hidden;
#         }}
#         iframe {{
#             width: 100%;
#             height: 100%;
#             border: none;
#         }}
#     </style>
# </head>
# <body>
#     <iframe 
#         src="{embed_src}" 
#         allow="autoplay; encrypted-media; fullscreen" 
#         allowfullscreen>
#     </iframe>
# </body>
# </html>"""
#     return HTMLResponse(content=html)

# ─── HUD Endpoint ─────────────────────────────────────────────────────
@app.get("/")
async def get_hud():
    """Serve the JARVIS HUD HTML file."""
    html_file = HUD_PATH / "jarvis-hud.html"
    if not html_file.exists():
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": "HUD file not found"}
        )
    return FileResponse(html_file)


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)