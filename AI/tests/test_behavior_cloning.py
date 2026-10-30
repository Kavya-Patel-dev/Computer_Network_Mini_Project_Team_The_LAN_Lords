import networkx as nx
import numpy as np
import pytest
import torch

from env.network_env import NetworkEnvConfig, NetworkRoutingEnv
from env.traffic import PoissonTrafficGenerator
from models.behavior_cloning import (ExpertExample, bc_optimizer_step,
                                     masked_bc_loss,
                                     split_graph_seed_blocks)
from models.gnn import PathScoringGATv2
from models.obs import ObservationWrapper


def ring_state(seed=17):
    graph = nx.cycle_graph(6)
    graph = nx.relabel_nodes(graph, {node: f"r{node}" for node in graph.nodes})
    for node in graph:
        graph.nodes[node].update(type="router", up=True)
    for u, v in graph.edges:
        graph[u][v].update(bandwidth=100.0, capacity=100.0, latency=2.0,
                           up=True, loss=0.0)
    env = NetworkRoutingEnv(
        graph,
        NetworkEnvConfig(k_paths=4, max_steps=20, intensity=0.1,
                         hosts_per_router_fraction=None, minimum_hosts=0),
        traffic_generator=PoissonTrafficGenerator(tuple(graph.nodes), demand_mbps=1.0),
    )
    observation, _info = env.reset(seed=seed)
    return ObservationWrapper(env, "bc-ring").process(observation)


def test_bc_loss_masks_invalid_actions_before_softmax_and_margin():
    q_values = torch.tensor([[0.2, 0.1, 100.0, -4.0]], requires_grad=True)
    mask = torch.tensor([[True, True, False, False]])
    actions = torch.tensor([0])
    total, cross_entropy, margin_loss = masked_bc_loss(q_values, mask, actions)
    expected_ce = torch.log(torch.exp(torch.tensor(0.2)) + torch.exp(torch.tensor(0.1))) - 0.2
    assert cross_entropy.item() == pytest.approx(expected_ce.item())
    assert margin_loss.item() == pytest.approx(0.7)
    assert total.item() == pytest.approx(expected_ce.item() + 0.7)
    total.backward()
    assert q_values.grad[0, 2].item() == 0.0
    assert q_values.grad[0, 3].item() == 0.0


def test_bc_margin_is_zero_when_expert_beats_every_valid_alternative_by_margin():
    q_values = torch.tensor([[1.0, 0.1, 500.0]])
    mask = torch.tensor([[True, True, False]])
    _total, _ce, margin_loss = masked_bc_loss(q_values, mask, torch.tensor([0]), 0.8)
    assert margin_loss.item() == 0.0


def test_expert_split_is_deterministic_blocked_and_train_only():
    blocks = [(graph, seed) for graph in ("train-a", "train-b")
              for seed in range(20000, 20032)]
    train, holdout = split_graph_seed_blocks(
        blocks, {"train-a", "train-b"}, {"locked-test"},
        holdout_fraction=0.125, seed=77)
    train_again, holdout_again = split_graph_seed_blocks(
        blocks, {"train-a", "train-b"}, {"locked-test"},
        holdout_fraction=0.125, seed=77)
    assert train == train_again
    assert holdout == holdout_again
    assert train.isdisjoint(holdout)
    assert train | holdout == set(blocks)
    assert {graph for graph, _seed in train | holdout} == {"train-a", "train-b"}
    for graph in ("train-a", "train-b"):
        graph_blocks = [block for block in blocks if block[0] == graph]
        held = sum(block in holdout for block in graph_blocks) / len(graph_blocks)
        assert 0.10 <= held <= 0.15
    with pytest.raises(ValueError, match="outside train split"):
        split_graph_seed_blocks([("locked-test", 1000)], {"train-a"},
                                {"locked-test"}, seed=77)


def test_bc_optimizer_update_is_deterministic_for_fixed_batch():
    state = ring_state(31)
    valid = np.flatnonzero(state.action_mask)
    assert len(valid) >= 1
    action = int(valid[0])
    batch = [ExpertExample(state, action, "train-ring", 20031),
             ExpertExample(state, action, "train-ring", 20031)]
    torch.set_num_threads(1)
    torch.manual_seed(812)
    first = PathScoringGATv2(actions=4, use_custom_collate=True)
    first_optimizer = torch.optim.Adam(first.parameters(), lr=5e-4)
    first_loss = bc_optimizer_step(first, first_optimizer, batch)

    torch.manual_seed(812)
    second = PathScoringGATv2(actions=4, use_custom_collate=True)
    second_optimizer = torch.optim.Adam(second.parameters(), lr=5e-4)
    second_loss = bc_optimizer_step(second, second_optimizer, batch)

    assert first_loss == pytest.approx(second_loss, abs=1e-8)
    for left, right in zip(first.parameters(), second.parameters()):
        assert torch.equal(left, right)
