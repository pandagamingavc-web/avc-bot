import time
from collections import defaultdict, deque

class SpamGate:
    def __init__(self, max_msgs: int, window_sec: int):
        self.max_msgs = max_msgs
        self.window_sec = window_sec
        self.events = defaultdict(deque)

    def hit(self, user_id: int) -> bool:
        now = time.time()
        q = self.events[user_id]
        q.append(now)
        while q and now - q[0] > self.window_sec:
            q.popleft()
        return len(q) > self.max_msgs
