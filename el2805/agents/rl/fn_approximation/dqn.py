import gym
import numpy as np
import torch
import pickle
from collections import deque
from copy import deepcopy
from el2805.agents.rl.rl_agent import RLAgent
from el2805.agents.rl.utils import Experience
from el2805.utils import random_decide


class QNetwork(torch.nn.Module):
    def __init__(
            self,
            input_size: int,
            output_size: int,
            n_hidden_layers: int,
            hidden_layer_size: int,
            activation: str
    ):
        super().__init__()
        self.input_size = input_size
        self.output_size = output_size
        self.n_hidden_layers = n_hidden_layers
        self.hidden_layer_size = hidden_layer_size
        self.activation = activation

        self._hidden_layers = []
        input_size = self.input_size
        for _ in range(n_hidden_layers):
            hidden_layer = torch.nn.Linear(input_size, self.hidden_layer_size)
            self._hidden_layers.append(hidden_layer)
            input_size = hidden_layer_size
        self._output_layer = torch.nn.Linear(input_size, output_size)

        if self.activation == "relu":
            self._activation_fn = torch.nn.functional.relu
        elif self.activation == "tanh":
            self._activation_fn = torch.nn.functional.tanh
        else:
            raise NotImplementedError

    def forward(self, x):
        for layer in self._hidden_layers:
            x = layer(x)
            x = self._activation_fn(x)
        x = self._output_layer(x)
        return x


class DQN(RLAgent):
    def __init__(
            self,
            *,
            environment: gym.Env,
            discount: float,
            epsilon: float | str,
            epsilon_max: float | None = None,
            epsilon_min: float | None = None,
            epsilon_decay_duration: int | None = None,
            learning_rate: float,
            batch_size: int,
            replay_buffer_size: int,
            warmup_steps: int,
            target_update_frequency: int,
            gradient_clipping_value: float,
            n_hidden_layers: int,
            hidden_layer_size: int,
            activation: str,
            cer: bool,
            dueling: bool,
            device: str
    ):
        super().__init__(environment=environment, discount=discount, learning_rate=learning_rate)

        self.epsilon = epsilon
        self.epsilon_max = epsilon_max
        self.epsilon_min = epsilon_min
        self.epsilon_decay_duration = epsilon_decay_duration
        self.replay_buffer_size = replay_buffer_size
        self.warmup_steps = warmup_steps
        self.batch_size = batch_size
        self.target_update_frequency = target_update_frequency
        self.gradient_clipping_value = gradient_clipping_value
        self.cer = cer
        self.dueling = dueling
        self.device = device

        assert isinstance(environment.observation_space, gym.spaces.Box)
        n_state_features = len(environment.observation_space.low)
        assert isinstance(environment.action_space, gym.spaces.Discrete)
        self._n_actions = environment.action_space.n

        self.q_network = QNetwork(
            input_size=n_state_features,
            output_size=self._n_actions,
            n_hidden_layers=n_hidden_layers,
            hidden_layer_size=hidden_layer_size,
            activation=activation
        )

        self._target_q_network = deepcopy(self.q_network)
        self._replay_buffer = deque(maxlen=replay_buffer_size)
        self._optimizer = torch.optim.Adam(self.q_network.parameters(), lr=self.learning_rate)
        self._n_updates = 0

        self.q_network = self.q_network.to(self.device)
        self._target_q_network = self._target_q_network.to(self.device)

        # TODO: implement exponential decay
        if self.epsilon != "linear_decay" and not isinstance(self.epsilon, float):
            raise NotImplementedError
        if self.epsilon == "linear_decay":
            assert self.epsilon_max is not None and \
                   self.epsilon_min is not None and \
                   self.epsilon_decay_duration is not None

        if self.dueling:
            raise NotImplementedError

    def update(self) -> dict:
        stats = {}

        # Check if buffer has been filled in enough
        if len(self._replay_buffer) < self.warmup_steps:
            return stats

        # Enable training mode
        self.q_network.train(mode=True)

        # Clean up gradients
        self._optimizer.zero_grad()

        # Sample mini-batch of experiences
        experience_indices = self._rng.choice(len(self._replay_buffer), size=self.batch_size)
        experience_batch = [self._replay_buffer[i] for i in experience_indices]
        if self.cer:
            experience_batch[-1] = self._replay_buffer[-1]

        # Unpack experiences
        states = torch.as_tensor(
            data=np.asarray([e.state for e in experience_batch]),
            dtype=torch.float32,
            device=self.device
        )
        actions = torch.as_tensor(
            data=[e.action for e in experience_batch],
            dtype=torch.long,
            device=self.device
        )
        next_states = torch.as_tensor(
            data=np.asarray([e.next_state for e in experience_batch]),
            dtype=torch.float32,
            device=self.device
        )
        rewards = torch.as_tensor(
            data=[e.reward for e in experience_batch],
            dtype=torch.float32,
            device=self.device
        )
        dones = torch.as_tensor(
            data=[e.done for e in experience_batch],
            dtype=torch.bool,
            device=self.device
        )

        # Compute targets
        q_next = self._target_q_network(next_states)        # Q(s',a)
        assert q_next.shape == (self.batch_size, self._n_actions)
        targets = rewards + dones.logical_not() * self.discount * q_next.max(axis=1).values
        assert targets.shape == (self.batch_size,)

        # Forward pass
        q = self.q_network(states)                          # Q(s,a)
        assert q.shape == (self.batch_size, self._n_actions)
        q = q[torch.arange(self.batch_size), actions]       # Q(s,a*), where a* is the action taken in the experience
        assert q.shape == (self.batch_size,)
        loss = torch.nn.functional.mse_loss(targets, q)

        # Backward pass
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.q_network.parameters(), max_norm=self.gradient_clipping_value)
        self._optimizer.step()

        # Update target network
        self._n_updates += 1
        if (self._n_updates % self.target_update_frequency) == 0:
            self._target_q_network = deepcopy(self.q_network)

        # Disable training mode
        self.q_network.train(mode=False)

        # Save stats
        stats["loss"] = loss.item()
        return stats

    def record_experience(self, experience: Experience) -> None:
        self._replay_buffer.append(experience)

    def compute_action(self, *, state: np.ndarray, episode: int, explore: bool = True, **kwargs) -> int:
        _ = kwargs

        # Calculate epsilon
        if explore and self.epsilon == "linear_decay":      # if explore=False, we don't care about epsilon
            epsilon = max(
                self.epsilon_min,
                self.epsilon_max - (self.epsilon_max-self.epsilon_min) * (episode-1) / (self.epsilon_decay_duration-1)
            )
        else:
            epsilon = self.epsilon

        # Epsilon-greedy policy (or greedy policy if explore=False)
        if explore and random_decide(self._rng, epsilon):   # exploration (probability eps)
            action = self._rng.choice(self._n_actions)
        else:                                               # exploitation (probability 1-eps)
            state = torch.as_tensor(
                data=state.reshape((1,) + state.shape),
                dtype=torch.float32,
                device=self.device
            )
            q_values = self.q_network(state)
            assert q_values.shape[0] == 1
            action = q_values.argmax().item()

        return action

    def save(self, filepath, only_nn: bool = False):
        with open(filepath, mode="wb") as file:
            if only_nn:
                torch.save(self.q_network, file)
            else:
                pickle.dump(self, file)

    @staticmethod
    def load(filepath):
        with open(filepath, mode="r") as file:
            dqn = pickle.load(file)
        assert isinstance(dqn, DQN)
        return dqn