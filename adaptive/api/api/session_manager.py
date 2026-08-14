from datetime import datetime, timezone
from database import student_states_collection
from models.student import Student, Concept
from models.student_state import StudentState
from utils.memory_store import save_student, load_student


class SessionManager:

    # ----------------------------------
    # CREATE SESSION
    # ----------------------------------

    async def create_session(self, data):

        student_id = data["student_id"]
        current_topic = data.get("current_topic", "General")

        concepts = data.get("concepts", {})

        # fallback for old API
        if not concepts:
            concepts = {
                current_topic: {
                    "knowledge": data.get("knowledge", 0.5),
                    "concept_mastery": data.get("concept_mastery", 0.5)
                }
            }

        student = self._build_student(student_id, data, concepts, current_topic)

        return student

    # ----------------------------------
    # LOAD STUDENT
    # ----------------------------------

    async def get_student(self, student_id):

        data = await load_student(student_id)

        if not data:
            return None

        concepts = data.get("concepts", {})
        current_topic = data.get("current_topic", "General")

        student = self._build_student(student_id, data, concepts, current_topic)

        student.history = data.get("history", [])

        return student

    # ----------------------------------
    # CORE BUILDER (DRY)
    # ----------------------------------

    def _build_student(self, student_id, data, concepts, current_topic):

        state = StudentState(
            student_id=student_id,
            learning_velocity=data.get("learning_velocity", 0.002),
            confidence=data.get("confidence", 0.5),
            engagement=data.get("engagement", 0.6),
            speed=data.get("speed", 0.5),
            hint_dependency=data.get("hint_dependency", 0.5),
            streak=data.get("streak", 0),
            fatigue=data.get("fatigue", 0.0),
            frustration=data.get("frustration", 0.1),
            curiosity=data.get("curiosity", 0.5),
            focus=data.get("focus", 0.6),
            retention=data.get("retention", 0.6),
            cognitive_load=data.get("cognitive_load", 0.3),
        )

        # P2.3: carry last_misconception through state
        state.last_misconception = data.get("last_misconception", "")

        student = Student(student_id, state)

        def build_concept(c):
            return Concept(
                knowledge=c.get("knowledge", 0.5),
                concept_mastery=c.get("concept_mastery", 0.5),
                subtopics={
                    sub: build_concept(sub_c)
                    for sub, sub_c in c.get("subtopics", {}).items()
                },
                last_reviewed=c.get("last_reviewed"),
                review_count=c.get("review_count", 0),
                decay_rate=c.get("decay_rate", 0.05),
                fsrs_state=c.get("fsrs_state"),
            )

        student.concepts = {
            topic: build_concept(c)
            for topic, c in concepts.items()
        }

        student.current_topic = current_topic

        self._attach_helpers(student)

        return student

    # ----------------------------------
    # SAVE STUDENT
    # ----------------------------------

    async def save(self, student):

        def serialize_concept(c):
            return {
                "knowledge": c.knowledge,
                "concept_mastery": c.concept_mastery,
                "subtopics": {
                    sub: serialize_concept(sub_c)
                    for sub, sub_c in c.subtopics.items()
                },
                "last_reviewed": getattr(c, "last_reviewed", None),
                "review_count": getattr(c, "review_count", 0),
                "decay_rate": getattr(c, "decay_rate", 0.05),
                "fsrs_state": getattr(c, "fsrs_state", None),
            }

        data = {
            "student_id": student.student_id,

            # global state
            "learning_velocity": student.learning_velocity,
            "confidence": student.confidence,
            "engagement": student.engagement,
            "speed": student.speed,
            "hint_dependency": student.hint_dependency,
            "streak": student.streak,

            "fatigue": student.fatigue,
            "frustration": student.frustration,
            "curiosity": student.curiosity,
            "focus": student.focus,

            "retention": student.retention,
            "cognitive_load": student.cognitive_load,

            # concepts
            "concepts": {
                topic: serialize_concept(c)
                for topic, c in student.concepts.items()
            },

            "current_topic": student.current_topic,
            # SCALE: cap the interaction history so the student document can't
            # grow past Mongo's 16MB limit (and to bound read amplification —
            # the whole doc is loaded on every tutor turn). Keep the most recent
            # 200 entries; long-term analytics live in the interactions collection.
            "history": (getattr(student, "history", []) or [])[-200:],

            # socratic mode tracking
            "conversation": getattr(student, "conversation", [])[-20:],  # keep last 20 turns
            "last_mode": getattr(student, "last_mode", 0),
            "conversation_turns": getattr(student, "conversation_turns", 0),

            # P2.3: last misconception for targeting next question
            "last_misconception": getattr(student, "last_misconception", ""),
        }

        await save_student(data)

    # ----------------------------------
    # HELPERS
    # ----------------------------------

    def _attach_helpers(self, student):
        # Student.get_current_concept() now natively returns Concept objects
        # No monkey-patching needed
        pass

    # ----------------------------------
    # STUDENT STATE (MONGO)
    # ----------------------------------

    async def get_student_state(self, student_id: str):

        state = await student_states_collection.find_one({"student_id": student_id})

        if not state:
            state = {
                "student_id": student_id,
                "current_topic": "Algebra",
                "total_questions": 0,
                "correct_answers": 0,
                "topic_proficiency": {},
                "last_updated": datetime.now(timezone.utc)
            }
            await student_states_collection.insert_one(state)

        return state

    async def update_student_state(self, student_id: str, is_correct: bool, topic: str):

        update_query = {
            "$inc": {
                "total_questions": 1,
                "correct_answers": 1 if is_correct else 0,
                f"topic_proficiency.{topic}": 1 if is_correct else 0
            },
            "$set": {
                "last_updated": datetime.now(timezone.utc)
            }
        }

        await student_states_collection.update_one(
            {"student_id": student_id},
            update_query,
            upsert=True
        )
