#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""Module for translating labels to flavours."""

import itertools

from pydantic import BaseModel, conlist

WORKFLOW_JOB = "workflow_job"
LABEL_SEPARATOR = "#"
Flavor = str
Label = str


class FlavorLabelsMapping(BaseModel):
    """A class to represent the mapping of flavors to labels.

    Attributes:
        mapping: The mapping of flavors to labels.
    """

    # mypy does not recognize the min_length parameter
    mapping: conlist(item_type=tuple[Flavor, list[Label]], min_length=1)  # type: ignore


class LabelsFlavorMapping(BaseModel):
    """A class to represent the mapping of labels to flavors.

    Attributes:
        mapping: The mapping of labels to flavors.
        ignore_labels: The labels to ignore (e.g. "self-hosted" or "linux").
        default_flavor: The default flavor.
    """

    mapping: dict[str, str]
    ignore_labels: set[str]
    default_flavor: Flavor


class InvalidLabelCombinationError(Exception):
    """The label combination is invalid."""


def to_labels_flavor_mapping(
    flavor_label_mapping: FlavorLabelsMapping, ignore_labels: set[Label]
) -> LabelsFlavorMapping:
    """Convert the flavor label mapping to a label flavor mapping.

    Args:
        flavor_label_mapping: The flavor label mapping.
        ignore_labels: The labels to ignore (e.g. "self-hosted" or "linux").

    Returns:
        The label flavor mapping.
    """
    flavor_mapping = flavor_label_mapping.mapping
    label_mapping = {}
    default_flavor = flavor_mapping[0][0]

    for flavor, labels in flavor_mapping:
        sorted_labels = sorted(labels.lower() for labels in labels)
        powerset = [
            x
            for length in range(1, len(sorted_labels) + 1)
            for x in itertools.combinations(sorted_labels, length)
        ]
        for label_combination in powerset:
            label_key = LABEL_SEPARATOR.join(label_combination)
            if label_key not in label_mapping:
                label_mapping[label_key] = flavor
    return LabelsFlavorMapping(
        default_flavor=default_flavor,
        mapping=label_mapping,
        ignore_labels={label.lower() for label in ignore_labels},
    )


def labels_to_flavor(labels: set[str], label_flavor_mapping: LabelsFlavorMapping) -> Flavor:
    """Map the labels to a flavor.

    Args:
        labels: The labels to map.
        label_flavor_mapping: The available flavors.

    Raises:
        InvalidLabelCombinationError: If the label combination is invalid.

    Returns:
        The flavor.
    """
    if not labels:
        return label_flavor_mapping.default_flavor
    labels_lowered = {label.lower() for label in labels}
    final_labels = labels_lowered - label_flavor_mapping.ignore_labels
    label_key = LABEL_SEPARATOR.join(sorted(final_labels))
    if label_key not in label_flavor_mapping.mapping:
        raise InvalidLabelCombinationError(f"Invalid label combination: {labels}")
    return label_flavor_mapping.mapping[label_key]
