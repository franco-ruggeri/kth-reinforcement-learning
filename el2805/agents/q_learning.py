from typing import Any
from el2805.agents.q_agent import QAgent


class QLearning(QAgent):
    def update(self, state: Any, action: int, reward: float, next_state: Any) -> None:
        s = self.env.state_index(state)
        a = self._action_index(state, action)
        s_next = self.env.state_index(next_state)
        step_size = 1 / (self._n[s][a] ** self.alpha)

        self._q[s][a] += step_size * (reward + self.env.discount * max(self._q[s_next]) - self._q[s][a])
        self._n[s][a] += 1