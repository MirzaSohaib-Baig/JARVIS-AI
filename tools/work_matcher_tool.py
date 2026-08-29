"""
cv_job_matcher.py
Finds jobs and freelance projects that match your CV.
"""

import re
import requests
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from config.settings import settings

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    from docx import Document
except ImportError:
    Document = None


# ─────────────────────────────────────────────
# CV PATH HANDLING
# ─────────────────────────────────────────────

# The directory where CVs are stored
CV_DIR = Path(settings.CV_PATH) if hasattr(settings, 'CV_PATH') else Path(__file__).parent.parent / "data" / "cv"
CV_DIR.mkdir(parents=True, exist_ok=True)

# Supported CV file extensions
SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt', '.md']


def find_cv_file() -> Optional[Path]:
    """
    Find the most recently modified CV file in the CV directory.
    Returns None if no CV file is found.
    """
    if not CV_DIR.exists():
        CV_DIR.mkdir(parents=True, exist_ok=True)
        return None
    
    # Look for files with supported extensions
    cv_files = []
    for ext in SUPPORTED_EXTENSIONS:
        cv_files.extend(CV_DIR.glob(f"*{ext}"))
    
    # Also check for files without extension
    cv_files.extend([f for f in CV_DIR.iterdir() if f.is_file() and f.suffix.lower() not in SUPPORTED_EXTENSIONS])
    
    if not cv_files:
        print(f"[JARVIS] No CV file found in {CV_DIR}")
        print(f"[JARVIS] Please upload your CV to: {CV_DIR}")
        return None
    
    # Return the most recently modified file
    cv_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return cv_files[0]


@dataclass
class Opportunity:
    title: str
    company: str
    url: str
    source: str
    score: float
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    location: str = "Remote"
    type: str = "job"
    salary: str = ""

    def to_dict(self):
        return {
            "title": self.title,
            "company": self.company,
            "url": self.url,
            "source": self.source,
            "score": self.score,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "location": self.location,
            "type": self.type,
            "salary": self.salary,
        }


class CVParser:

    SKILLS = [
        "python", "javascript", "typescript", "java",
        "react", "next.js", "vue", "node.js",
        "express.js", "fastapi", "django", "flask",
        "sql", "postgresql", "mysql", "mongodb",
        "redis", "docker", "aws",
        "tensorflow", "pytorch", "machine learning",
        "nlp", "rest api", "graphql",
        "html", "css", "tailwind",
        "git", "github", "ci/cd",
        "kubernetes", "terraform", "go", "rust",
        "c++", "c#", "flutter", "swift", "kotlin",
    ]

    def parse(self, path: Optional[str] = None):
        """
        Parse a CV from a file path or auto-discover from the CV directory.
        Returns a profile dict with skills and experience.
        """
        # Determine which file to parse
        if path:
            cv_file = Path(path)
            if not cv_file.exists():
                print(f"[JARVIS] CV file not found: {path}")
                return self._default_profile()
            if cv_file.is_dir():
                print(f"[JARVIS] Path is a directory, not a file: {path}")
                cv_file = find_cv_file()
                if not cv_file:
                    return self._default_profile()
        else:
            cv_file = find_cv_file()
            if not cv_file:
                return self._default_profile()
        
        print(f"[JARVIS] Parsing CV: {cv_file}")
        
        text = self._read(cv_file).lower()
        
        if not text:
            print("[JARVIS] Failed to extract text from CV")
            return self._default_profile()
        
        skills = [
            skill for skill in self.SKILLS
            if skill.lower() in text
        ]
        
        experience = self._get_experience(text)
        role_title = self._get_role_title(text)
        
        print(f"[JARVIS] Found {len(skills)} skills: {skills}")
        print(f"[JARVIS] Experience: {experience} years")
        
        return {
            "skills": skills,
            "experience_years": experience,
            "role_title": role_title,
            "cv_path": str(cv_file),
        }

    def _default_profile(self) -> dict:
        """Return a default profile when no CV is available."""
        print("[JARVIS] Using default profile (no CV found)")
        return {
            "skills": ["python", "javascript", "react", "node.js", "sql", "docker"],
            "experience_years": 3,
            "role_title": "software developer",
            "cv_path": None,
        }

    def _read(self, path: Path) -> str:
        """Extract text from PDF, DOCX, or TXT file."""
        suffix = path.suffix.lower()
        
        try:
            if suffix == '.pdf' and PyPDF2:
                with open(path, "rb") as file:
                    reader = PyPDF2.PdfReader(file)
                    return "\n".join(
                        page.extract_text() or ""
                        for page in reader.pages
                    )
            
            elif suffix == '.docx' and Document:
                doc = Document(str(path))
                return "\n".join(
                    paragraph.text
                    for paragraph in doc.paragraphs
                )
            
            elif suffix in ['.txt', '.md', '']:
                return path.read_text(errors="ignore")
            
            else:
                # Try to read as text anyway
                try:
                    return path.read_text(errors="ignore")
                except Exception:
                    print(f"[JARVIS] Unsupported file type: {suffix}")
                    return ""
        except Exception as e:
            print(f"[JARVIS] Failed to read CV: {e}")
            return ""

    def _get_experience(self, text: str) -> int:
        """Extract years of experience from CV text."""
        match = re.search(
            r"(\d+)\+?\s*years?\s*(?:of)?\s*experience",
            text
        )
        return int(match.group(1)) if match else 0

    def _get_role_title(self, text: str) -> str:
        """Extract role title from CV text."""
        patterns = [
            r'(senior|junior|lead|principal)?\s*(software|web|frontend|backend|fullstack|full stack|devops|data|ml|ai)\s*(developer|engineer|architect|scientist|analyst)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        return ""


class JobMatcher:

    def __init__(self, profile: dict):
        self.skills = profile.get("skills", [])
        self.experience_years = profile.get("experience_years", 0)
        self.role_title = profile.get("role_title", "")
        
        if not self.skills:
            print("[JARVIS] Warning: No skills found in profile")
            self.skills = ["python", "javascript", "react", "node.js", "sql", "docker"]

    def search_jobs(self, limit: int = 10) -> List[Opportunity]:
        """Search for jobs matching the CV profile."""
        jobs = []
        
        jobs += self._remotive()
        jobs += self._remoteok()
        
        # If no jobs found, try a broader search
        if not jobs:
            jobs += self._search_duckduckgo_jobs()
        
        ranked = self._rank(jobs)
        return ranked[:limit]

    def search_freelance(self, limit: int = 10) -> List[Opportunity]:
        """Search for freelance opportunities."""
        jobs = []
        
        # Add freelance sources here
        jobs += self._search_upwork_rss()
        
        if not jobs:
            jobs += self._search_duckduckgo_freelance()
        
        ranked = self._rank(jobs)
        return ranked[:limit]

    # ───────── Remotive ─────────

    def _remotive(self) -> List[Opportunity]:
        try:
            response = requests.get(
                "https://remotive.com/api/remote-jobs",
                timeout=10
            )
            data = response.json()
            
            jobs = []
            for job in data.get("jobs", [])[:30]:
                opp = self._make_opportunity(
                    title=job.get("title", ""),
                    company=job.get("company_name", ""),
                    description=job.get("description", ""),
                    url=job.get("url", ""),
                    source="Remotive",
                    location=job.get("candidate_required_location", "Remote"),
                    salary=job.get("salary", ""),
                )
                if opp.score > 10:  # Only include somewhat relevant jobs
                    jobs.append(opp)
            
            print(f"[JARVIS] Remotive: {len(jobs)} relevant jobs found")
            return jobs
        except Exception as e:
            print(f"[JARVIS] Remotive failed: {e}")
            return []

    # ───────── RemoteOK ─────────

    def _remoteok(self) -> List[Opportunity]:
        try:
            response = requests.get(
                "https://remoteok.com/api",
                headers={"User-Agent": "JARVIS/1.0"},
                timeout=10
            )
            data = response.json()
            
            jobs = []
            for job in data[1:31]:  # Skip header, limit to 30
                if not isinstance(job, dict):
                    continue
                
                opp = self._make_opportunity(
                    title=job.get("position", ""),
                    company=job.get("company", ""),
                    description=job.get("description", ""),
                    url=f"https://remoteok.com/remote-jobs/{job.get('slug', '')}",
                    source="RemoteOK",
                    salary=str(job.get("salary_min", "")),
                )
                if opp.score > 10:
                    jobs.append(opp)
            
            print(f"[JARVIS] RemoteOK: {len(jobs)} relevant jobs found")
            return jobs
        except Exception as e:
            print(f"[JARVIS] RemoteOK failed: {e}")
            return []

    # ───────── Upwork RSS ─────────

    def _search_upwork_rss(self) -> List[Opportunity]:
        try:
            import feedparser
            feed = feedparser.parse("https://www.upwork.com/ab/feed/topics/rss")
            
            jobs = []
            for entry in feed.entries[:20]:
                opp = self._make_opportunity(
                    title=entry.get("title", ""),
                    company="Upwork Client",
                    description=entry.get("summary", ""),
                    url=entry.get("link", ""),
                    source="Upwork",
                    type="freelance",
                )
                if opp.score > 10:
                    jobs.append(opp)
            
            print(f"[JARVIS] Upwork: {len(jobs)} freelance opportunities found")
            return jobs
        except Exception as e:
            print(f"[JARVIS] Upwork failed: {e}")
            return []

    # ───────── DuckDuckGo Fallback ─────────

    def _search_duckduckgo_jobs(self) -> List[Opportunity]:
        try:
            from ddgs import DDGS
            query = f"remote {self.role_title or 'software developer'} jobs {' '.join(self.skills[:3])}"
            
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=10))
            
            jobs = []
            for r in results:
                opp = self._make_opportunity(
                    title=r.get("title", ""),
                    company="",
                    description=r.get("body", ""),
                    url=r.get("href", ""),
                    source="DuckDuckGo",
                )
                jobs.append(opp)
            
            return jobs
        except Exception as e:
            print(f"[JARVIS] DuckDuckGo jobs failed: {e}")
            return []

    def _search_duckduckgo_freelance(self) -> List[Opportunity]:
        try:
            from ddgs import DDGS
            query = f"freelance {' '.join(self.skills[:3])} projects"
            
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=10))
            
            jobs = []
            for r in results:
                opp = self._make_opportunity(
                    title=r.get("title", ""),
                    company="",
                    description=r.get("body", ""),
                    url=r.get("href", ""),
                    source="DuckDuckGo",
                    type="freelance",
                )
                jobs.append(opp)
            
            return jobs
        except Exception as e:
            print(f"[JARVIS] DuckDuckGo freelance failed: {e}")
            return []

    # ───────── Matching ─────────

    def _make_opportunity(
        self,
        title: str,
        company: str,
        description: str,
        url: str,
        source: str,
        location: str = "Remote",
        type: str = "job",
        salary: str = "",
    ) -> Opportunity:
        text = f"{title} {description}".lower()

        matched = [
            skill for skill in self.skills
            if skill.lower() in text
        ]

        missing = [
            skill for skill in self.skills
            if skill.lower() not in text
        ]

        score = (
            len(matched) / len(self.skills) * 100
            if self.skills else 0
        )

        return Opportunity(
            title=title,
            company=company,
            url=url,
            source=source,
            score=round(score, 1),
            matched_skills=matched,
            missing_skills=missing,
            location=location,
            type=type,
            salary=salary,
        )

    def _rank(self, jobs: List[Opportunity]) -> List[Opportunity]:
        return sorted(
            jobs,
            key=lambda job: job.score,
            reverse=True
        )


# ─────────────────────────────────────────────
# JARVIS TOOLS
# ─────────────────────────────────────────────

parser = CVParser()
matcher = None


def upload_cv(file_path: str):
    """Upload and parse a CV file."""
    global matcher
    
    profile = parser.parse(file_path)
    
    # Rebuild matcher with new profile
    matcher = JobMatcher(profile)
    
    return {
        "status": "success",
        "profile": profile,
        "message": (
            f"CV uploaded successfully. "
            f"Found {len(profile['skills'])} skills."
        )
    }


def _get_matcher():
    """Get or create the job matcher instance."""
    global matcher
    
    if matcher is None:
        profile = parser.parse()  # Will auto-discover CV or use default
        matcher = JobMatcher(profile)
    
    return matcher


def find_matching_jobs(limit: int = 5):
    """Find jobs that match the user's CV."""
    jobs = _get_matcher().search_jobs(limit)
    return [job.to_dict() for job in jobs]


def find_freelance_opportunities(limit: int = 5):
    """Find freelance projects matching the user's CV."""
    jobs = _get_matcher().search_freelance(limit)
    return [job.to_dict() for job in jobs]


# ─────────────────────────────────────────────
# LLM TOOLS
# ─────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "find_matching_jobs",
            "description": (
                "Find remote software development jobs "
                "matching the user's CV and skills."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of jobs to return."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "upload_cv",
            "description": "Upload a CV to JARVIS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the CV file."},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_freelance_opportunities",
            "description": (
                "Find freelance software development "
                "projects matching the user's CV."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of projects to return."
                    }
                },
                "required": []
            }
        }
    }
]


TOOL_FUNCTIONS = {
    "find_matching_jobs": find_matching_jobs,
    "find_freelance_opportunities": find_freelance_opportunities,
    "upload_cv": upload_cv
}