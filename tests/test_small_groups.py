"""Model values › Small groups (SPEC F9, slice 2): which groups the try can't be trusted on."""

from oakbox import model, smallgroups


def _group(sales: int = 100, valued: int = 500, below: int = 0, median: float | None = 1.0):
    rows = [model.ModelRow(model="ensemble", name="Ensemble", values={"median_ratio": median, "cod": 12.0})]
    sets = [model.SalesSet(key="holdout", sales=sales, first=None, last=None, rows=rows, trimmed=[])] if median else []
    return model.ModelGroupResult(
        id="g", name="G", color="#000", parcels=500, sales=sales, sets=sets, valued=valued, below_zero=below
    )


def test_a_sound_group_isnt_flagged():
    assert smallgroups.flags(_group()) == []


def test_what_flags_a_group():
    assert smallgroups.flags(_group(sales=14)) == ["too_few"]
    assert smallgroups.flags(_group(valued=0, median=None)) == ["no_values"]
    # Values, but no sale held out to judge them by.
    assert smallgroups.flags(_group(sales=16, median=None)) == ["no_holdout"]
    assert smallgroups.flags(_group(median=0.31)) == ["implausible"]
    assert smallgroups.flags(_group(median=2.4, below=3)) == ["implausible", "below_zero"]
