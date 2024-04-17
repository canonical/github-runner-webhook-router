#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Unit tests for the label_translation module."""

import itertools

import pytest

from webhook_router.webhook.label_translation import (
    LABEL_SEPARATOR,
    FlavorLabelsMapping,
    InvalidLabelCombinationError,
    LabelsFlavorMapping,
    labels_to_flavor,
    to_labels_flavor_mapping,
)


def test_to_label_flavor_mapping():
    """
    arrange: A mapping of flavors to labels.
    act: Call to_label_flavor_mapping with the mapping.
    assert: A LabelsFlavorMapping object is returned.
    """
    flavor_mapping = FlavorLabelsMapping(
        mapping=[("large", ["arm64", "large"]), ("x64-large", ["large", "x64", "jammy"])]
    )
    ignore_labels = {"self-hosted", "linux"}
    labels_mapping = to_labels_flavor_mapping(flavor_mapping, ignore_labels)
    assert labels_mapping == LabelsFlavorMapping(
        mapping={
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
            "x64": "x64-large",
            "jammy": "x64-large",
            f"jammy{LABEL_SEPARATOR}x64": "x64-large",
            f"jammy{LABEL_SEPARATOR}large": "x64-large",
            f"large{LABEL_SEPARATOR}x64": "x64-large",
            f"jammy{LABEL_SEPARATOR}large{LABEL_SEPARATOR}x64": "x64-large",
        },
        default_flavor="large",
        ignore_labels=ignore_labels,
    )


def test_to_label_flavor_mapping_case_insensitive():
    """
    arrange: A mapping of flavors to labels with labels in mixed case.
    act: Call to_label_flavor_mapping with the mapping.
    assert: A LabelsFlavorMapping object is returned which has all labels in lower case.
    """
    flavor_mapping = FlavorLabelsMapping(mapping=[("large", ["arM64", "LaRgE"])])
    ignore_labels = {"self-HOSTED", "LINux"}
    labels_mapping = to_labels_flavor_mapping(flavor_mapping, ignore_labels)
    assert labels_mapping == LabelsFlavorMapping(
        mapping={
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )


def test_labels_to_flavor():
    """
    arrange: Two flavors and a labels to flavor mapping
    act: Call labels_to_flavor with all combintation of labels.
    assert: The correct flavor is returned.
    """
    arm_flavor_labels = ["arm64", "jammy", "large"]
    x64_flavor_labels = ["large", "noble", "x64"]
    arm_label_combination = set(
        x
        for length in range(1, len(arm_flavor_labels) + 1)
        for x in itertools.combinations(arm_flavor_labels, length)
    )
    x64_label_combination = set(
        x
        for length in range(1, len(x64_flavor_labels) + 1)
        for x in itertools.combinations(x64_flavor_labels, length)
    )
    x64_label_combination.remove(("large",))
    mapping = LabelsFlavorMapping(
        mapping={
            **{
                LABEL_SEPARATOR.join(label_combination): "large"
                for label_combination in arm_label_combination
            },
            **{
                LABEL_SEPARATOR.join(label_combination): "x64-large"
                for label_combination in x64_label_combination
            },
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )

    for label_combination in arm_label_combination:
        assert (
            labels_to_flavor(set(label_combination), mapping) == "large"
        ), f"Expected large flavor for {label_combination}"

    for label_combination in x64_label_combination:
        assert (
            labels_to_flavor(set(label_combination), mapping) == "x64-large"
        ), f"Expected x64-large flavor for {label_combination}"


def test_labels_to_flavor_case_insensitive():
    """
    arrange: Two flavors and a labels to flavor mapping
    act: Call labels_to_flavor with all combination of labels in mixed case.
    assert: The correct flavor is returned.
    """
    mapping = LabelsFlavorMapping(
        mapping={
            "small": "small",
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )

    assert labels_to_flavor({"SMALl"}, mapping) == "small"
    assert labels_to_flavor({"ARM64"}, mapping) == "large"
    assert labels_to_flavor({"lARGE"}, mapping) == "large"
    assert labels_to_flavor({"arM64", "lArge"}, mapping) == "large"
    assert labels_to_flavor({"small", "SELF-hosted"}, mapping) == "small"


def test_labels_to_flavor_default_label():
    """
    arrange: Two flavors and a labels to flavor mapping
    act: Call labels_to_flavor with empty labels.
    assert: The default flavor is returned.
    """
    mapping = LabelsFlavorMapping(
        mapping={
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
            "x64": "large-x64",
            f"large{LABEL_SEPARATOR}x64": "x64-large",
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )
    assert labels_to_flavor(set(), mapping) == "large"


def test_labels_to_flavor_invalid_combination():
    """
    arrange: Two flavors and a labels to flavor mapping
    act: Call labels_to_flavor with an invalid combination.
    assert: An InvalidLabelCombinationError is raised.
    """
    mapping = LabelsFlavorMapping(
        mapping={
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
            "x64": "large-x64",
            f"large{LABEL_SEPARATOR}x64": "x64-large",
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )
    labels = {"self-hosted", "linux", "arm64", "large", "x64"}
    with pytest.raises(InvalidLabelCombinationError) as exc_info:
        labels_to_flavor(labels, mapping)
    assert "Invalid label combination:" in str(exc_info.value)


def test_labels_to_flavor_unrecognised_label():
    """
    arrange: Two flavors and a labels to flavor mapping
    act: Call labels_to_flavor with an unrecognised label.
    assert: An InvalidLabelCombinationError is raised.
    """
    mapping = LabelsFlavorMapping(
        mapping={
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
            "x64": "large-x64",
            f"large{LABEL_SEPARATOR}x64": "x64-large",
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )
    labels = {"self-hosted", "linux", "arm64", "large", "noble"}
    with pytest.raises(InvalidLabelCombinationError) as exc_info:
        labels_to_flavor(labels, mapping)
    assert "Invalid label combination:" in str(exc_info.value)


def test_labels_to_flavor_ignore_labels():
    """
    arrange: Two flavors and a labels to flavor mapping
    act: Call labels_to_flavor with an ignored label.
    assert: The correct flavor is returned.
    """
    mapping = LabelsFlavorMapping(
        mapping={
            "arm64": "large",
            "large": "large",
            f"arm64{LABEL_SEPARATOR}large": "large",
            "x64": "large-x64",
            f"large{LABEL_SEPARATOR}x64": "x64-large",
        },
        default_flavor="large",
        ignore_labels={"self-hosted", "linux"},
    )
    labels = {"self-hosted", "linux", "arm64", "large"}
    assert labels_to_flavor(labels, mapping) == "large"
