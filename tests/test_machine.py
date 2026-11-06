"""This computer (machine.py, SPEC §5): the tier the check puts it in, the settings each tier recommends, the
user's own choices over them, and the memory warning for a large county."""

from oakbox import appsettings, bring_in, machine


def found(**kw):
    base = {"memory_gb": 7.8, "cores": 6, "threads": 6, "speed": 92, "graphics": "Intel UHD Graphics 630"}
    return machine.finish({**base, **kw})


def test_memory_decides_the_tier():
    assert found().tier == "light"  # an 8 GB OptiPlex
    assert found(memory_gb=15.8).tier == "standard"
    assert found(memory_gb=31.8, cores=8, threads=16).tier == "strong"
    assert found(memory_gb=31.8, cores=4, threads=8).tier == "standard"  # memory, but four cores
    assert found(memory_gb=15.8, cores=2, threads=4).tier == "light"  # two cores
    assert found(memory_gb=15.8, speed=55).tier == "light"  # a slow processor
    assert found(memory_gb=31.8, cores=8, cancelled=True).tier == "light"  # cancelled: the safest


def test_each_tier_recommends():
    light = machine.recommended(found())
    assert (light.fold_workers, light.folds_at_once, light.maps, light.map_detail, light.street_map) == (
        "one",
        1,
        "click",
        "dots",
        "off",
    )
    std = machine.recommended(found(memory_gb=15.8))
    assert (std.fold_workers, std.maps, std.map_detail, std.street_map) == ("two", "now", "auto", "on")
    strong = machine.recommended(found(memory_gb=31.8, cores=8, threads=16))
    assert (strong.fold_workers, strong.folds_at_once, strong.map_detail) == ("cores", 14, "shapes")


def test_graphics_in_software_draw_maps_simply_on_any_tier():
    m = found(memory_gb=31.8, cores=8, threads=16, graphics="Google SwiftShader")
    assert m.graphics_software and m.tier == "strong"
    r = machine.recommended(m)
    assert (r.fold_workers, r.maps, r.map_detail, r.street_map) == ("cores", "click", "dots", "off")
    assert found(graphics=None).graphics_software  # no WebGL at all
    assert not found(graphics="ANGLE (NVIDIA GeForce GTX 1650)").graphics_software


def test_a_choice_stays_and_recommended_follows_the_check():
    p = machine.Performance(maps="now")
    light = machine.resolve(p, found())
    assert light.maps == "now" and light.fold_workers == "one"
    std = machine.resolve(p, found(memory_gb=15.8))
    assert std.maps == "now" and std.fold_workers == "two"
    assert machine.resolve(machine.Performance(fold_workers="cores"), found()).folds_at_once == 4


def test_memory_need_grows_with_the_county_and_the_workers():
    assert machine.memory_need_gb(50_000, 1) == 1.5
    assert machine.memory_need_gb(50_000, 2) == 2.1
    assert machine.memory_need_gb(5_000, 1) < 1
    assert machine.memory_for_oakbox_gb(found()) == 7.8 - machine.OTHERS_GB


def test_the_check_and_settings_through_the_api(client):
    v = client.get("/api/machine").json()
    assert v["machine"] is None and v["resolved"]["fold_workers"] == "two"  # not checked yet: Standard's
    b = client.post("/api/machine/basics").json()
    assert b["memory_gb"] > 0 and b["threads"] >= 1
    d = client.post("/api/machine/disk").json()
    assert d["disk_mb_s"] is None or d["disk_mb_s"] > 0
    v = client.put("/api/machine", json={"memory_gb": 7.8, "cores": 4, "threads": 4, "graphics": "Mesa Intel"}).json()
    assert v["machine"]["tier"] == "light" and v["resolved"]["maps"] == "click"
    assert v["memory_for_oakbox_gb"] == 2.3
    v = client.put("/api/performance", json={"maps": "now"}).json()
    assert v["resolved"]["maps"] == "now" and v["recommended"]["maps"] == "click"
    assert appsettings.load().performance.maps == "now"
    assert machine.folds_at_once() == 1


def test_a_county_too_big_for_this_computer_is_said_before_it_runs(client):
    assert bring_in.memory_note(200_000) is None  # not checked: nothing to say
    client.put("/api/machine", json={"memory_gb": 7.8, "cores": 4, "threads": 4, "graphics": "Mesa Intel"})
    assert bring_in.memory_note(50_000) is None  # 1.5 GB of 2.3
    note = bring_in.memory_note(200_000)
    assert note is not None and note.parcels == 200_000 and note.need_gb == 4.5 and note.have_gb == 2.3
