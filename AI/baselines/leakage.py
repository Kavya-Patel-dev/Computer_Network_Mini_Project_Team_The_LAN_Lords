"""Split-safety assertions shared by tuning and fitting code."""
from __future__ import annotations


def validate_graph_partitions(train_names, val_names, test_names) -> None:
    train, val, test = set(train_names), set(val_names), set(test_names)
    if train & val or train & test or val & test:
        raise AssertionError("train, validation, and test graph partitions must be disjoint")


def guard_fit_and_tuning(fit_names, tuning_names, train_names, val_names,
                         test_names) -> None:
    validate_graph_partitions(train_names, val_names, test_names)
    fit, tuning, test = set(fit_names), set(tuning_names), set(test_names)
    if not fit <= set(train_names):
        raise AssertionError("model fit data may contain train graphs only")
    if not tuning <= set(val_names):
        raise AssertionError("hyperparameter selection may contain validation graphs only")
    if fit & test or tuning & test:
        raise AssertionError("test graphs cannot be used for model fit or tuning")
