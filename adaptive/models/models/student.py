import time


class Concept:
    """Represents per-topic knowledge state. Used across Student and SessionManager."""

    def __init__(self, knowledge=0.5, concept_mastery=0.5, subtopics=None,
                 last_reviewed=None, review_count=0, decay_rate=0.05,
                 fsrs_state=None):
        self.knowledge = knowledge
        self.concept_mastery = concept_mastery
        self.subtopics = subtopics or {}
        self.last_reviewed = last_reviewed or time.time()
        self.review_count = review_count
        self.decay_rate = decay_rate  # legacy, kept for backward compat

        # FSRS card state (persisted as dict, reconstructed on load)
        # Keys: card_id, state, step, stability, difficulty, due, last_review
        self.fsrs_state = fsrs_state  # None = no FSRS card yet


class Student:

    def __init__(self, student_id, state):

        self.student_id = student_id

        # -----------------------------
        # CONCEPT SYSTEM
        # -----------------------------
        self.concepts = getattr(state, "concepts", {})
        self.current_topic = getattr(state, "current_topic", "General")

        self.ensure_concept(self.current_topic)

        # -----------------------------
        # GLOBAL STATE
        # -----------------------------
        self.learning_velocity = state.learning_velocity
        self.confidence = state.confidence

        self.engagement = state.engagement
        self.speed = state.speed
        self.hint_dependency = state.hint_dependency
        self.streak = getattr(state, "streak", 0)

        self.fatigue = getattr(state, "fatigue", 0.0)
        self.frustration = getattr(state, "frustration", 0.1)
        self.curiosity = getattr(state, "curiosity", 0.5)
        self.focus = getattr(state, "focus", 0.6)

        self.retention = state.retention
        self.cognitive_load = state.cognitive_load

        # -----------------------------
        # SYNC CONCEPT VALUES
        # -----------------------------
        self.sync_from_concept()

        # -----------------------------
        # TRACKING
        # -----------------------------
        self.memory = []
        self.history = getattr(state, "history", [])

        # -----------------------------
        # SOCRATIC MODE TRACKING
        # -----------------------------
        self.conversation = getattr(state, "conversation", [])  # multi-turn context
        self.last_mode = getattr(state, "last_mode", 0)         # last RL mode used
        self.conversation_turns = getattr(state, "conversation_turns", 0)  # turns in current topic

        # P2.3: Last misconception for targeting next question
        self.last_misconception = getattr(state, "last_misconception", "")

    # ----------------------------------
    # CONCEPT MANAGEMENT
    # ----------------------------------

    def ensure_concept(self, topic):
        if topic not in self.concepts:
            self.concepts[topic] = Concept()

    def get_current_concept(self):
        self.ensure_concept(self.current_topic)
        return self.concepts[self.current_topic]

    def sync_from_concept(self):
        c = self.get_current_concept()
        self.knowledge = c.knowledge
        self.concept_mastery = c.concept_mastery

    def sync_to_concept(self):
        c = self.get_current_concept()
        c.knowledge = self.knowledge
        c.concept_mastery = self.concept_mastery

    # ----------------------------------
    # TOPIC SWITCH
    # ----------------------------------

    def set_topic(self, topic):
        self.current_topic = topic
        self.ensure_concept(topic)
        self.sync_from_concept()