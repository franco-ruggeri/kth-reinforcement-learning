import numpy as np
from pathlib import Path
from typing import Optional
from gym.utils.seeding import np_random
from el2805.lab0.envs.grid_world import GridWorld, Move


class PluckingBerries(GridWorld):
    def __init__(self, map_filepath: Path, horizon: Optional[int] = None, discount: Optional[float] = None):
        super().__init__(map_filepath, horizon, discount)
        self._player_position = None
        self._n_steps = None
        self._states = [np.asarray((x, y)) for x in range(self._map.shape[0]) for y in range(self._map.shape[1])]

    def reset(self) -> np.ndarray:
        x = self._rng.randint(low=0, high=self._map.shape[0])
        y = self._rng.randint(low=0, high=self._map.shape[1])
        self._player_position = np.asarray((x, y))
        self._n_steps = 0
        return self._player_position

    def seed(self, seed=None):
        self._rng, seed = np_random(seed)
        return [seed]

    def reward(
            self,
            state: np.ndarray,
            action: int,
            mean: bool = False
    ) -> float:
        assert action in self.valid_actions(state)
        x_next, y_next = self._next_state(state, action)
        symbol = self._map[x_next, y_next]
        reward = np.iinfo(np.int32).min if symbol == "#" else int(symbol)
        return reward

    def valid_actions(self, state: np.ndarray) -> list[int]:
        valid_moves = [Move.NOP]
        x, y = state

        x_tmp = x - 1
        if x_tmp >= 0:
            valid_moves.append(Move.UP)

        x_tmp = x + 1
        if x_tmp < self._map.shape[0]:
            valid_moves.append(Move.DOWN)

        y_tmp = y - 1
        if y_tmp >= 0:
            valid_moves.append(Move.LEFT)

        y_tmp = y + 1
        if y_tmp < self._map.shape[1]:
            valid_moves.append(Move.RIGHT)

        return valid_moves

    def state_to_index(self, state: np.ndarray) -> int:
        x, y = state
        index = x * self._map.shape[1] + y   # think about row-major matrix in memory (e.g., C programming language)
        return index

    def _episode_end(self):
        horizon_reached = self._n_steps >= self.horizon if self.horizon is not None else False
        return horizon_reached

    def _load_map(self, filepath):
        with open(filepath) as f:
            lines = f.readlines()
        self._map = np.asarray([[symbol for symbol in line[:-1].split("\t")] for line in lines])
