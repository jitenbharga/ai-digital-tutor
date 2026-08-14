from models.student import Concept
from utils.state_vector import build_state_vector


class StudentState:

    def __init__(
        self,
        student_id,

        # DEFAULT CONCEPT
        current_topic="General",

        # Global (behavioral)
        learning_velocity=0.002,
        confidence=0.5,

        engagement=0.6,
        speed=0.5,
        hint_dependency=0.5,
        streak=0,

        fatigue=0.0,
        frustration=0.1,
        curiosity=0.5,
        focus=0.6,

        retention=0.6,
        cognitive_load=0.3
    ):

        self.student_id = student_id

        # -----------------------------
        # CONCEPT SYSTEM
        # -----------------------------
        self.concepts = {}
        self.current_topic = current_topic

        self.ensure_concept(self.current_topic)

        # -----------------------------
        # GLOBAL STATE
        # -----------------------------
        self.learning_velocity = learning_velocity
        self.confidence = confidence

        self.engagement = engagement
        self.speed = speed
        self.hint_dependency = hint_dependency
        self.streak = streak

        self.fatigue = fatigue
        self.frustration = frustration
        self.curiosity = curiosity
        self.focus = focus

        self.retention = retention
        self.cognitive_load = cognitive_load

        # -----------------------------
        # SYNCED VALUES (IMPORTANT)
        # -----------------------------
        self.sync_from_concept()

        # Logs
        self.history = []

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
    # SWITCH TOPIC (IMPORTANT)
    # ----------------------------------

    def set_topic(self, topic):
        self.current_topic = topic
        self.ensure_concept(topic)
        self.sync_from_concept()

    # ----------------------------------
    # STATE VECTOR (16 DIM)
    # ----------------------------------

    def to_vector(self):

        self.sync_from_concept()

        return build_state_vector(
            knowledge=self.knowledge,
            learning_velocity=self.learning_velocity,
            confidence=self.confidence,
            concept_mastery=self.concept_mastery,
            engagement=self.engagement,
            speed=self.speed,
            hint_dependency=self.hint_dependency,
            streak=self.streak,
            fatigue=self.fatigue,
            frustration=self.frustration,
            curiosity=self.curiosity,
            focus=self.focus,
            retention=self.retention,
            cognitive_load=self.cognitive_load,
            conversation_turns=getattr(self, "conversation_turns", 0),
            last_mode=getattr(self, "last_mode", 0),
        )