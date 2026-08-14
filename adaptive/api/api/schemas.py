import re
from pydantic import BaseModel, field_validator
from typing import Dict, List, Optional


def _validate_safe_id(v: str) -> str:
    """Block NoSQL injection via $ operators and keep IDs alphanumeric."""
    if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', v):
        raise ValueError(
            "ID must be 1-64 characters, alphanumeric, hyphens, or underscores only"
        )
    return v


class StudentInput(BaseModel):

    student_id: str
    current_topic: str = "Algebra"

    @field_validator("student_id")
    def validate_student_id(cls, v):
        return _validate_safe_id(v)


class TutorResponse(BaseModel):

    mode: str = "direct_question"
    hint_level: int
    difficulty: float
    question: str
    explanation: Optional[dict] = None
    predicted_engagement: Optional[float] = None
    predicted_learning_gain: Optional[float] = None


class FeedbackInput(BaseModel):

    student_id: str
    correct: bool
    response_time: float
    hint_used: Optional[int] = 0
    difficulty: Optional[float] = None

    @field_validator("student_id")
    def validate_student_id(cls, v):
        return _validate_safe_id(v)

class AnswerRequest(BaseModel):
    student_id: str
    answer: str

    @field_validator("student_id")
    def validate_student_id(cls, v):
        return _validate_safe_id(v)


class UserIn(BaseModel):
    """Public signup schema — creates student (default) or guardian.

    SEC: only two account types are publicly creatable. 'teacher' and 'admin'
    are NOT accepted here — the teacher role was removed, and there is no
    self-serve path to any elevated role (prevents privilege escalation via
    the signup body).
    """
    username: str
    password: str
    account_type: str = "student"
    date_of_birth: str = ""  # ISO YYYY-MM-DD; required for students (13+ policy)
    email: str               # required — login identifier + email verification

    @field_validator("username")
    def valid_username(cls, v):
        v = (v or "").strip()
        if not re.match(r'^[a-zA-Z0-9_\-.]{3,32}$', v):
            raise ValueError(
                "Username must be 3-32 characters: letters, numbers, '_', '-', '.'"
            )
        return v

    @field_validator("password")
    def strong_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        return v

    @field_validator("date_of_birth")
    def valid_dob(cls, v):
        if not v:
            return v
        from datetime import date
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("date_of_birth must be YYYY-MM-DD")
        return v

    @field_validator("account_type")
    def valid_account_type(cls, v):
        if v not in ("student", "guardian"):
            raise ValueError("account_type must be 'student' or 'guardian'")
        return v

    @field_validator("email")
    def valid_email(cls, v):
        v = (v or "").strip().lower()
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError("A valid email is required")
        if len(v) > 254:
            raise ValueError("Email is too long")
        return v


class UserOut(BaseModel):
    id: str
    username: str
    role: str


class GuardianRedeemRequest(BaseModel):
    """Guardian redeems a student-generated invite code."""
    code: str


class Token(BaseModel):
    access_token: str
    # SEC-5: the refresh token now travels in an httpOnly cookie, not the JSON
    # body. Kept optional for backward compatibility with older clients.
    refresh_token: str = ""
    token_type: str
    role: str = "student"
    username: str = ""  # so email-login clients get the real display username

class StudentProgress(BaseModel):
    student_id: str
    topics: Dict[str, int]
    total_questions: int
    accuracy: float

class HintRequest(BaseModel):
    student_id: str
    question: str

    @field_validator("student_id")
    def validate_student_id(cls, v):
        return _validate_safe_id(v)


class HintResponse(BaseModel):
    hint: str


# ------------------------------------------------
# KNOWLEDGE GRAPH
# ------------------------------------------------

class GraphNode(BaseModel):
    topic: str
    mastery: float

class GraphEdge(BaseModel):
    source: str
    target: str
    strength: str
    reason: str

class KnowledgeGraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    weak_links: List[str]
    suggested_focus: str


# ------------------------------------------------
# SPACED REPETITION / REVIEW
# ------------------------------------------------

class ReviewItem(BaseModel):
    topic: str
    refresher: Optional[str] = None
    question: str
    answer: str
    tests_concept: str
    retention_estimate: float
    days_since_review: float

class DueTopicItem(BaseModel):
    topic: str
    mastery: float
    retention_estimate: float
    days_since_review: float
    review_count: int

class ReviewResponse(BaseModel):
    due_topics: List[DueTopicItem]
    review_question: Optional[ReviewItem] = None
    message: str


# ------------------------------------------------
# STUDY PLANNER
# ------------------------------------------------

class StudyPlanItem(BaseModel):
    topic: str
    duration_min: int
    type: str  # "review" | "learn" | "practice"
    reason: str

class StudyPlanProfileSummary(BaseModel):
    weak_concepts: List[Dict] = []
    strong_concepts: List[Dict] = []
    avg_session_minutes: float = 15.0
    fatigue: float = 0.0
    frustration: float = 0.1
    streak: int = 0
    engagement_trend: str = "not enough data"
    available_minutes: int = 30
    day: str = ""

class StudyPlanResponse(BaseModel):
    plan: List[StudyPlanItem]
    motivational_note: str
    estimated_knowledge_gain: str
    profile_summary: Optional[StudyPlanProfileSummary] = None


# ------------------------------------------------
# PROGRESSIVE CHALLENGE
# ------------------------------------------------

class ProgressiveChallengeStep(BaseModel):
    step: int
    sub_problem: str
    checkpoint_answer: str
    hint_if_stuck: str
    concept_tested: str

class ProgressiveChallengeResponse(BaseModel):
    topic: str
    difficulty: str
    problem_statement: str
    steps: List[ProgressiveChallengeStep]
    final_answer: str
    learning_arc: str


# ----------------------------------
# GAMIFICATION
# ----------------------------------

class BadgeInfo(BaseModel):
    id: str
    name: str
    emoji: str
    description: str
    unlocked_at: Optional[str] = None

class StreakInfo(BaseModel):
    current: int = 0
    alive: bool = True
    freezes_remaining: int = 2
    freezes_used_this_week: int = 0

class DailyGoal(BaseModel):
    date: str = ""
    answers_done: int = 0
    answers_target: int = 5
    reviews_done: int = 0
    reviews_target: int = 3
    completed: bool = False

class GamificationResponse(BaseModel):
    xp: int
    level: int
    xp_in_level: int
    xp_for_next_level: int
    streak: StreakInfo
    daily_goal: DailyGoal
    badges: List[BadgeInfo]
    new_badges: List[BadgeInfo] = []

    # Keep backward compat
    @property
    def current_streak(self) -> int:
        return self.streak.current

class CelebrationEvent(BaseModel):
    event: str  # "level_up", "daily_goal_completed", "badge_unlocked"
    new_level: Optional[int] = None
    new_badges: Optional[List[BadgeInfo]] = None


# ----------------------------------
# GUARDIAN (read-only parental access)
# ----------------------------------

class ChildSummary(BaseModel):
    student_id: str
    total_questions: int
    accuracy: float
    topics_count: int
    last_active: Optional[str] = None

class GuardianChildrenResponse(BaseModel):
    children: List[ChildSummary]

class GuardianChildOverview(BaseModel):
    student_id: str
    progress: StudentProgress
    knowledge_graph: Optional[KnowledgeGraphResponse] = None


# ----------------------------------
# RL STATS (OBSERVABILITY)
# ----------------------------------

class ActionDistribution(BaseModel):
    mode: dict = {}
    hint: dict = {}
    difficulty: dict = {}


class RLStatsResponse(BaseModel):
    epsilon: float
    step_counter: int
    total_decisions: int
    total_learns: int
    total_train_steps: int
    mean_reward: float
    mean_loss: float
    reward_window_size: int
    loss_window_size: int
    action_distribution: ActionDistribution
    uptime_seconds: float
    last_decision_at: Optional[float] = None
    last_learn_at: Optional[float] = None


# ----------------------------------
# QUIZ
# ----------------------------------

class QuizQuestion(BaseModel):
    id: int
    question: str
    options: Dict[str, str]
    correct: List[str]
    multiple: bool = False
    concept: str = ""
    explanation: str = ""
    difficulty: str = "medium"

class QuizResponse(BaseModel):
    quiz_title: str
    questions: List[QuizQuestion]

class QuizQuestionPublic(BaseModel):
    """Quiz question without correct answers (sent to frontend)."""
    id: int
    question: str
    options: Dict[str, str]
    multiple: bool = False
    concept: str = ""
    difficulty: str = "medium"

class QuizPublicResponse(BaseModel):
    quiz_title: str
    questions: List[QuizQuestionPublic]
    quiz_id: str

class QuizAnswerSubmission(BaseModel):
    quiz_id: str
    answers: Dict[str, List[str]]  # {"1": ["A"], "2": ["A", "C"]}

class QuizQuestionResult(BaseModel):
    id: int
    question: str
    submitted: List[str]
    correct: List[str]
    is_correct: bool
    multiple: bool = False
    explanation: str = ""
    concept: str = ""

class QuizScoreResponse(BaseModel):
    total_questions: int
    correct_count: int
    score_percentage: float
    results: List[QuizQuestionResult]


# ----------------------------------
# ONBOARDING
# ----------------------------------

class OnboardingProfile(BaseModel):
    """Captured during the onboarding wizard."""
    display_name: str
    age_band: str  # "under-13", "13-17", "18+"
    interests: List[str] = []
    goal: str = ""

    @field_validator("age_band")
    def valid_age_band(cls, v):
        allowed = {"under-13", "13-17", "18+"}
        if v not in allowed:
            raise ValueError(f"age_band must be one of {allowed}")
        return v


class OnboardingStartResponse(BaseModel):
    session_id: str
    question: str
    options: Optional[Dict[str, str]] = None
    topic: str
    question_number: int
    total_questions: int


class OnboardingAnswerRequest(BaseModel):
    session_id: str
    answer: str


class OnboardingAnswerResponse(BaseModel):
    correct: bool
    next_question: Optional[str] = None
    next_options: Optional[Dict[str, str]] = None
    next_topic: Optional[str] = None
    question_number: int
    total_questions: int
    done: bool = False


class OnboardingCompleteResponse(BaseModel):
    display_name: str
    topics_assessed: List[str]
    mastery_seeds: Dict[str, float]
    message: str


# -- E5: Learning Path & Daily Plan --

class SetGoalRequest(BaseModel):
    goal: str

    @field_validator("goal")
    def validate_goal(cls, v):
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError("Goal must be 1-100 characters")
        return v


class PathNode(BaseModel):
    topic: str
    order: int
    mastery: float
    state: str  # "mastered", "unlocked", "current", "locked"
    prereqs: List[str] = []


class LearningPathResponse(BaseModel):
    goal: str
    path: List[PathNode]
    current_topic: Optional[str] = None
    progress_pct: float = 0.0


class TodayTask(BaseModel):
    type: str  # "learn", "review", "practice"
    topic: str
    reason: str
    duration_min: int = 15
    mastery: Optional[float] = None


class TodayPlanResponse(BaseModel):
    tasks: List[TodayTask]
    message: str
    has_path: bool = False


# -- E6: Mastery Dashboard --

class MasterySnapshot(BaseModel):
    date: str  # ISO date string
    mastery: float

class TopicMasteryHistory(BaseModel):
    topic: str
    current_mastery: float
    snapshots: List[MasterySnapshot]

class MasteryOverviewCounts(BaseModel):
    mastered: int
    in_progress: int
    not_started: int
    total: int

class MasteryDashboardResponse(BaseModel):
    counts: MasteryOverviewCounts
    history: List[TopicMasteryHistory]
    overall_trend: str  # "improving", "steady", "declining"


# -- E7: Certificates --

class CertificateInfo(BaseModel):
    cert_id: str
    topic: str
    tier: str  # "Proficiency", "Excellence", "Mastery"
    mastery: float
    awarded_at: str
    display_name: str = ""

class CertificatesListResponse(BaseModel):
    certificates: List[CertificateInfo]
    total: int


# -- E11: Daily Quests --

class QuestInfo(BaseModel):
    quest_id: str
    template_id: str
    title: str
    description: str
    type: str  # "challenge", "streak", "review", "practice", "explore", "accuracy"
    difficulty: str  # "easy", "medium", "hard"
    topic: str = ""
    xp_reward: int
    target: int
    metric: str
    progress: int = 0
    completed: bool = False
    date: str = ""

class QuestsResponse(BaseModel):
    quests: List[QuestInfo]
    date: str


# -- P5: Leaderboard, Reminders, Retention --

class LeaderboardEntry(BaseModel):
    rank: int
    display_name: str
    weekly_xp: int

class LeaderboardResponse(BaseModel):
    week: str
    entries: List[LeaderboardEntry]
    total_participants: int
    my_rank: Optional[dict] = None

class ReminderInfo(BaseModel):
    reminder_id: str
    type: str
    title: str
    body: str
    priority: str = "medium"
    read: bool = False
    date: str = ""

class ReminderPrefsResponse(BaseModel):
    streak_reminder: bool = True
    daily_goal_reminder: bool = True
    welcome_back: bool = True
    weekly_summary: bool = True
    quiet_hours_start: int = 22
    quiet_hours_end: int = 8

class RetentionResponse(BaseModel):
    student_id: str
    first_seen: Optional[str] = None
    total_active_days: int = 0
    day_1_returned: bool = False
    day_7_returned: bool = False


# -- E9: Preferences (language, reading level, accessibility) --

class StudentPreferences(BaseModel):
    # B5: en | hi | hinglish | ta te bn mr gu kn ml pa (regional Indian languages)
    language: str = "en"
    reading_level: str = "standard"  # "simple" | "standard"
    font_size: str = "normal"      # "normal" | "large" | "xl"
    tts_enabled: bool = False
    stt_enabled: bool = False

    @field_validator("language")
    def valid_language(cls, v):
        from utils.language import LANGUAGE_NAMES
        if v not in LANGUAGE_NAMES:
            raise ValueError(
                "language must be one of: " + ", ".join(sorted(LANGUAGE_NAMES))
            )
        return v

    @field_validator("reading_level")
    def valid_reading_level(cls, v):
        if v not in ("simple", "standard"):
            raise ValueError("reading_level must be 'simple' or 'standard'")
        return v

    @field_validator("font_size")
    def valid_font_size(cls, v):
        if v not in ("normal", "large", "xl"):
            raise ValueError("font_size must be 'normal', 'large', or 'xl'")
        return v


# ----------------------------------
# N1: ASK-ANYTHING
# ----------------------------------

class AskRequest(BaseModel):
    """Student brings their own question (text + optional image text)."""
    question: str
    image_text: Optional[str] = None  # OCR'd text from uploaded image

    @field_validator("question")
    def validate_question(cls, v):
        v = v.strip()
        if not v or len(v) > 5000:
            raise ValueError("Question must be 1-5000 characters")
        return v


class AskResponse(BaseModel):
    response: str
    probing_question: str = ""
    hint_if_stuck: str = ""
    concept_connection: str = ""
    topic: str = ""
    concept: str = ""
    session_id: str = ""


# ----------------------------------
# N2: EXPLAIN-AGAIN
# ----------------------------------

class ExplainAgainRequest(BaseModel):
    """Re-explain current concept in a different style."""
    session_id: Optional[str] = None
    topic: Optional[str] = None
    style: str = "simpler"

    @field_validator("style")
    def valid_style(cls, v):
        allowed = {"simpler", "analogy", "worked_example", "step_by_step"}
        if v not in allowed:
            raise ValueError(f"style must be one of {allowed}")
        return v


class ExplainAgainResponse(BaseModel):
    explanation: str
    style_used: str = ""
    key_takeaway: str = ""
    check_understanding: str = ""


# ----------------------------------
# N10: CURRICULUM MAP
# ----------------------------------

class SubjectInfo(BaseModel):
    id: str
    title: str
    icon: str = ""
    color: str = ""
    started: bool = False

class SubjectListResponse(BaseModel):
    subjects: List[SubjectInfo]

class CurriculumNode(BaseModel):
    node_id: str
    title: str
    level: int
    parent_id: Optional[str] = None
    prerequisites: List[str] = []
    order: int = 0
    status: str = "not_started"
    mastery: float = 0.0
    node_type: str = "topic"  # "topic" | "choice" | "branch"
    branch_group: Optional[str] = None  # shared key among sibling branch options

class CurriculumStats(BaseModel):
    total: int = 0
    done: int = 0
    in_progress: int = 0
    not_started: int = 0
    progress_pct: float = 0.0
    est_minutes_left: int = 0
    current_node_id: Optional[str] = None

class CurriculumMapResponse(BaseModel):
    subject_id: str
    subject_title: str = ""
    nodes: List[CurriculumNode] = []
    stats: CurriculumStats = CurriculumStats()
    pending_choices: List[str] = []  # branch_group ids user hasn't chosen yet
    chosen_branches: Dict[str, str] = {}  # branch_group -> chosen node_id

class SkipNodeResponse(BaseModel):
    success: bool
    node_id: str
    warnings: List[str] = []
    message: str = ""


# ----------------------------------
# N3: RESUME
# ----------------------------------

class ResumeInfo(BaseModel):
    has_session: bool = False
    topic: str = ""
    last_active_at: float = 0
    elapsed_hours: float = 0
    last_question: str = ""
    last_mode: str = ""
    mastery: float = 0.0


# ----------------------------------
# N4: REVIEW-DUE
# ----------------------------------

class ReviewDueCount(BaseModel):
    count: int = 0
    topics: List[Dict] = []


# ----------------------------------
# N9: QUIZ HISTORY
# ----------------------------------

class QuizHistoryItem(BaseModel):
    quiz_id: str
    topic: str
    score_pct: float
    correct: int
    total: int
    passed: bool
    taken_at: float
    wrong_concepts: List[str] = []

class QuizHistoryResponse(BaseModel):
    history: List[QuizHistoryItem] = []
    total_quizzes: int = 0
    avg_score: float = 0.0


# ----------------------------------
# N5: MISTAKES NOTEBOOK
# ----------------------------------

class MistakeItem(BaseModel):
    mistake_id: str
    source: str = ""
    topic: str = ""
    concept: str = ""
    question: str = ""
    user_answer: str = ""
    correct_answer: str = ""
    explanation: str = ""
    timestamp: float = 0
    resolved: bool = False
    resolved_at: Optional[float] = None

class MistakesResponse(BaseModel):
    mistakes: List[MistakeItem] = []
    total: int = 0
    unresolved: int = 0


# ----------------------------------
# N13: PROJECT-BASED LEARNING
# ----------------------------------

class ProjectMilestone(BaseModel):
    milestone_id: str
    title: str
    description: str = ""
    related_nodes: List[str] = []
    order: int = 0
    completed: bool = False
    completed_at: Optional[float] = None

class ProjectBrief(BaseModel):
    project_id: str = ""
    subject_id: str = ""
    topic_type: str = "technical"
    title: str = ""
    goal: str = ""
    description: str = ""
    skills_required: List[str] = []
    milestones: List[ProjectMilestone] = []
    rubric: List[str] = []
    status: str = "active"
    milestones_done: int = 0
    milestones_total: int = 0
    created_at: float = 0

class ConceptProjectLink(BaseModel):
    node_id: str
    node_title: str = ""
    project_part: str = ""
    milestone_id: str = ""

class ProjectSubmissionRequest(BaseModel):
    submission_type: str = "description"
    content: str = ""

    @field_validator("content")
    def validate_content(cls, v):
        v = v.strip()
        if not v or len(v) > 20000:
            raise ValueError("Submission must be 1-20000 characters")
        return v

class MilestoneReview(BaseModel):
    milestone_id: str
    title: str = ""
    passed: bool = False
    feedback: str = ""

class ProjectReviewResponse(BaseModel):
    project_id: str = ""
    overall_score: float = 0.0
    passed: bool = False
    summary: str = ""
    milestone_reviews: List[MilestoneReview] = []
    strengths: List[str] = []
    improvements: List[str] = []
    next_steps: str = ""


# ----------------------------------
# N7: PROGRESS SNAPSHOT
# ----------------------------------

class TopicGain(BaseModel):
    topic: str
    mastery_before: float = 0.0
    mastery_now: float = 0.0
    gain: float = 0.0

class ProgressSnapshot(BaseModel):
    topics_touched_this_week: int = 0
    topics_list: List[TopicGain] = []
    total_mastery_gain: float = 0.0
    current_streak: int = 0
    questions_this_week: int = 0
    next_up: str = ""
    message: str = ""


# ----------------------------------
# N12: PERSONAL NOTEBOOK
# ----------------------------------

class NoteItem(BaseModel):
    note_id: str = ""
    node_id: str = ""
    topic: str = ""
    selected_text: str = ""
    user_note: str = ""
    source_context: str = ""
    related_topics: List[str] = []
    created_at: float = 0
    updated_at: float = 0

class NotebookResponse(BaseModel):
    notes: List[NoteItem] = []
    total: int = 0
    topics: List[str] = []
