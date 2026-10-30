import numpy as np
import torch

from models.dqn import DoubleDQNAgent, Transition
from models.fast_replay import TensorModelState, custom_collate, tensorize_state
from models.gnn import PathScoringGATv2
from models.obs import ModelState

from test_day4_agent import make_state


def test_custom_collate_matches_pyg_path_within_one_e_minus_six():
    states = [make_state(5, 21), make_state(6, 22), make_state(5, 23)]
    pytorch_batch_model = PathScoringGATv2(actions=4)
    custom_batch_model = PathScoringGATv2(actions=4, use_custom_collate=True)
    custom_batch_model.load_state_dict(pytorch_batch_model.state_dict())
    pytorch_batch_model.eval()
    custom_batch_model.eval()

    with torch.no_grad():
        expected_q, expected_attention = pytorch_batch_model(states)
        observed_q, observed_attention = custom_batch_model(states)

    assert torch.allclose(expected_q, observed_q, atol=1e-6, rtol=0.0)
    assert torch.allclose(expected_attention, observed_attention,
                          atol=1e-6, rtol=0.0)
    batch = custom_collate(states)
    assert batch.ptr.tolist() == [0, 5, 11, 16]
    assert batch.edge_index.shape[1] == sum(s.edge_index.shape[1] for s in states)
    tensor_states = [tensorize_state(
        state, torch.tensor(np.asarray(state.edge_index), dtype=torch.long))
        for state in states]
    with torch.no_grad():
        tensor_q, tensor_attention = custom_batch_model(tensor_states)
    assert torch.allclose(expected_q, tensor_q, atol=1e-6, rtol=0.0)
    assert torch.allclose(expected_attention, tensor_attention,
                          atol=1e-6, rtol=0.0)


def test_tensor_replay_stores_ready_tensors_and_reuses_identical_states():
    state = make_state(6, 31)
    agent = DoubleDQNAgent(actions=4, batch_size=4, replay_capacity=16,
                           learning_starts=4, seed=32,
                           store_tensor_replay=True, use_custom_collate=True,
                           reuse_duplicate_states=True)
    action = int(np.flatnonzero(state.action_mask)[0])
    for _ in range(4):
        agent.replay.add(Transition(state, action, 0.25, state, False, False))

    stored = agent.replay.sample(1)[0]
    assert isinstance(stored.state, TensorModelState)
    assert isinstance(stored.state.node_features, torch.Tensor)
    assert stored.state.edge_index is stored.next_state.edge_index
    loss = agent.update()
    assert loss is not None and np.isfinite(loss)
    assert agent.updates == 1
    assert all(value >= 0.0 for value in agent.last_update_timings_ms.values())


def test_duplicate_state_reuse_matches_reference_update_loss_within_one_e_minus_six():
    state = make_state(6, 41)
    action = int(np.flatnonzero(state.action_mask)[0])
    agents = [
        DoubleDQNAgent(actions=4, batch_size=4, replay_capacity=16,
                       learning_starts=4, seed=42),
        DoubleDQNAgent(actions=4, batch_size=4, replay_capacity=16,
                       learning_starts=4, seed=42,
                       store_tensor_replay=True, use_custom_collate=True,
                       reuse_duplicate_states=True),
    ]
    losses = []
    for agent in agents:
        for _ in range(8):
            agent.replay.add(Transition(state, action, 0.25, state, False, False))
        loss = agent.update()
        assert loss is not None
        losses.append(loss)
    assert np.isclose(losses[0], losses[1], atol=1e-6, rtol=0.0)
