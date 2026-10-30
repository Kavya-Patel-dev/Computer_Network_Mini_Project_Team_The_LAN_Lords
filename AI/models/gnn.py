"""Topology-size-independent GATv2 encoder and attention path scorer."""
from __future__ import annotations

import time
from dataclasses import replace
from typing import Sequence

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch_geometric.data import Batch, Data
from torch_geometric.nn import GATv2Conv

from .obs import ModelState
from .fast_replay import TensorModelState, custom_collate


class FactorizedNoisyLinear(nn.Module):
    """Factorized Gaussian NoisyNet layer; evaluation always uses mu weights."""

    def __init__(self, in_features: int, out_features: int,
                 sigma0: float = 0.1) -> None:
        super().__init__()
        self.in_features, self.out_features = int(in_features), int(out_features)
        self.weight_mu = nn.Parameter(torch.empty(out_features, in_features))
        self.weight_sigma = nn.Parameter(torch.empty(out_features, in_features))
        self.bias_mu = nn.Parameter(torch.empty(out_features))
        self.bias_sigma = nn.Parameter(torch.empty(out_features))
        self.register_buffer("weight_epsilon", torch.zeros(out_features, in_features))
        self.register_buffer("bias_epsilon", torch.zeros(out_features))
        bound = 1.0 / in_features ** 0.5
        nn.init.uniform_(self.weight_mu, -bound, bound)
        nn.init.uniform_(self.bias_mu, -bound, bound)
        nn.init.constant_(self.weight_sigma, float(sigma0) / in_features ** 0.5)
        nn.init.constant_(self.bias_sigma, float(sigma0) / out_features ** 0.5)
        self.reset_noise()

    @staticmethod
    def _noise(size: int, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
        value = torch.randn(size, device=device, dtype=dtype)
        return value.sign() * value.abs().sqrt()

    @torch.no_grad()
    def reset_noise(self) -> None:
        incoming = self._noise(self.in_features, self.weight_mu.device,
                               self.weight_mu.dtype)
        outgoing = self._noise(self.out_features, self.weight_mu.device,
                               self.weight_mu.dtype)
        self.weight_epsilon.copy_(outgoing.outer(incoming))
        self.bias_epsilon.copy_(outgoing)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        if self.training:
            weight = self.weight_mu + self.weight_sigma * self.weight_epsilon
            bias = self.bias_mu + self.bias_sigma * self.bias_epsilon
        else:
            weight, bias = self.weight_mu, self.bias_mu
        return F.linear(values, weight, bias)


class PathScoringGATv2(nn.Module):
    """Score K candidate paths for each graph in a variable-size PyG batch."""

    def __init__(self, node_features: int = 6, edge_features: int = 5,
                 flow_features: int = 7, candidate_features: int = 6,
                 actions: int = 4, use_third_layer: bool = False,
                 use_custom_collate: bool = False, *,
                 dueling: bool = False, noisy_net: bool = False,
                 gru_history: bool = False, use_mlp_encoder: bool = False,
                 auxiliary_utilization: bool = False,
                 noisy_sigma0: float = 0.1) -> None:
        super().__init__()
        if actions <= 0:
            raise ValueError("actions must be positive")
        self.actions = int(actions)
        self.use_custom_collate = bool(use_custom_collate)
        self.dueling = bool(dueling)
        self.noisy_net = bool(noisy_net)
        self.gru_history = bool(gru_history)
        self.use_mlp_encoder = bool(use_mlp_encoder)
        self.auxiliary_utilization = bool(auxiliary_utilization)
        self.last_collate_ms = 0.0
        # Edge indices are immutable for a topology and repeated thousands of
        # times in replay batches. Retain the NumPy owner alongside the tensor
        # so cache keys cannot be recycled while replay still holds states.
        self._edge_index_cache: dict[tuple[str, int], tuple[object, torch.Tensor]] = {}
        self.hidden = 64
        self.conv1 = GATv2Conv(node_features, 16, heads=4,
                              edge_dim=edge_features, add_self_loops=True)
        self.residual1 = nn.Linear(node_features, self.hidden)
        self.norm1 = nn.LayerNorm(self.hidden)
        self.conv2 = GATv2Conv(self.hidden, 16, heads=4,
                              edge_dim=edge_features, add_self_loops=True)
        self.norm2 = nn.LayerNorm(self.hidden)
        self.use_third_layer = bool(use_third_layer)
        if self.use_third_layer:
            self.conv3 = GATv2Conv(self.hidden, 16, heads=4,
                                  edge_dim=edge_features, add_self_loops=True)
            self.norm3 = nn.LayerNorm(self.hidden)

        if self.use_mlp_encoder:
            self.node_mlp = nn.Sequential(
                nn.Linear(node_features, self.hidden), nn.ELU(),
                nn.Linear(self.hidden, self.hidden), nn.ELU(),
            )
        if self.gru_history:
            self.history_gru = nn.GRU(self.hidden, self.hidden, batch_first=True)

        self.path_attention = nn.Sequential(
            nn.Linear(self.hidden + flow_features, 32),
            nn.ELU(),
            nn.Linear(32, 1),
        )
        scorer_width = self.hidden * 3 + candidate_features + flow_features
        linear = (lambda in_width, out_width: FactorizedNoisyLinear(
            in_width, out_width, noisy_sigma0)) if self.noisy_net else nn.Linear
        self.scorer = nn.Sequential(
            linear(scorer_width, 128), nn.ELU(),
            linear(128, 128), nn.ELU(),
            linear(128, 1),
        )
        if self.dueling:
            self.value_head = nn.Sequential(
                nn.Linear(self.hidden * 2 + flow_features, 128), nn.ELU(),
                nn.Linear(128, 1),
            )
        if self.auxiliary_utilization:
            self.auxiliary_head = nn.Sequential(
                nn.Linear(self.hidden * 2 + edge_features, 64), nn.ELU(),
                nn.Linear(64, 1),
            )

    def _encode_nodes(self, states: Sequence[ModelState | TensorModelState]
                      ) -> tuple[torch.Tensor, torch.Tensor]:
        collate_started = time.perf_counter()
        if self.use_custom_collate:
            batch = custom_collate(states)
            x, edge_index, edge_attr, ptr = (
                batch.x, batch.edge_index, batch.edge_attr, batch.ptr)
        else:
            graph_data = []
            for state in states:
                cache_key = (state.graph_id, id(state.edge_index))
                cached = self._edge_index_cache.get(cache_key)
                if cached is None:
                    if isinstance(state.edge_index, torch.Tensor):
                        edge_index = state.edge_index
                        owner = edge_index
                    else:
                        edge_index = torch.tensor(state.edge_index, dtype=torch.long)
                        owner = state.edge_index
                    self._edge_index_cache[cache_key] = (owner, edge_index)
                else:
                    edge_index = cached[1]
                if isinstance(state, TensorModelState):
                    x_state, edge_state = state.node_features, state.edge_attr
                else:
                    x_state = torch.as_tensor(state.node_features, dtype=torch.float32)
                    edge_state = torch.as_tensor(state.edge_attr, dtype=torch.float32)
                graph_data.append(Data(x=x_state, edge_index=edge_index,
                                       edge_attr=edge_state))
            batch = Batch.from_data_list(graph_data)
            x, edge_index, edge_attr, ptr = (
                batch.x, batch.edge_index, batch.edge_attr, batch.ptr)
        self.last_collate_ms = (time.perf_counter() - collate_started) * 1000.0
        if self.use_mlp_encoder:
            return self.node_mlp(x), ptr
        h0 = x
        h1 = F.elu(self.norm1(self.conv1(h0, edge_index, edge_attr)
                              + self.residual1(h0)))
        h2 = F.elu(self.norm2(self.conv2(h1, edge_index, edge_attr)
                              + h1))
        if self.use_third_layer:
            h2 = F.elu(self.norm3(self.conv3(h2, edge_index, edge_attr)
                                  + h2))
        return h2, ptr

    def _encode_state_nodes(self, states: Sequence[ModelState | TensorModelState]
                            ) -> tuple[torch.Tensor, torch.Tensor]:
        if not self.gru_history:
            return self._encode_nodes(states)
        snapshots: list[torch.Tensor] = []
        ptr: torch.Tensor | None = None
        for time_index in range(self._history_length(states)):
            at_time = []
            for state in states:
                history_nodes = state.history_node_features
                history_edges = state.history_edge_attr
                nodes = (state.node_features if history_nodes is None
                         else history_nodes[time_index])
                edges = (state.edge_attr if history_edges is None
                         else history_edges[time_index])
                at_time.append(replace(state, node_features=nodes,
                                       edge_attr=edges))
            encoded, ptr = self._encode_nodes(at_time)
            snapshots.append(encoded)
        assert ptr is not None
        temporal = torch.stack(snapshots, dim=1)
        encoded, _hidden = self.history_gru(temporal)
        return encoded[:, -1, :], ptr

    @staticmethod
    def _history_length(states: Sequence[ModelState | TensorModelState]) -> int:
        lengths = [int(state.history_node_features.shape[0])
                   for state in states if state.history_node_features is not None]
        if not lengths:
            return 1
        if len(set(lengths)) != 1:
            raise ValueError("all states in a GRU batch must have the same history length")
        return lengths[0]

    def reset_noise(self) -> None:
        for module in self.modules():
            if isinstance(module, FactorizedNoisyLinear):
                module.reset_noise()

    def forward(self, states: ModelState | TensorModelState |
                Sequence[ModelState | TensorModelState]
                ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return masked Q values (B,K) and path-position attention (B,K,Nmax).

        Invalid candidate Q values are -inf by design. Every unmasked Q and all
        differentiable finite-action computations remain finite.
        """
        if isinstance(states, (ModelState, TensorModelState)):
            states = [states]
        states = list(states)
        if not states:
            raise ValueError("at least one model state is required")
        if any(state.candidate_features.shape[0] != self.actions for state in states):
            raise ValueError("state action count does not match model")
        node_embedding, ptr = self._encode_state_nodes(states)
        q_rows = []
        attention_rows = []
        for graph_i, state in enumerate(states):
            begin, end = int(ptr[graph_i]), int(ptr[graph_i + 1])
            embeddings = node_embedding[begin:end]
            if isinstance(state, TensorModelState):
                flow = state.flow_features
                path_array = state.candidate_paths
                candidate_features = state.candidate_features
                mask = state.action_mask
            else:
                flow = torch.as_tensor(state.flow_features, dtype=torch.float32)
                path_array = torch.as_tensor(state.candidate_paths, dtype=torch.long)
                candidate_features = torch.as_tensor(state.candidate_features, dtype=torch.float32)
                mask = torch.as_tensor(state.action_mask, dtype=torch.bool)
            advantages = []
            candidate_attention = []
            for action in range(self.actions):
                ids = path_array[action]
                ids = ids[ids >= 0]
                if ids.numel() == 0:
                    advantages.append(embeddings.new_zeros(()))
                    candidate_attention.append(embeddings.new_zeros(state.num_nodes))
                    continue
                path_nodes = embeddings[ids]
                flow_expanded = flow.unsqueeze(0).expand(path_nodes.shape[0], -1)
                logits = self.path_attention(torch.cat((path_nodes, flow_expanded), dim=-1)).squeeze(-1)
                weights = torch.softmax(logits, dim=0)
                pooled = torch.sum(path_nodes * weights.unsqueeze(-1), dim=0)
                src, dst = path_nodes[0], path_nodes[-1]
                scorer_input = torch.cat((pooled, src, dst,
                                          candidate_features[action], flow), dim=-1)
                advantages.append(self.scorer(scorer_input).squeeze(-1))
                padded_weights = F.pad(weights, (0, state.num_nodes - weights.numel()))
                candidate_attention.append(padded_weights)
            advantage = torch.stack(advantages)
            if self.dueling:
                pooled_graph = torch.cat((embeddings.mean(dim=0),
                                          embeddings.max(dim=0).values, flow), dim=-1)
                value = self.value_head(pooled_graph).squeeze(-1)
                valid = mask.to(dtype=torch.bool)
                valid_count = valid.sum().clamp_min(1)
                valid_mean = advantage.masked_fill(~valid, 0.0).sum() / valid_count
                q = value + advantage - valid_mean
            else:
                q = advantage
            q = q.masked_fill(~mask, -torch.inf)
            q_rows.append(q)
            attention_rows.append(torch.stack(candidate_attention))

        max_nodes = max(state.num_nodes for state in states)
        padded_rows = [F.pad(row, (0, max_nodes - row.shape[1]))
                       for row in attention_rows]
        return torch.stack(q_rows), torch.stack(padded_rows)

    def auxiliary_predictions(
        self, states: ModelState | TensorModelState |
                Sequence[ModelState | TensorModelState]
    ) -> list[tuple[torch.Tensor, torch.Tensor]]:
        """Return (predicted next utilization, router-router mask) per graph.

        Call this with current observations. Predictions align with the exact
        directed edge rows in each state's edge_index/edge_attr arrays; training
        aligns them with utilization targets from the corresponding next state.
        """
        if not self.auxiliary_utilization:
            raise RuntimeError("auxiliary utilization head is disabled")
        if isinstance(states, (ModelState, TensorModelState)):
            states = [states]
        embeddings_batch, ptr = self._encode_state_nodes(states)
        outputs: list[tuple[torch.Tensor, torch.Tensor]] = []
        for graph_i, state in enumerate(states):
            begin, end = int(ptr[graph_i]), int(ptr[graph_i + 1])
            embeddings = embeddings_batch[begin:end]
            edge_index = (state.edge_index if isinstance(state.edge_index, torch.Tensor)
                          else torch.tensor(np.asarray(state.edge_index).copy(),
                                            dtype=torch.long))
            edge_attr = (state.edge_attr if isinstance(state.edge_attr, torch.Tensor)
                         else torch.tensor(np.asarray(state.edge_attr).copy(),
                                           dtype=torch.float32))
            left, right = edge_index[0], edge_index[1]
            edge_input = torch.cat((embeddings[left], embeddings[right], edge_attr), dim=-1)
            predicted = 2.0 * torch.sigmoid(self.auxiliary_head(edge_input).squeeze(-1))
            nodes = state.node_features
            if not isinstance(nodes, torch.Tensor):
                nodes = torch.tensor(np.asarray(nodes).copy(), dtype=torch.float32)
            # Day 4 wrapper's node column 2 marks host/access nodes.
            router_mask = (nodes[left, 2] < 0.5) & (nodes[right, 2] < 0.5)
            outputs.append((predicted, router_mask))
        return outputs
