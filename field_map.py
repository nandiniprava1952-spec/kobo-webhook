"""
Field mapping between the autoclave checklist form's submitted fields and
the facility-master dataset's columns (the ones your pulldata() calls read
from, e.g. autoclave_count, radiant_warmer_count, ot_table_count...).

Only the fields relevant to the department actually assessed on a given
visit (${departments_visited}) get written -- so a visit that only covered
"sterilization" equipment never overwrites SNCU or OT numbers with blanks.
"""

from typing import Any

MASTER_KEY_FIELD = "facility_code"  # column in the master dataset used as the join key

# Fields captured regardless of department (the shared "sterilization" group)
COMMON_FIELDS = [
    "autoclave_count",
    "autoclave_functional_count",
    "autoclave_drums_count",
    "autoclave_drums_functional_count",
    "delivery_sets_count",
]

# Fields captured only when departments_visited == 'sterilization'
STERILIZATION_FIELDS = [
    "fetal_doppler_count",
    "fetal_doppler_functional_count",
    "resuscitation_table_count",
    "resuscitation_table_functional_count",
    "suction_machine_lr_count",
    "suction_machine_lr_functional_count",
    "weighing_scale_newborn_count",
    "weighing_scale_newborn_functional_count",
    "o2_cylinder_concentrator_count",
    "o2_cylinder_concentrator_functional_count",
]

# Fields captured only when departments_visited == 'sncu'
SNCU_FIELDS = [
    "radiant_warmer_count",
    "radiant_warmer_functional_count",
    "phototherapy_unit_count",
    "phototherapy_unit_functional_count",
    "infusion_pump_count",
    "infusion_pump_functional_count",
    "oxygen_concentrator_count",
    "oxygen_concentrator_functional_count",
    "weighing_scale_newborn_sncu_count",
    "weighing_scale_newborn_sncu_functional_count",
]

# Fields captured only when departments_visited == 'ot'
OT_FIELDS = [
    "ot_table_count",
    "ot_table_functional_count",
    "anesthesia_machine_count",
    "anesthesia_machine_functional_count",
    "ot_light_count",
    "ot_light_functional_count",
    "suction_machine_count",
    "suction_machine_functional_count",
    "weighing_scale_newborn_ot_count",
    "weighing_scale_newborn_ot_functional_count",
]

DEPARTMENT_FIELD_MAP = {
    "sterilization": STERILIZATION_FIELDS,
    "sncu": SNCU_FIELDS,
    "ot": OT_FIELDS,
}


def build_master_update(submission: dict[str, Any]) -> dict[str, Any]:
    """
    Given a raw Kobo submission (flat dict of field name -> value, using
    Kobo's group-prefixed keys e.g. 'grp_facility_equipment/autoclave_count'
    OR flat keys depending on your export settings), return just the
    fields that should be written into the facility-master dataset.

    Kobo submissions nest group fields with a '/' path by default
    (e.g. "grp_facility_equipment/autoclave_count"). This function checks
    both the flat name and any key ending in "/<field>" so it works
    whichever export format your REST Service payload uses.
    """
    department = submission.get("departments_visited") or _find(submission, "departments_visited")

    wanted_fields = list(COMMON_FIELDS)
    if department in DEPARTMENT_FIELD_MAP:
        wanted_fields += DEPARTMENT_FIELD_MAP[department]
    else:
        # No recognized department -- still sync the common/shared fields
        pass

    result = {}
    for field in wanted_fields:
        value = _find(submission, field)
        if value not in (None, ""):
            result[field] = value

    return result


def find_field(submission: dict[str, Any], field_name: str):
    """Look up a field by exact key, or by any key ending in '/<field_name>'
    (Kobo nests group fields with a '/' path, e.g. 'grp_x/facility_name_select')."""
    if field_name in submission:
        return submission[field_name]
    suffix = f"/{field_name}"
    for key, value in submission.items():
        if key.endswith(suffix):
            return value
    return None


# Kept as a private alias so the rest of this module's existing calls still work
_find = find_field
