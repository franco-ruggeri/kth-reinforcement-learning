from pathlib import Path
from el2805.lab0.envs import Maze
from el2805.lab0.agents import DynamicProgrammingAgent, ValueIterationAgent
from utils import best_path


def main():
    horizon = 20
    for map_filepath in [
        Path(__file__).parent.parent / "data" / "maze.txt",
        Path(__file__).parent.parent / "data" / "maze_delay.txt",
    ]:
        env = Maze(map_filepath=map_filepath, horizon=horizon)
        agent = DynamicProgrammingAgent(env)
        agent.solve()
        # for t in range(horizon):
        #     print(f"Dynamic programming - Policy with {horizon-t} remaining time steps")
        #     env.render(mode="policy", policy=agent.policy[t])
        #     print()

        print("Dynamic programming - Shortest path")
        env.render(mode="policy", policy=best_path(env, agent))
        print()

        print("Value iteration - Stationary policy")
        env = Maze(map_filepath=map_filepath, discount=.99)
        agent = ValueIterationAgent(env)
        agent.solve()
        env.render(mode="policy", policy=agent._policy)
        print()


if __name__ == "__main__":
    main()