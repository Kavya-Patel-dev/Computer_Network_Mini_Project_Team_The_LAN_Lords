import numpy as np
import networkx as nx
import pytest
import torch

from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import PoissonTrafficGenerator
from models.data_guard import SplitLeakageError, guard_graph_request
from models.dqn import (DoubleDQNAgent, double_dqn_targets, learning_done)
from models.gnn import PathScoringGATv2
from models.harness import FlowLatencyCapture
from models.obs import ModelState, ObservationWrapper


def ring(size: int) -> nx.Graph:
    graph = nx.cycle_graph(size)
    for node in graph:
        graph.nodes[node]["type"] = "router"
        graph.nodes[node]["up"] = True
    for u, v in graph.edges:
        graph[u][v].update(bandwidth=100.0, capacity=100.0, latency=2.0,
                           up=True, loss=0.0)
    return graph


def make_state(size: int = 4, seed: int = 17) -> ModelState:
    graph = ring(size)
    # Preserve string node labels just as Day 1 topology loaders do.
    graph = nx.relabel_nodes(graph, {n: str(n) for n in graph.nodes})
    generator = PoissonTrafficGenerator(tuple(graph.nodes), demand_mbps=1.0)
    env = NetworkRoutingEnv(
        graph,
        NetworkEnvConfig(k_paths=4, max_steps=25, intensity=0.1,
                         hosts_per_router_fraction=None, minimum_hosts=0),
        traffic_generator=generator,
    )
    observation, _ = env.reset(seed=seed)
    return ObservationWrapper(env, f"ring-{size}").process(observation)


def test_observation_wrapper_bidirectional_edges_and_feature_shapes():
    state = make_state(5)
    assert state.node_features.shape == (5, 6)
    assert state.edge_index.shape == (2, 2 * 5)
    assert state.edge_attr.shape == (2 * 5, 5)
    assert state.flow_features.shape == (7,)
    assert state.candidate_features.shape == (4, 6)
    assert state.candidate_paths.shape == (4, 5)
    assert state.action_mask.shape == (4,)
    assert np.array_equal(state.edge_index[:, 5:], state.edge_index[::-1, :5])
    assert np.array_equal(state.edge_attr[5:], state.edge_attr[:5])
    assert np.isfinite(state.node_features).all()
    assert np.isfinite(state.edge_attr).all()


def test_gatv2_batches_different_topology_sizes_and_masks_q_values():
    states = [make_state(4, 1), make_state(6, 2)]
    model = PathScoringGATv2(actions=4)
    q_values, attention = model(states)
    assert q_values.shape == (2, 4)
    assert attention.shape == (2, 4, 6)
    assert torch.isfinite(q_values[torch.isfinite(q_values)]).all()
    for i, state in enumerate(states):
        mask = torch.as_tensor(state.action_mask, dtype=torch.bool)
        assert torch.isneginf(q_values[i, ~mask]).all()
        for action in torch.where(mask)[0]:
            weights = attention[i, action]
            assert torch.isfinite(weights).all()
            assert weights.sum().item() == pytest.approx(1.0)
    valid_actions = [int(np.flatnonzero(s.action_mask)[0]) for s in states]
    selected = q_values.gather(1, torch.tensor(valid_actions).view(-1, 1)).squeeze(1)
    loss = selected.square().mean()
    loss.backward()
    assert all(p.grad is None or torch.isfinite(p.grad).all()
               for p in model.parameters())


def test_gatv2_reuses_cached_edge_index_for_replay_states():
    state = make_state(6)
    model = PathScoringGATv2(actions=4)
    model(state)
    cache_key = (state.graph_id, id(state.edge_index))
    cached_tensor = model._edge_index_cache[cache_key][1]

    model(state.replay_copy())

    assert model._edge_index_cache[cache_key][1] is cached_tensor
    assert len(model._edge_index_cache) == 1


def test_masked_actions_never_selected_over_1000_random_masks():
    agent = DoubleDQNAgent(actions=4, seed=9)
    base = make_state(5, 4)
    rng = np.random.default_rng(42)
    for _ in range(1000):
        mask = rng.integers(0, 2, size=4, dtype=np.int8).astype(bool)
        state = ModelState(base.graph_id, base.node_features, base.edge_index,
                           base.edge_attr, base.flow_features,
                           base.candidate_paths, base.candidate_features, mask)
        action = agent.select_action(state, epsilon=1.0, rng=rng)
        if not mask.any():
            assert action == 4  # valid idle sentinel
        else:
            assert mask[action]


def test_checkpoint_reload_preserves_q_values(tmp_path):
    state = make_state(5, 10)
    first = DoubleDQNAgent(actions=4, seed=12)
    expected = first.q_values(state)
    path = tmp_path / "agent.pt"
    first.save(str(path), {"stage": "test"})
    second = DoubleDQNAgent(actions=4, seed=99)
    second.load(str(path))
    observed = second.q_values(state)
    valid = state.action_mask
    assert np.max(np.abs(expected[valid] - observed[valid])) < 1e-6


def test_double_dqn_bootstraps_on_truncation_but_not_termination():
    rewards = torch.tensor([1.0, 2.0])
    terminated = torch.tensor([False, True])
    truncated = [True, False]
    online = torch.tensor([[1.0, 5.0, -torch.inf], [3.0, 2.0, 1.0]])
    target = torch.tensor([[7.0, 11.0, -torch.inf], [13.0, 17.0, 19.0]])
    mask = torch.tensor([[True, True, False], [True, True, True]])
    result = double_dqn_targets(rewards, terminated, online, target, mask, 0.95)
    assert learning_done(False, truncated[0]) is False
    assert learning_done(True, truncated[1]) is True
    # Online selects action 1; target evaluates action 1, even at truncation.
    assert result.tolist() == pytest.approx([1.0 + 0.95 * 11.0, 2.0])


def test_locked_holdout_graph_guard_raises_before_loading():
    partitions = {
        "train": [{"name": "train-only"}],
        "val": [{"name": "validation-only"}],
        "test": [{"name": "holdout-only"}],
    }
    with pytest.raises(SplitLeakageError, match="cannot be loaded"):
        guard_graph_request({"name": "holdout-only", "split": "test"},
                            "train", partitions)
    with pytest.raises(SplitLeakageError, match="requested train partition"):
        guard_graph_request({"name": "validation-only", "split": "val"},
                            "train", partitions)


def test_reward_scaling_only_clips_in_wrapper_range():
    assert ObservationWrapper.scale_reward(-9.0) == (-5.0, True)
    assert ObservationWrapper.scale_reward(1.5) == (1.5, False)
    assert ObservationWrapper.scale_reward(4.0) == (2.0, True)


def test_latency_cap_fraction_uses_routed_flows_as_denominator():
    capture = FlowLatencyCapture(measured_decisions=10, routed_flows=4,
                                 capped_flows=2)
    assert capture.fraction_capped == pytest.approx(0.5)
