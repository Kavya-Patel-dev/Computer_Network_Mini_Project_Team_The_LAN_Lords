import gc
import itertools
from dataclasses import replace

import numpy as np
import pytest
import torch

from models.day5_variants import (
    NStepAccumulator,
    VariantDQNAgent,
    VariantReplay,
    VariantTransition,
    auxiliary_utilization_targets,
    beta_at,
    initialize_from_checkpoint,
    masked_double_dqn_nstep_targets,
    planned_update_count,
)
import models.day5_variants as day5_variants
from models.dqn import DoubleDQNAgent
from models.gnn import PathScoringGATv2
from models.obs import ModelState

from test_day4_agent import make_state


def history_state(seed=901):
    state = make_state(6, seed)
    return ModelState(
        state.graph_id, state.node_features, state.edge_index, state.edge_attr,
        state.flow_features, state.candidate_paths, state.candidate_features,
        state.action_mask,
        np.stack([state.node_features.copy() for _ in range(4)]),
        np.stack([state.edge_attr.copy() for _ in range(4)]),
    )


def state_with_edge_utilization(state, values, *, edge_index=None,
                                node_features=None):
    edge_attr = state.edge_attr.copy()
    edge_attr[:, 0] = np.asarray(values, dtype=np.float32)
    return replace(
        state,
        edge_index=(state.edge_index if edge_index is None else edge_index),
        edge_attr=edge_attr,
        node_features=(state.node_features if node_features is None else node_features),
    )


def test_day4_flag_off_model_preserves_bc_checkpoint_q_values_within_one_e_minus_six():
    state = make_state(6, 902)
    payload = torch.load("runs/day5/bc_init.pt", map_location="cpu",
                         weights_only=False)
    day4_agent = DoubleDQNAgent(actions=4, seed=10)
    day4_agent.load("runs/day5/bc_init.pt")
    variant_agent = VariantDQNAgent(flags={}, seed=11)
    init = initialize_from_checkpoint(variant_agent.online, "runs/day5/bc_init.pt")
    with torch.no_grad():
        day4_q = torch.as_tensor(day4_agent.q_values(state))
        variant_q = torch.as_tensor(variant_agent.q_values(state))
    assert init["copied_tensors"] == len(payload["online"])
    finite = torch.isfinite(day4_q) & torch.isfinite(variant_q)
    assert torch.allclose(day4_q[finite], variant_q[finite], atol=1e-6, rtol=0.0)


def test_dueling_valid_action_mean_masks_invalid_and_single_valid_q_is_value():
    state = make_state(6, 903)
    valid_action = int(np.flatnonzero(state.action_mask)[0])
    mask = np.zeros_like(state.action_mask)
    mask[valid_action] = True
    state = ModelState(state.graph_id, state.node_features, state.edge_index,
                       state.edge_attr, state.flow_features, state.candidate_paths,
                       state.candidate_features, mask)
    model = PathScoringGATv2(actions=4, dueling=True)
    model.eval()
    with torch.no_grad():
        q_values, _ = model(state)
        embeddings, _ptr = model._encode_nodes([state])
        graph_value_input = torch.cat((embeddings.mean(0), embeddings.max(0).values,
                                       torch.as_tensor(state.flow_features)))
        expected_value = model.value_head(graph_value_input).squeeze()
    assert q_values[0, valid_action].item() == pytest.approx(expected_value.item(), abs=1e-6)
    assert torch.isneginf(q_values[0, ~torch.as_tensor(mask)]).all()


def test_nstep_returns_match_bruteforce_and_truncation_preserves_bootstrap():
    state = make_state(6, 904)
    action = int(np.flatnonzero(state.action_mask)[0])
    acc = NStepAccumulator(n=3, gamma=0.5)
    emitted = []
    for index, reward in enumerate((1.0, 2.0, 3.0, 4.0)):
        emitted.extend(acc.append(VariantTransition(
            state, action, reward, state, False, index == 3), episode_id="ep-a"))
    assert [row.reward for row in emitted] == pytest.approx([2.75, 4.5, 5.0, 4.0])
    assert [row.n_steps for row in emitted] == [3, 3, 2, 1]
    assert [row.truncated for row in emitted] == [False, True, True, True]

    rewards = torch.tensor([2.75, 2.75])
    horizons = torch.tensor([3.0, 3.0])
    terminated = torch.tensor([False, True])
    online_next = torch.tensor([[1.0, 3.0], [1.0, 3.0]])
    target_next = torch.tensor([[5.0, 7.0], [5.0, 7.0]])
    mask = torch.tensor([[True, False], [True, False]])
    targets = masked_double_dqn_nstep_targets(
        rewards, horizons, terminated, online_next, target_next, mask, 0.5)
    assert targets.tolist() == pytest.approx([2.75 + 0.5**3 * 5.0, 2.75])


def test_nstep_flush_uses_final_state_when_unstored_decision_ends_episode():
    first, final = make_state(6, 905), make_state(6, 906)
    action = int(np.flatnonzero(first.action_mask)[0])
    acc = NStepAccumulator(3, 0.5)
    acc.append(VariantTransition(first, action, 1.0, first, False, False), 1)
    rows = acc.flush(1, final, truncated=True)
    assert len(rows) == 1
    assert rows[0].next_state.graph_id == final.graph_id
    assert rows[0].truncated is True


def test_prioritized_replay_probabilities_weights_updates_and_beta_schedule():
    state = make_state(6, 907)
    action = int(np.flatnonzero(state.action_mask)[0])
    replay = VariantReplay(capacity=4, prioritized=True, alpha=0.6, seed=10)
    for _ in range(3):
        replay.add(VariantTransition(state, action, 0.0, state, False, False))
    replay.update_priorities([0, 1, 2], [0.0, 1.0, 3.0])
    raw = np.power(np.asarray([0.001, 1.001, 3.001]), 0.6)
    expected_probs = raw / raw.sum()
    for index, expected in enumerate(expected_probs):
        assert replay.tree.tree[replay.tree.leaf_count + index] / replay.tree.total == pytest.approx(expected)
    sample, indices, weights, probs = replay.sample(3, beta=0.7)
    assert len(sample) == 3 and len(indices) == 3
    expected_weights = np.power(3 * probs, -0.7)
    expected_weights /= expected_weights.max()
    assert weights == pytest.approx(expected_weights.astype(np.float32))
    replay.update_priorities(indices, np.full(3, 7.0))
    assert replay.max_priority == pytest.approx(7.001)
    assert beta_at(0, 100) == pytest.approx(0.4)
    assert beta_at(100, 100) == pytest.approx(1.0)
    assert planned_update_count(3_000) == 250
    assert beta_at(planned_update_count(3_000), planned_update_count(3_000)) == pytest.approx(1.0)


def test_noisy_net_is_deterministic_in_evaluation_and_stochastic_while_training():
    state = make_state(6, 908)
    model = PathScoringGATv2(actions=4, noisy_net=True)
    model.eval()
    with torch.no_grad():
        first, _ = model(state)
        model.reset_noise()
        second, _ = model(state)
    assert torch.equal(first, second)
    model.train()
    model.reset_noise()
    with torch.no_grad():
        third, _ = model(state)
    model.reset_noise()
    with torch.no_grad():
        fourth, _ = model(state)
    assert not torch.equal(third, fourth)


def test_noisy_action_selection_ignores_epsilon_and_target_noise_is_off():
    state = make_state(6, 920)
    agent = VariantDQNAgent(flags={"noisy_net": True}, seed=921)
    class EpsilonMustNotBeRead:
        def random(self):
            raise AssertionError("epsilon RNG must be bypassed in NoisyNet mode")
    action = agent.select_action(state, epsilon=1.0, rng=EpsilonMustNotBeRead())
    assert state.action_mask[action]
    from models.gnn import FactorizedNoisyLinear
    target_layers = [module for module in agent.target.modules()
                     if isinstance(module, FactorizedNoisyLinear)]
    assert target_layers and all(not layer.training for layer in target_layers)


def test_gru_history_shapes_and_auxiliary_targets_align_to_next_edge_order():
    state = history_state(909)
    model = PathScoringGATv2(actions=4, gru_history=True,
                             auxiliary_utilization=True)
    q_values, attention = model(state)
    assert q_values.shape == (1, 4)
    assert attention.shape == (1, 4, state.num_nodes)
    predictions, backbone_mask = model.auxiliary_predictions(state)[0]
    targets, target_mask = auxiliary_utilization_targets(state)
    assert predictions.shape == targets.shape == (state.edge_index.shape[1],)
    assert torch.equal(backbone_mask, target_mask)
    assert torch.equal(targets, torch.as_tensor(state.edge_attr[:, 0]).clamp(0, 2))
    assert torch.isfinite(predictions).all()


def test_batched_auxiliary_prediction_matches_per_state_loss_and_gradients_within_one_e_minus_six():
    states = [make_state(6, 933), make_state(7, 934), make_state(5, 935)]
    torch.manual_seed(936)
    per_state = PathScoringGATv2(actions=4, use_custom_collate=True,
                                 auxiliary_utilization=True)
    batched = PathScoringGATv2(actions=4, use_custom_collate=True,
                               auxiliary_utilization=True)
    batched.load_state_dict(per_state.state_dict())

    def auxiliary_loss(model, use_batch):
        predictions = (model.auxiliary_predictions(states) if use_batch else
                       [model.auxiliary_predictions([state])[0]
                        for state in states])
        losses = []
        for state, (predicted, router_mask) in zip(states, predictions):
            target, target_mask = auxiliary_utilization_targets(state)
            mask = router_mask & target_mask
            losses.append(torch.nn.functional.smooth_l1_loss(
                predicted[mask], target[mask]))
        return torch.stack(losses).mean(), predictions

    loop_loss, loop_predictions = auxiliary_loss(per_state, False)
    batch_loss, batch_predictions = auxiliary_loss(batched, True)
    assert torch.allclose(loop_loss, batch_loss, atol=1e-6, rtol=0.0)
    for (loop_values, loop_mask), (batch_values, batch_mask) in zip(
            loop_predictions, batch_predictions):
        assert torch.equal(loop_mask, batch_mask)
        assert torch.allclose(loop_values, batch_values, atol=1e-6, rtol=0.0)

    loop_loss.backward()
    batch_loss.backward()
    for (loop_name, loop_param), (batch_name, batch_param) in zip(
            per_state.named_parameters(), batched.named_parameters()):
        assert loop_name == batch_name
        assert (loop_param.grad is None) == (batch_param.grad is None)
        if loop_param.grad is not None:
            assert torch.allclose(loop_param.grad, batch_param.grad,
                                  atol=1e-6, rtol=0.0), loop_name


def test_float16_replay_history_reduces_payload_with_q_error_below_one_e_minus_three():
    state = history_state(916)
    action = int(np.flatnonzero(state.action_mask)[0])
    replay = VariantReplay(capacity=4, compact_history=True, seed=17)
    replay.add(VariantTransition(state, action, 0.0, state, False, False))
    stored = replay.items[0].state
    assert stored.history_node_features.dtype == np.float16
    assert stored.history_edge_attr.dtype == np.float16
    full_bytes = (state.history_node_features.nbytes
                  + state.history_edge_attr.nbytes)
    compact_bytes = (stored.history_node_features.nbytes
                     + stored.history_edge_attr.nbytes)
    assert compact_bytes == full_bytes // 2
    model = PathScoringGATv2(actions=4, gru_history=True)
    model.eval()
    with torch.no_grad():
        original_q, _ = model(state)
        compact_q, _ = model(stored)
    valid = torch.isfinite(original_q) & torch.isfinite(compact_q)
    assert (original_q[valid] - compact_q[valid]).abs().max().item() < 1e-3


def test_variant_initialization_and_replay_sampling_are_deterministic():
    state = make_state(6, 917)
    action = int(np.flatnonzero(state.action_mask)[0])
    first = VariantReplay(capacity=8, prioritized=False, seed=918)
    second = VariantReplay(capacity=8, prioritized=False, seed=918)
    for index in range(8):
        row = VariantTransition(state, action, float(index), state, False, False)
        first.add(row)
        second.add(row)
    assert first.sample(5)[1].tolist() == second.sample(5)[1].tolist()
    torch.manual_seed(919)
    first_model = PathScoringGATv2(actions=4, dueling=True)
    torch.manual_seed(919)
    second_model = PathScoringGATv2(actions=4, dueling=True)
    first_model.eval()
    second_model.eval()
    with torch.no_grad():
        first_q, _ = first_model(state)
        second_q, _ = second_model(state)
    assert torch.equal(first_q, second_q)


def test_auxiliary_head_uses_next_snapshot_edge_rows_and_ignores_host_access_edges():
    state = history_state(910)
    next_edges = state.edge_attr.copy()
    next_edges[:, 0] = np.arange(len(next_edges), dtype=np.float32) / 10.0
    nodes = state.node_features.copy()
    nodes[0, 2] = 1.0
    next_state = ModelState(state.graph_id, nodes, state.edge_index, next_edges,
                            state.flow_features, state.candidate_paths,
                            state.candidate_features, state.action_mask,
                            state.history_node_features, state.history_edge_attr)
    targets, mask = auxiliary_utilization_targets(next_state)
    current_targets, _current_mask = auxiliary_utilization_targets(state)
    assert targets.tolist() == pytest.approx(np.arange(len(next_edges)) / 10.0)
    assert not torch.equal(targets, current_targets)
    endpoints = next_state.edge_index
    host_incident = ((endpoints[0] == 0) | (endpoints[1] == 0))
    assert not mask[torch.as_tensor(host_incident)].any()
    assert mask.sum().item() == len(next_edges) - int(host_incident.sum())


def test_auxiliary_update_predicts_from_current_and_targets_aligned_next_with_gradients(
        monkeypatch):
    base = history_state(941)
    action = int(np.flatnonzero(base.action_mask)[0])
    rows = []
    for index, (current_util, next_util) in enumerate(((0.11, 0.71), (0.22, 0.82))):
        current = state_with_edge_utilization(
            base, np.full(base.edge_attr.shape[0], current_util))
        next_state = state_with_edge_utilization(
            base, np.full(base.edge_attr.shape[0], next_util))
        rows.append((current, next_state))

    agent = VariantDQNAgent(
        flags={"auxiliary_utilization": True}, batch_size=2,
        learning_starts=2, replay_capacity=8, seed=942)
    for current, next_state in rows:
        agent.replay.add(VariantTransition(
            current, action, 0.0, next_state, False, False))

    prediction_inputs = []
    target_inputs = []
    original_predict = agent.online.auxiliary_predictions
    original_targets = day5_variants.auxiliary_utilization_targets

    def capture_predict(states):
        prediction_inputs.extend(states)
        return original_predict(states)

    def capture_targets(state):
        target_inputs.append(state)
        return original_targets(state)

    monkeypatch.setattr(agent.online, "auxiliary_predictions", capture_predict)
    monkeypatch.setattr(day5_variants, "auxiliary_utilization_targets", capture_targets)
    loss = agent.update()

    assert loss is not None and np.isfinite(loss)
    assert sorted(round(float(state.edge_attr[:, 0].mean()), 2)
                  for state in prediction_inputs) == [0.11, 0.22]
    assert sorted(round(float(state.edge_attr[:, 0].mean()), 2)
                  for state in target_inputs) == [0.71, 0.82]
    assert len(prediction_inputs) == len(target_inputs) == 2
    aux_grads = [parameter.grad for parameter in agent.online.auxiliary_head.parameters()]
    assert aux_grads and all(grad is not None and torch.isfinite(grad).all()
                             for grad in aux_grads)
    assert any(torch.count_nonzero(grad).item() for grad in aux_grads)


def test_auxiliary_update_rejects_mismatched_static_edge_row_order():
    state = history_state(943)
    action = int(np.flatnonzero(state.action_mask)[0])
    permutation = np.arange(state.edge_index.shape[1])[::-1].copy()
    mismatched_next = state_with_edge_utilization(
        state, np.linspace(0.1, 0.9, state.edge_attr.shape[0]),
        edge_index=state.edge_index[:, permutation],
    )
    # Keep edge attributes associated with their reordered edge rows. The
    # topology is equivalent, but the row order no longer matches the input.
    mismatched_next = replace(mismatched_next,
                              edge_attr=mismatched_next.edge_attr[permutation])
    agent = VariantDQNAgent(
        flags={"auxiliary_utilization": True}, batch_size=1,
        learning_starts=1, replay_capacity=4, seed=944)
    agent.replay.add(VariantTransition(
        state, action, 0.0, mismatched_next, False, False))
    with pytest.raises(ValueError, match="matching current/next static edge order"):
        agent.update()


def test_auxiliary_update_masks_next_state_host_edges_from_utilization_loss(
        monkeypatch):
    state = history_state(945)
    action = int(np.flatnonzero(state.action_mask)[0])
    nodes = state.node_features.copy()
    nodes[0, 2] = 1.0
    next_state = state_with_edge_utilization(
        state, np.linspace(0.1, 0.9, state.edge_attr.shape[0]),
        node_features=nodes)
    agent = VariantDQNAgent(
        flags={"auxiliary_utilization": True}, batch_size=1,
        learning_starts=1, replay_capacity=4, seed=946)
    agent.replay.add(VariantTransition(
        state, action, 0.0, next_state, False, False))

    prediction = torch.linspace(0.15, 0.85, state.edge_attr.shape[0],
                                requires_grad=True)
    monkeypatch.setattr(
        agent.online, "auxiliary_predictions",
        lambda states: [(prediction, torch.ones_like(prediction, dtype=torch.bool))])
    loss = agent.update()

    _targets, valid_mask = auxiliary_utilization_targets(next_state)
    incident_host = ((torch.tensor(state.edge_index[0].copy()) == 0)
                     | (torch.tensor(state.edge_index[1].copy()) == 0))
    assert not valid_mask[incident_host].any()
    assert loss is not None and np.isfinite(loss)
    assert prediction.grad is not None and torch.isfinite(prediction.grad).all()
    assert torch.count_nonzero(prediction.grad[~valid_mask]).item() == 0
    assert torch.count_nonzero(prediction.grad[valid_mask]).item() > 0


def test_mlp_encoder_output_is_invariant_to_permuted_or_removed_edge_index():
    state = make_state(6, 911)
    model = PathScoringGATv2(actions=4, use_mlp_encoder=True)
    model.eval()
    permutation = np.arange(state.edge_index.shape[1])[::-1]
    permuted_edges = ModelState(
        state.graph_id, state.node_features, state.edge_index[:, permutation],
        state.edge_attr[permutation], state.flow_features, state.candidate_paths,
        state.candidate_features, state.action_mask)
    empty_edges = ModelState(
        state.graph_id, state.node_features, np.empty((2, 0), dtype=np.int64),
        state.edge_attr[:0], state.flow_features, state.candidate_paths,
        state.candidate_features, state.action_mask)
    with torch.no_grad():
        expected, _ = model(state)
        permuted, _ = model(permuted_edges)
        observed, _ = model(empty_edges)
    assert torch.allclose(expected, permuted, atol=1e-6, rtol=0.0)
    assert torch.allclose(expected, observed, atol=1e-6, rtol=0.0)


def test_nstep_and_prioritized_replay_interaction_has_finite_update():
    state = make_state(6, 912)
    action = int(np.flatnonzero(state.action_mask)[0])
    agent = VariantDQNAgent(flags={"dueling": True}, batch_size=2,
                            learning_starts=2, replay_capacity=16,
                            prioritized=True, n_step=3, seed=913)
    for index in range(4):
        agent.add_transition(VariantTransition(
            state, action, 0.25, state, False, index == 3), episode_id=0)
    loss = agent.update()
    assert loss is not None and np.isfinite(loss)
    assert agent.updates == 1


@pytest.mark.parametrize("dueling,noisy,gru,mlp,aux", list(itertools.product(
    (False, True), repeat=5)))
def test_checkpoint_roundtrip_q_values_within_one_e_minus_six_for_each_flag_combo(
        tmp_path, dueling, noisy, gru, mlp, aux):
    state = history_state(914)
    flags = {"dueling": dueling, "noisy_net": noisy,
             "gru_history": gru, "mlp_encoder": mlp,
             "auxiliary_utilization": aux}
    torch.manual_seed(915)
    agent = VariantDQNAgent(flags=flags, seed=915, learning_starts=2)
    expected = agent.q_values(state)
    checkpoint = tmp_path / "agent.pt"
    agent.save(str(checkpoint), {"flags": flags})
    loaded = VariantDQNAgent(flags=flags, seed=916, learning_starts=2)
    loaded.load(str(checkpoint))
    observed = loaded.q_values(state)
    valid = np.isfinite(expected) & np.isfinite(observed)
    assert np.max(np.abs(expected[valid] - observed[valid])) < 1e-6
    del agent, loaded
    gc.collect()
