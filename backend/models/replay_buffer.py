from collections import deque
import random
import torch
import asyncio
import time


class ReplayBuffer:

    def __init__(self, capacity=20000, db_collection=None):
        self.buffer = deque(maxlen=capacity)
        self.capacity = capacity
        self._collection = db_collection  # Motor async collection (or None)

    # ----------------------------------
    # PUSH (hot path + write-through)
    # ----------------------------------

    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))

        # Write-through to MongoDB (fire-and-forget)
        if self._collection is not None:
            doc = {
                "state": state.tolist(),
                "action": int(action),
                "reward": float(reward),
                "next_state": next_state.tolist(),
                "done": bool(done),
                "ts": time.time(),
            }
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._persist(doc))
                else:
                    loop.run_until_complete(self._persist(doc))
            except RuntimeError:
                # No event loop — skip persistence silently
                pass

    async def _persist(self, doc):
        """Insert one transition document. Best-effort — errors are logged, not raised."""
        try:
            await self._collection.insert_one(doc)
        except Exception as e:
            print("WARNING: Failed to persist transition: %s" % e)

    # ----------------------------------
    # LOAD FROM DB (startup)
    # ----------------------------------

    async def load_from_db(self):
        """
        Reload the most recent `capacity` transitions from MongoDB into the deque.
        Called once at startup. Returns number of transitions loaded.
        """
        if self._collection is None:
            return 0

        try:
            cursor = self._collection.find().sort("ts", -1).limit(self.capacity)
            docs = await cursor.to_list(length=self.capacity)

            # Reverse so oldest is first (deque order matches training order)
            docs.reverse()

            for doc in docs:
                state = torch.tensor(doc["state"], dtype=torch.float32)
                next_state = torch.tensor(doc["next_state"], dtype=torch.float32)
                self.buffer.append((
                    state,
                    doc["action"],
                    doc["reward"],
                    next_state,
                    doc["done"],
                ))

            count = len(docs)
            if count > 0:
                print("Loaded %d transitions from DB into replay buffer." % count)
            else:
                print("No prior transitions found in DB. Starting fresh.")
            return count

        except Exception as e:
            print("WARNING: Failed to load replay buffer from DB: %s" % e)
            return 0

    # ----------------------------------
    # SAMPLE
    # ----------------------------------

    def sample(self, batch_size):
        batch = random.sample(self.buffer, batch_size)

        states, actions, rewards, next_states, dones = zip(*batch)

        return (
            torch.stack(states),
            torch.tensor(actions),
            torch.tensor(rewards, dtype=torch.float32),
            torch.stack(next_states),
            torch.tensor(dones, dtype=torch.float32)
        )

    def __len__(self):
        return len(self.buffer)
