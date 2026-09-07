import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from apscheduler.schedulers.background import BackgroundScheduler

from brain.orchestrator import handle_message
from config.settings import settings
from tools import cv_matcher_tool, news  # Import your existing news tool

BRIEFINGS_DIR = Path(settings.BRIEFINGS_PATH) if hasattr(settings, 'BRIEFINGS_PATH') else Path(__file__).parent.parent / "data" / "briefings"
BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)


class TaskType(Enum):
    JOB_SEARCH = "job_search"
    FREELANCE = "freelance_search"
    TREND_MONITOR = "trend_monitor"
    NEWS_DIGEST = "news_digest" 
    CUSTOM_RESEARCH = "custom_research"
    TECH_WATCH = "tech_watch",
    JOB_MATCHER = "job_matcher"


@dataclass
class BackgroundTask:
    """A scheduled task JARVIS runs autonomously."""
    id: str
    type: TaskType
    query: str
    interval_hours: float
    last_run: Optional[datetime] = None
    results: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "query": self.query,
            "interval_hours": self.interval_hours,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "results": self.results[-5:],  # Last 5 results for briefing
            "created_at": self.created_at.isoformat(),
        }


class BackgroundTaskManager:
    """Manages background tasks and generates daily briefings."""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.tasks: Dict[str, BackgroundTask] = {}
        self._setup_default_tasks()
        self.scheduler.start()
        print("[JARVIS] Background intelligence system online")
    
    def _setup_default_tasks(self):
        """Create default tasks that provide daily value."""
        defaults = [
            {
                "type": TaskType.TECH_WATCH,
                "query": "emerging technologies and developer trends",
                "interval_hours": 0.5,
            },
            {
                "type": TaskType.JOB_SEARCH,
                "query": "remote software developer jobs high paying",
                "interval_hours": 0.5,
            },
            {
                "type": TaskType.NEWS_DIGEST,
                "query": "tech industry important developments",
                "interval_hours": 0.5,
            },
        ]
        
        for config in defaults:
            task_id = f"{config['type'].value}_default"
            if task_id not in self.tasks:
                task = BackgroundTask(
                    id=task_id,
                    type=config["type"],
                    query=config["query"],
                    interval_hours=config["interval_hours"],
                )
                self.tasks[task_id] = task
                self._schedule_task(task)
    
    def _schedule_task(self, task: BackgroundTask):
        """Schedule a task to run every X hours."""
        self.scheduler.add_job(
            func=self._run_task,
            args=[task.id],
            trigger="interval",
            hours=task.interval_hours,
            id=task.id,
            replace_existing=True,
        )
    
    def create_task(self, task_type: TaskType, query: str, interval_hours: float = 0.5) -> BackgroundTask:
        """Create a new background task."""
        task_id = f"{task_type.value}_{int(time.time())}"
        task = BackgroundTask(
            id=task_id,
            type=task_type,
            query=query,
            interval_hours=interval_hours,
        )
        self.tasks[task_id] = task
        self._schedule_task(task)
        return task
    
    def _run_task(self, task_id: str):
        """Run a single background task."""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        print(f"[JARVIS] Running: {task.type.value} — {task.query}")
        
        try:
            result = self._execute_task(task)
            task.last_run = datetime.now()
            task.results.append({
                "timestamp": datetime.now().isoformat(),
                "data": result,
            })
            print(f"[JARVIS] Completed: {task.type.value}")
        except Exception as e:
            print(f"[JARVIS] Task failed {task.type.value}: {e}")
    
    def _execute_task(self, task: BackgroundTask) -> Dict:
        """Execute the actual work for a task using news tools + AI summary."""

        if task.type == TaskType.JOB_MATCHER:
            jobs = cv_matcher_tool.find_matching_jobs(limit=10)
            return {
                "query": task.query,
                "jobs": jobs,
                "summary": f"Found {len(jobs)} job opportunities matching your criteria.",
                "timestamp": datetime.now().isoformat(),
            }

        if task.type == TaskType.FREELANCE:
            opportunities = cv_matcher_tool.find_freelance_opportunities(limit=10)
            return {
                "query": task.query,
                "jobs": jobs,
                "summary": f"Found {len(opportunities)} freelance opportunities matching your criteria.",
                "timestamp": datetime.now().isoformat(),
            }
        
        # Collect raw data based on task type
        raw_data = self._collect_raw_data(task)
        
        # Use AI to summarize and extract actionable insights
        summary = self._summarize_with_ai(task, raw_data)
        
        return {
            "query": task.query,
            "raw_data": raw_data,
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
        }
    
    def _collect_raw_data(self, task: BackgroundTask) -> Dict:
        """Collect raw data using existing news tools."""
        data = {
            "world_news": [],
            "tech_news": [],
            "hacker_news": [],
            "search_results": [],
        }
        
        try:
            if task.type == TaskType.NEWS_DIGEST:
                data["world_news"] = news.get_world_news(limit=5)
                data["tech_news"] = news.get_tech_news(limit=5)
                data["hacker_news"] = news.get_hacker_news_trends(limit=5)
            
            elif task.type == TaskType.TECH_WATCH:
                data["tech_news"] = news.get_tech_news(limit=8)
                data["hacker_news"] = news.get_hacker_news_trends(limit=10)
                data["search_results"] = news.search_world_news(task.query, limit=5)
            
            elif task.type == TaskType.JOB_SEARCH:
                data["search_results"] = news.search_world_news(task.query, limit=8)
            
            elif task.type == TaskType.FREELANCE:
                data["search_results"] = news.search_world_news(f"freelance {task.query}", limit=8)
            
            elif task.type == TaskType.CUSTOM_RESEARCH:
                data["search_results"] = news.search_world_news(task.query, limit=6)
                data["tech_news"] = news.get_tech_news(limit=3)
            
        except Exception as e:
            print(f"[JARVIS] Data collection failed: {e}")
        
        return data
    
    def _summarize_with_ai(self, task: BackgroundTask, raw_data: Dict) -> str:
        """Use AI to create a meaningful summary from raw data."""
        
        # Build a prompt with the raw data
        data_summary = []
        
        if raw_data.get("tech_news"):
            data_summary.append("Tech News:")
            for item in raw_data["tech_news"][:3]:
                data_summary.append(f"- {item.get('title', '')}")
        
        if raw_data.get("hacker_news"):
            data_summary.append("\nDeveloper Trends (Hacker News):")
            for item in raw_data["hacker_news"][:3]:
                data_summary.append(f"- {item.get('title', '')} (Score: {item.get('score', '?')})")
        
        if raw_data.get("search_results"):
            data_summary.append(f"\nSearch Results for '{task.query}':")
            for item in raw_data["search_results"][:5]:
                data_summary.append(f"- {item.get('title', '')}")
        
        if raw_data.get("world_news"):
            data_summary.append("\nWorld News:")
            for item in raw_data["world_news"][:3]:
                data_summary.append(f"- {item.get('title', '')}")
        
        data_text = "\n".join(data_summary) if data_summary else "No data collected"
        
        # Build prompt for AI
        prompt_map = {
            TaskType.TECH_WATCH: f"Based on this data:\n{data_text}\n\nProvide a concise summary of: 1) What technologies are trending, 2) What skills are in demand, 3) What should I learn next. Be specific and actionable.",
            
            TaskType.JOB_SEARCH: f"Based on this job search data:\n{data_text}\n\nProvide: 1) Top job opportunities found, 2) Required skills, 3) Salary insights, 4) Direct application recommendations.",
            
            TaskType.NEWS_DIGEST: f"Based on this news:\n{data_text}\n\nProvide a morning briefing: 1) 3 most important news items, 2) Why they matter, 3) What action I should take.",
            
            TaskType.FREELANCE: f"Based on this freelance data:\n{data_text}\n\nProvide: 1) Best freelance opportunities, 2) Platforms to use, 3) Pricing strategy, 4) How to compete.",
            
            TaskType.CUSTOM_RESEARCH: f"Based on this research:\n{data_text}\n\nProvide a comprehensive summary with: 1) Key findings, 2) Trends, 3) Recommendations, 4) Next steps.",
        }
        
        prompt = prompt_map.get(task.type, f"Summarize this data:\n{data_text}")
        
        try:
            # Use orchestrator for AI-powered summary
            result = handle_message(
                prompt,
                session_id=f"background-{task.id}"
            )
            return result.get("reply", "Unable to generate summary.")
        except Exception as e:
            print(f"[JARVIS] AI summary failed: {e}")
            return "Summary generation failed. Raw data available."
    
    def get_morning_briefing(self) -> str:
        """Generate a comprehensive morning briefing."""
        briefing_parts = []
        briefing_parts.append("🌅 GOOD MORNING, SIR.")
        briefing_parts.append("Here's your overnight intelligence briefing:\n")
        
        for task in self.tasks.values():
            if task.last_run and (datetime.now() - task.last_run) < timedelta(hours=24):
                task_label = task.type.value.replace("_", " ").title()
                briefing_parts.append(f"\n📌 {task_label}: {task.query}")
                briefing_parts.append("-" * 40)
                
                if task.results:
                    latest = task.results[-1]
                    summary = latest.get("data", {}).get("summary", "No summary available")
                    briefing_parts.append(summary)
                else:
                    briefing_parts.append("No results yet. Will update soon.")
                
                briefing_parts.append("")
        
        briefing_parts.append("=" * 40)
        briefing_parts.append("💡 Ask me for details on any topic.")
        
        return "\n".join(briefing_parts)
    
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()


# Singleton
background_manager: Optional[BackgroundTaskManager] = None


def get_background_manager() -> BackgroundTaskManager:
    global background_manager
    if background_manager is None:
        background_manager = BackgroundTaskManager()
    return background_manager

def initialize_background_tasks():
    """Initialize the background task manager and start default tasks."""
    manager = get_background_manager()
    print(f"[JARVIS] Background tasks initialized: {len(manager.tasks)} tasks scheduled.")
    return manager