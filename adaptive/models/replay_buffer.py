from collections import deque
import random
import asyncio
import time

try:
    import torch
    HAS_TORCH = True
except ImportError:
    torch = None
    HAS_TORCH = False


class ReplayBuffer:

    def __init__(self, capacity=20000, db_collection=None):
        self.buffer = deque(maxlen=capacity)
        self.capacity = capacity
        self._collection = db_collection

    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))

        if self._collection is not None:
            state_list = state.tolist() if hasattr(state, "tolist") else list(state)
            next_state_list = next_state.tolist() if hasattr(next_state, "tolist") else list(next_state)

            doc = {
                "ts": time.time(),
                "state": state_list,
                "action": action,
                "reward": float(reward),
                "next_state": next_state_list,
                "done": bool(done),
            }

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._persist(doc))
                else:
                    loop.run_until_complete(self._persist(doc))
            except RuntimeError:
                pass

    async def _persist(self, doc):
        try:
            await self._collection.insert_one(doc)
        except Exception as e:
            print("WARNING: Failed to persist transition: %s" % e)

    async def load_from_db(self):
        if self._collection is None:
            return 0

        try:
            cursor = self._collection.find().sort("ts", -1).limit(self.capacity)
            docs = await cursor.to_list(length=self.capacity)
            docs.reverse()

            for doc in docs:
                if HAS_TORCH:
                    state = torch.tensor(doc["state"], dtype=torch.float32)
                    next_state = torch.tensor(doc["next_state"], dtype=torch.float32)
                else:
                    state = doc["state"]
                    next_state = doc["next_state"]

                self.buffer.append((
                    state,
                    doc["action"],
                    doc["reward"],
                    next_state,
                    doc["done"],
                ))

            count = len(docs)
            return count

        except Exception as e:
            print("WARNING: Failed to load replay buffer from DB: %s" % e)
            return 0

    def sample(self, batch_size):
        batch = random.sample(self.buffer, batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)

        if HAS_TORCH:
            return (
                torch.stack(states),
                torch.tensor(actions),
                torch.tensor(rewards, dtype=torch.float32),
                torch.stack(next_states),
                torch.tensor(dones, dtype=torch.float32)
            )
        else:
            return states, actions, rewards, next_states, dones

    def __len__(self):
        return len(self.buffer)
