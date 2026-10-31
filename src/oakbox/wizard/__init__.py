"""F3d, the Fields wizard (SPEC §3.0): one small question at a time, over all of a project's files.

It writes only what OpenAVMKit reads: each file's ``load`` (as F3c) and ``calc``, and what each
file holds, from which the merge lists are written (``projects._data``). Its own state is the
base file, the steps seen and skipped, and the fields already decided (``WizardState``).

Guesses are modest (SPEC D45): a column is preselected only when its name matches the field (its
key, its name, or a short alias list) and its values pass the field's check. A guess is made
once per field, when its step is first shown, and never replaces a choice.
"""

from __future__ import annotations

from oakbox.wizard.base import RENAMED, YES
from oakbox.wizard.condos import set_condos, set_unit_field, set_units, unit_ids, units_view
from oakbox.wizard.core import (
    confirm,
    repeat_rows,
    set_field,
    set_file,
    set_sale_id,
    skip,
    update_base,
    view,
    visit,
)
from oakbox.wizard.deeds_permits import deed_names, set_permits
from oakbox.wizard.files import Files, base_file, file_stamp, sales_file, values_of
from oakbox.wizard.ids import Reconcile, SampleView, reconcile, set_reconcile
from oakbox.wizard.maps import LayerMap, MapView, coverage, enrich_view, layer_map, layers, map_view, set_overlay
from oakbox.wizard.models import LocationField, RepeatRows, Wizard
from oakbox.wizard.money import NumberPreview, number_preview
from oakbox.wizard.quality import (
    Candidate,
    ScalePreview,
    TiersPreview,
    candidates,
    scale_preview,
    short_number,
    tier_order,
    tiers_preview,
)
from oakbox.wizard.rules import (
    ColumnValues,
    DatePreview,
    RulePreview,
    ValueSort,
    column_values,
    date_preview,
    rule_complete,
    rule_preview,
    rule_result,
    set_rule,
    sort_counts,
)
from oakbox.wizard.user_fields import locations, set_custom, set_location
from oakbox.wizard.values import add_value_set, change_value_set, remove_value_set

__all__ = [
    "base_file",
    "Candidate",
    "candidates",
    "column_values",
    "ColumnValues",
    "confirm",
    "coverage",
    "date_preview",
    "DatePreview",
    "deed_names",
    "enrich_view",
    "file_stamp",
    "Files",
    "layer_map",
    "LayerMap",
    "layers",
    "LocationField",
    "locations",
    "map_view",
    "MapView",
    "number_preview",
    "NumberPreview",
    "Reconcile",
    "reconcile",
    "RENAMED",
    "repeat_rows",
    "RepeatRows",
    "rule_complete",
    "rule_preview",
    "rule_result",
    "RulePreview",
    "sales_file",
    "SampleView",
    "scale_preview",
    "ScalePreview",
    "set_condos",
    "set_custom",
    "set_field",
    "set_file",
    "set_location",
    "set_overlay",
    "set_permits",
    "set_reconcile",
    "set_rule",
    "set_sale_id",
    "set_unit_field",
    "add_value_set",
    "change_value_set",
    "remove_value_set",
    "set_units",
    "short_number",
    "skip",
    "sort_counts",
    "tier_order",
    "tiers_preview",
    "TiersPreview",
    "unit_ids",
    "units_view",
    "update_base",
    "values_of",
    "ValueSort",
    "view",
    "visit",
    "Wizard",
    "YES",
]
