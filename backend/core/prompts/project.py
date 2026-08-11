"""
LLM prompts for N13 Project-Based Learning.
"""


def build_project_generation_prompt(
    subject_title: str,
    topic_title: str,
    subtopics: list[str],
    is_technical: bool,
) -> str:
    """
    Prompt to generate a capstone project (technical) or applied task (non-technical).
    """
    project_type = "capstone coding/building project" if is_technical else "applied analysis/essay/worked-problem task"

    return f"""You are an expert curriculum designer. Generate a {project_type} for a student learning "{topic_title}" under the subject "{subject_title}".

The topic covers these subtopics: {', '.join(subtopics)}.

Return a JSON object with these keys:
{{
  "title": "Short, compelling project title",
  "goal": "One sentence: what the student will build/produce",
  "description": "2-3 paragraph description of the project. What they build, why it matters, what they'll learn. Keep scope tight to ONLY what the topic teaches.",
  "skills_required": ["skill1", "skill2", ...],
  "milestones": [
    {{
      "milestone_id": "m1",
      "title": "Milestone title",
      "description": "What to complete for this milestone",
      "related_subtopics": ["subtopic names that feed this milestone"],
      "order": 1
    }},
    ...
  ],
  "rubric": [
    "Criterion 1: description",
    "Criterion 2: description",
    ...
  ]
}}

Rules:
- Generate 3-6 milestones, each mapped to 1-2 subtopics
- Milestones should be sequential and build on each other
- Scope the project to EXACTLY what the topic teaches — no scope creep
- {"For technical topics: the project should be something buildable (app, script, tool, algorithm)" if is_technical else "For non-technical topics: create an analysis, essay prompt, research task, or worked problem set"}
- Rubric should have 4-6 criteria, each assessable from a text/code submission
- Keep language clear, encouraging, and appropriate for a student
- Return ONLY valid JSON, no markdown fences
"""


def build_concept_project_link_prompt(
    node_title: str,
    project_title: str,
    project_goal: str,
    milestones: list[dict],
) -> str:
    """
    Prompt to generate the concept→project mapping for a specific subtopic.
    """
    ms_text = "\n".join(
        f"- {m['title']}: {m.get('description', '')}" for m in milestones
    )

    return f"""You are a tutor helping a student see how their current lesson connects to their capstone project.

Current subtopic: "{node_title}"
Project: "{project_title}" — {project_goal}
Project milestones:
{ms_text}

Return a JSON object:
{{
  "project_part": "A short, motivating sentence: 'You'll use this for: [specific part of the project]'. Be concrete about HOW this subtopic helps build the project.",
  "milestone_id": "The milestone_id this subtopic most directly feeds (from the list above)"
}}

Rules:
- Be specific and concrete, not generic
- Reference the actual project by name
- If the subtopic doesn't strongly connect to any milestone, still find the best match and explain the indirect connection
- Return ONLY valid JSON, no markdown fences
"""


def build_project_review_prompt(
    project_title: str,
    project_goal: str,
    milestones: list[dict],
    rubric: list[str],
    submission_content: str,
    submission_type: str,
) -> str:
    """
    Prompt to review a student's project submission against rubric + milestones.
    """
    ms_text = "\n".join(
        f"- [{m['milestone_id']}] {m['title']}: {m.get('description', '')}"
        for m in milestones
    )
    rubric_text = "\n".join(f"- {r}" for r in rubric)

    return f"""You are a supportive but honest project reviewer for a student's capstone project.

Project: "{project_title}"
Goal: {project_goal}
Submission type: {submission_type}

Milestones to check:
{ms_text}

Rubric criteria:
{rubric_text}

Student's submission:
---
{submission_content[:8000]}
---

Review the submission and return a JSON object:
{{
  "overall_score": <number 0-100>,
  "passed": <true if score >= 60>,
  "summary": "2-3 sentence overall assessment. Be encouraging but honest.",
  "milestone_reviews": [
    {{
      "milestone_id": "m1",
      "title": "Milestone title",
      "passed": true/false,
      "feedback": "Specific feedback for this milestone"
    }},
    ...
  ],
  "strengths": ["What the student did well (2-3 items)"],
  "improvements": ["What could be improved (2-3 items)"],
  "next_steps": "One sentence suggesting what to do next"
}}

Rules:
- This is best-effort review, NOT a hard pass/fail gate. Be clear about that.
- Be specific in feedback — reference what they actually submitted
- Be encouraging: highlight what works before what doesn't
- For code submissions, check logic/structure, not syntax perfection
- For description/essay submissions, check understanding and completeness
- Score generously for genuine effort that demonstrates understanding
- Return ONLY valid JSON, no markdown fences
"""
