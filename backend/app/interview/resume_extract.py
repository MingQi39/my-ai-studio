"""Local-only resume keyword extraction. Source bytes are never persisted here."""

from __future__ import annotations

from io import BytesIO
import re
from zipfile import ZipFile
from xml.etree import ElementTree

from pypdf import PdfReader


TECHNOLOGIES = (
    "React", "Vue", "TypeScript", "JavaScript", "Python", "FastAPI", "Django",
    "Node.js", "Java", "Go", "Docker", "Kubernetes", "MySQL", "PostgreSQL",
    "Redis", "MongoDB", "AWS", "LangChain", "LangGraph", "LLM", "RAG", "SSE",
    "WebSocket", "Git", "Linux", "Next.js", "Tailwind", "Vite", "PyTorch",
    "TensorFlow", "OpenAI", "Anthropic", "GraphQL", "gRPC", "Kafka", "Nginx",
)

SECTION_MARKERS = re.compile(
    r"(项目经历|工作经历|实习经历|教育经历|专业技能|个人技能|技能|"
    r"project experience|work experience|education|skills)",
    re.I,
)


def extract_resume_text(content: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
    if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        with ZipFile(BytesIO(content)) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        return "\n".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
    raise ValueError("仅支持 PDF 或 DOCX 简历")


def _clean_label(raw: str) -> str:
    label = re.sub(r"\s+", " ", raw).strip(" -•·\t|/")
    label = re.sub(r"^\d{4}[./年].{0,20}", "", label).strip(" -•·\t|/")
    return label[:80]


def extract_resume_claims(text: str) -> list[dict[str, object]]:
    """Extract skills + project/work experience. Does not invent salary or seniority."""
    normalized = re.sub(r"\s+", " ", text)
    claims: list[dict[str, object]] = []

    for technology in TECHNOLOGIES:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(technology)}(?![A-Za-z0-9])", normalized, re.I):
            claims.append({"category": "skill", "label": technology, "keywords": [technology]})

    current_section: str | None = None
    for line in text.splitlines():
        candidate = line.strip(" -•·\t")
        if not candidate:
            continue

        section_match = SECTION_MARKERS.search(candidate)
        if section_match and len(candidate) <= 40:
            marker = section_match.group(1).lower()
            if "项目" in marker or "project" in marker:
                current_section = "project"
            elif "工作" in marker or "实习" in marker or "work" in marker:
                current_section = "role"
            else:
                current_section = None
            # Header-only lines should not become claims.
            if len(candidate) <= 12 or SECTION_MARKERS.fullmatch(candidate):
                continue
            if current_section is None:
                continue

        if len(candidate) > 80:
            continue

        if current_section in {"project", "role"}:
            # Skip pure date lines / bullet-only noise.
            if re.fullmatch(r"[\d./\-~\s年月至日]+", candidate):
                continue
            label = _clean_label(candidate)
            if len(label) >= 2:
                claims.append({"category": current_section, "label": label, "keywords": []})
            continue

        if re.search(r"(项目|project)", candidate, re.I):
            label = _clean_label(
                re.sub(r"^(项目经历|项目|project experience|project)[:：\s-]*", "", candidate, flags=re.I)
            )
            if len(label) >= 2:
                claims.append({"category": "project", "label": label, "keywords": []})
        elif re.search(r"(工作|实习|任职)", candidate):
            label = _clean_label(
                re.sub(r"^(工作经历|实习经历|工作|实习)[:：\s-]*", "", candidate, flags=re.I)
            )
            if len(label) >= 2:
                claims.append({"category": "role", "label": label, "keywords": []})

    unique: dict[tuple[str, str], dict[str, object]] = {}
    for claim in claims:
        unique[(str(claim["category"]), str(claim["label"]).lower())] = claim
    return list(unique.values())[:40]
