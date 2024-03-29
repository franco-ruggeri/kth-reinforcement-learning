import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from tqdm import trange
from el2805.envs import MinotaurMaze
from el2805.envs.grid_world import Move
from el2805.envs.maze import MazeCell
from el2805.envs.minotaur_maze import Progress
from el2805.agents.mdp import MDPAgent, DynamicProgramming, ValueIteration
from el2805.agents.rl import RLAgent, QLearning, Sarsa
from utils import print_and_write_line, minotaur_maze_exit_probability, train_rl_agent_one_episode, plot_bar

SEED = 1


def task_c(map_filepath, results_dir):
    results_dir.mkdir(parents=True, exist_ok=True)

    environment = MinotaurMaze(map_filepath=map_filepath, horizon=20)
    agent = DynamicProgramming(environment=environment)
    agent.solve()

    done = False
    time_step = 0
    environment.seed(1)
    state = environment.reset()
    environment.render()
    while not done:
        action = agent.compute_action(state=state, time_step=time_step)
        state, _, done, _ = environment.step(action)
        time_step += 1
        environment.render()

    for t in [0, agent.policy.shape[0]-1]:
        policy = agent.policy[t]
        map_policy = np.zeros(environment.map.shape)
        minotaur_position = np.asarray(environment.map == MazeCell.EXIT).nonzero()
        minotaur_position = int(minotaur_position[0][0]), int(minotaur_position[1][0])

        for i in range(environment.map.shape[0]):
            for j in range(environment.map.shape[1]):
                try:
                    state = ((i, j), minotaur_position, Progress.WITH_KEYS)
                    s = environment.state_index(state)
                    map_policy[i, j] = policy[s]
                except KeyError:
                    map_policy[i, j] = Move.NOP

        print()
        print(f"Dynamic programming - Minotaur at exit and t={t+1}")
        environment.render(mode="policy", policy=map_policy)


def task_d(map_filepath, results_dir):
    results_dir.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots()
    write_mode = "w"
    for minotaur_nop in [False, True]:
        print(f"Minotaur NOP: {minotaur_nop}")
        horizons = np.arange(1, 31)

        # Trick: instead of solving for every min_horizon<=T<=max_horizon, we solve only for T=max_horizon.
        # Then, we read the results by hacking the policy to consider the last T time steps
        max_horizon = horizons[-1]
        environment = MinotaurMaze(map_filepath=map_filepath, horizon=max_horizon, minotaur_nop=minotaur_nop)
        agent = DynamicProgramming(environment=environment)
        agent.solve()
        full_policy = agent.policy.copy()

        exit_probabilities = []
        for horizon in horizons:
            agent.policy = full_policy[max_horizon - horizon:]  # trick
            environment.horizon = horizon

            exit_probability = minotaur_maze_exit_probability(environment, agent)
            exit_probabilities.append(exit_probability)

            print_and_write_line(
                filepath=results_dir / "results.txt",
                output=f"T={horizon} -> P('exit alive')={exit_probability}",
                mode=write_mode
            )
            write_mode = "a"    # append after the first time

        label = ("with " if minotaur_nop else "w/o ") + "stay move"
        axes.plot(horizons, exit_probabilities, marker="o", label=label)
    axes.set_xlabel("T")
    axes.set_ylabel(r"$\mathbb{P}$('exit alive')")
    axes.set_xticks(horizons[4::5])
    axes.legend()
    figure.savefig(results_dir / "probability_exit.pdf")
    figure.show()


def task_f(map_filepath, results_dir):
    results_dir.mkdir(parents=True, exist_ok=True)

    expected_life = 30
    environment = MinotaurMaze(map_filepath=map_filepath, probability_poison_death=1/expected_life)
    agent = ValueIteration(environment=environment, discount=1 - 1 / expected_life, precision=1e-2)
    agent.solve()

    exit_probability = minotaur_maze_exit_probability(environment, agent)
    print_and_write_line(
        filepath=results_dir / "results.txt",
        output=f"P('exit alive'|'poisoned')={exit_probability}",
        mode="w"
    )


def task_ij(map_filepath, results_dir):
    results_dir.mkdir(parents=True, exist_ok=True)

    expected_life = 50
    discount = 1 - 1/expected_life
    n_episodes = 50000

    environment = MinotaurMaze(
        map_filepath=map_filepath,
        minotaur_chase=True,
        keys=True,
        probability_poison_death=0  # important: we can sample better with infinite horizon
    )

    # Baseline: Value Iteration
    start_state = environment.reset()
    agent = ValueIteration(environment=environment, discount=discount, precision=1e-2)
    agent.solve()
    v = agent.v(start_state)
    values_baseline = np.full(n_episodes, v)
    x = np.arange(1, n_episodes+1)

    # TODO: update parameters below
    filename = "task_j3"
    figure, axes = plt.subplots()

    for delta, alpha in zip(
        [0.55, 0.55, 0.75, 0.75, 0.95, 0.95],
        [0.65, 0.85, 0.65, 0.85, 0.65, 0.85],
    ):
        label = rf"$\delta$={delta:.2f} - $\alpha$={alpha:.2f}"

        # agent = QLearning(
        agent = Sarsa(
            environment=environment,
            learning_rate="decay",
            discount=discount,
            alpha=alpha,
            epsilon="delta",
            delta=delta,
            q_init=1,
            seed=SEED
        )

        environment.seed(SEED)
        values = []
        for episode in trange(1, n_episodes+1, desc=label):
            train_rl_agent_one_episode(environment, agent, episode)
            v = agent.v(start_state)
            values.append(v)

        axes.plot(x, values, label=label)
    axes.plot(x, values_baseline, label="VI")
    axes.set_xlabel("number of episodes")
    axes.set_ylabel(r"V($s_0$)")
    axes.legend()
    figure.savefig(results_dir / f"{filename}.pdf")
    figure.show()


def task_k(map_filepath, results_dir):
    results_dir.mkdir(parents=True, exist_ok=True)

    expected_life = 50
    probability_poison_death = 1/expected_life
    discount = 1 - 1/expected_life

    environment = MinotaurMaze(
        map_filepath=map_filepath,
        minotaur_chase=True,
        keys=True,
        probability_poison_death=probability_poison_death
    )

    agent_vi = ValueIteration(environment=environment, discount=discount, precision=1e-2)

    agent_q_learning = QLearning(
        environment=environment,
        learning_rate="decay",
        discount=discount,
        alpha=0.55,
        epsilon=0.2,
        delta=None,
        q_init=0.01,
        seed=SEED
    )

    agent_sarsa = Sarsa(
        environment=environment,
        learning_rate="decay",
        discount=discount,
        alpha=0.65,
        epsilon="delta",
        delta=0.95,
        q_init=1,
        seed=SEED
    )

    write_mode = "w"
    n_episodes = 50000
    agents = [agent_vi, agent_q_learning, agent_sarsa]
    agent_names = ["vi", "q_learning", "sarsa"]
    exit_probabilities = []
    for agent_name, agent in zip(agent_names, agents):
        # Train or solve
        if isinstance(agent, RLAgent):
            agent.train(n_episodes)
        elif isinstance(agent, MDPAgent):
            agent.solve()
        else:
            raise ValueError

        # Test
        exit_probability = minotaur_maze_exit_probability(environment, agent)
        exit_probabilities.append(exit_probability)
        print_and_write_line(
            filepath=results_dir / "results.txt",
            output=f"{agent_name}: P('exit alive'|'poisoned')={exit_probability}",
            mode=write_mode
        )
        write_mode = "a"    # append after the first time
        print()

    plot_bar(
        heights=exit_probabilities,
        x_tick_labels=agent_names,
        y_label=r"$\mathbb{P}$('exit alive')",
        filepath=results_dir / "probability_exit.pdf"
    )


def main():
    results_dir = Path(__file__).parent.parent / "results" / "lab1" / "problem1"
    map_filepath = Path(__file__).parent.parent / "data" / "maze_minotaur.txt"
    map_filepath_key = Path(__file__).parent.parent / "data" / "maze_minotaur_key.txt"

    print("Task (c)")
    task_c(map_filepath, results_dir / "task_c")
    print()

    print("Task (d)")
    task_d(map_filepath, results_dir / "task_d")
    print()

    print("Task (f)")
    task_f(map_filepath, results_dir / "task_f")
    print()

    print("Task (i-j)")
    task_ij(map_filepath_key, results_dir / "task_ij")
    print()

    print("Task (k)")
    task_k(map_filepath_key, results_dir / "task_k")
    print()


if __name__ == "__main__":
    main()
