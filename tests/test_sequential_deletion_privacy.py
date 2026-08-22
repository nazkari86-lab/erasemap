import json
from pathlib import Path

import numpy as np
import pytest

from experiments.sequential_deletion_privacy import (
    ATTACKS,
    _validate_protocol,
    release_difference_attacks,
    train_adapter,
)


def test_sequential_protocol_is_frozen_before_results() -> None:
    protocol = json.loads(Path("benchmark/sequential-deletion-privacy-v1.json").read_text())
    _validate_protocol(protocol)
    assert protocol["sequence_length"] == 5
    assert len(protocol["random_seeds"]) == 5
    assert protocol["candidate"]["epochs"] == 60
    assert protocol["exact_retraining"]["epochs"] == 100
    assert tuple(protocol["privacy_attacks"]) == ATTACKS


def test_protocol_rejects_non_bounded_candidate() -> None:
    protocol = json.loads(Path("benchmark/sequential-deletion-privacy-v1.json").read_text())
    protocol["candidate"]["epochs"] = 100
    with pytest.raises(ValueError, match="smaller frozen epoch budget"):
        _validate_protocol(protocol)


def test_release_difference_attack_returns_all_registered_signals() -> None:
    rng = np.random.default_rng(7)
    features = rng.normal(size=(24, 8)).astype(np.float32)
    targets = np.repeat(np.arange(4), 6)
    previous_classes = np.arange(4)
    current_classes = np.arange(3)
    previous, _ = train_adapter(
        features,
        targets,
        hidden_dimension=6,
        epochs=2,
        learning_rate=0.01,
        weight_decay=0.0,
        seed=11,
    )
    retained = targets != 3
    current, _ = train_adapter(
        features[retained],
        targets[retained],
        hidden_dimension=6,
        epochs=2,
        learning_rate=0.01,
        weight_decay=0.0,
        seed=12,
    )
    result = release_difference_attacks(
        previous,
        previous_classes,
        current,
        current_classes,
        features,
        np.asarray([0, 1, 6, 7, 12, 13]),
        np.asarray([2, 3, 8, 9, 14, 15]),
        target_fpr=0.1,
    )
    assert set(result) == set(ATTACKS)
    assert all(0 <= value <= 1 for value in result.values())
