# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""The iscwsa:spe90408 library and the six SPE 90408 Appendix D example models."""
import json
import math
from pathlib import Path

import pytest

from tools import make_spe90408
from tools.formula import parse
from tools.validate import validate_repo

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "tools" / "spe90408.json").read_text(encoding="utf-8"))
LIBRARY = json.loads((ROOT / "library" / "iscwsa" / "spe90408.json").read_text(encoding="utf-8"))
REV5 = json.loads((ROOT / "library" / "iscwsa" / "rev5.json").read_text(encoding="utf-8"))
MODELS = {
    n: json.loads((ROOT / "conformance" / "models" / "iscwsa" / f"SPE90408_Ex{n}.json").read_text(encoding="utf-8"))
    for n in range(1, 7)
}

# Fixed sample points: Inc 5-85 deg, AzT 0-330 deg, Lat 60 deg; the inputs the values below were computed with.
INC = [5, 9, 14, 18, 23, 27, 32, 36, 41, 45, 50, 54, 59, 63, 68, 72, 77, 81, 84, 85]
AZ = [(k * 33) % 360 for k in range(20)]
LAT = 60.0
EARTH_RATE = 7.2921159e-5  # rad/s
GRAVITY = 9.80665  # m/s2
NOISE_FACTOR = 0.5
CANT = 17.0  # deg; k = 1 (Inc below 90 deg), so IncCant = Inc - CANT
MD, MD_PREV, SPEED = 1500.0, 1470.0, 2160.0  # m, m, m/hr
INC_PREV_OFFSET = 2.0  # deg
DRIFT_PREV, WALK_PREV = 0.7, 0.4  # the previous station's accumulators

# Paper rows written in the paper's own notation (above each entry), values computed from that notation alone.
# name: (the one non-zero field, 20 values at the sample points); the other two fields are 0.
EXPECTED = {
    # cos I / G
    "AXYZ-XYB": ("inclination", [
        0.101583588493, 0.100716181427, 0.0989426283467, 0.0969807749124,
        0.093865372319, 0.0908573798584, 0.0864768393036, 0.0824967745739,
        0.0769589595043, 0.0721048249083, 0.0655460947099, 0.0599374151512,
        0.0525192675287, 0.0462941473122, 0.0381992416795, 0.031510963925,
        0.0229386237241, 0.015951876027, 0.0106589368712, 0.00888741239339,
    ]),
    # 1 / (G cos(I - k a)), k = 1
    "AXY-B": ("inclination", [
        0.104249727977, 0.102973754801, 0.102111561644, 0.101987154435,
        0.102533309495, 0.103544697923, 0.105568790607, 0.107847295579,
        0.111621836051, 0.115490004302, 0.121587218146, 0.127682303147,
        0.137216351109, 0.146793914295, 0.162034510161, 0.177782096396,
        0.203943242596, 0.232614810634, 0.26097644611, 0.272209894567,
    ]),
    # tan(I - k a)
    "AXY-SF": ("inclination", [
        -0.21255656167, -0.140540834702, -0.052407779283, 0.0174550649282,
        0.105104235266, 0.176326980708, 0.267949192431, 0.34432761329,
        0.445228685309, 0.531709431661, 0.649407593198, 0.753554050103,
        0.900404044298, 1.03553031379, 1.23489715654, 1.42814800674,
        1.73205080757, 2.05030384158, 2.35585236582, 2.47508685342,
    ]),
    # 1
    "AXY-MIS": ("inclination", [
        1, 1, 1, 1,
        1, 1, 1, 1,
        1, 1, 1, 1,
        1, 1, 1, 1,
        1, 1, 1, 1,
    ]),
    # tan(I - k a) / G
    "AXY-GB": ("inclination", [
        -0.021674737211, -0.0143311767731, -0.00534410622211, 0.00177992127059,
        0.0107176492753, 0.0179803481014, 0.0273232135776, 0.0351116449847,
        0.0454006908892, 0.0542192728058, 0.0662211451614, 0.0768411282245,
        0.0918156602201, 0.105594705, 0.125924465188, 0.145630567701,
        0.176620029018, 0.209072806879, 0.240230085281, 0.252388619296,
    ]),
    # sin A cos I / (Om cos lat)
    "GXYZ-B1": ("azimuth", [
        0, 14753.8418778, 24311.4417123, 25763.3708864,
        18761.8635812, 6324.898313, -7187.52354881, -17243.9467104,
        -20585.9372634, -17279.9435438, -8814.82985873, 843.714051342,
        8302.98884309, 11624.5174977, 10049.772812, 5992.99339783,
        1282.75399627, -1537.58111482, -2319.3625647, -2387.13427008,
    ]),
    # cos A / (Om cos lat)
    "GXYZ-B2": ("azimuth", [
        27426.8816819, 23002.1184371, 11155.5177853, -4290.50956363,
        -18352.1659703, -26492.3333511, -26084.5145452, -17260.2959053,
        -2866.88979443, 12451.5437211, 23752.3762831, 27389.2940938,
        22188.8133834, 9828.91535076, -5702.36934434, -19393.7340241,
        -26827.5385128, -25605.1998981, -16121.116569, -1435.41207958,
    ]),
    # f sqrt(1 - sin^2 A sin^2 I) / (Om cos lat)
    "GXYZ-RN": ("azimuth", [
        13713.4408409, 13663.5766067, 13374.3390041, 13059.0940703,
        13122.5904535, 13618.4439737, 13528.3257817, 12199.0933361,
        10392.3032831, 10649.3824928, 12667.6418932, 13701.1430577,
        11845.7066388, 7611.45492048, 5777.43346375, 10149.2966414,
        13429.0941659, 12825.6619469, 8143.55331132, 1392.73273294,
    ]),
    # cos A sin I / (Om cos lat)
    "GXYZ-G1": ("azimuth", [
        2390.41024424, 3598.3240925, 2698.76400902, -1325.84036969,
        -7170.76251981, -12027.2676573, -13822.6867557, -10145.3473834,
        -1880.84893476, 8804.5710014, 18195.3758626, 22158.4043858,
        19019.5252736, 8757.62770323, -5287.14478885, -18444.5371189,
        -26139.9504387, -25289.9573979, -16032.8034056, -1429.94990326,
    ]),
    # cos A cos I / (Om cos lat)
    "GXYZ-G2": ("azimuth", [
        27322.5141167, 22718.9241893, 10824.1512315, -4080.51707872,
        -16893.2578471, -23604.8418568, -22120.9228992, -13963.8727154,
        -2163.6691933, 8804.5710014, 15267.7331754, 16099.023139,
        11428.0837295, 4462.23419199, -2136.14515448, -5992.99339783,
        -6034.8830739, -4005.5357483, -1685.11554112, -125.104405945,
    ]),
    # sin A cos^2 I / (Om cos lat)
    "GXYZ-G3": ("azimuth", [
        0, 14572.1976017, 23589.287993, 24502.4217632,
        17270.3864863, 5635.52566171, -6095.36566165, -13950.6459388,
        -15536.4040706, -12218.7652584, -5666.06341469, 495.922676531,
        4276.35538975, 5277.42050799, 3764.71115771, 1851.93680711,
        288.556863924, -240.530679153, -242.439404648, -208.052460347,
    ]),
    # sin A sin I cos I / (Om cos lat)
    "GXYZ-G4": ("azimuth", [
        0, 2308.00936145, 5881.47006379, 7961.31943628,
        7330.84412964, 2871.44374592, -3808.80719065, -10135.7375677,
        -13505.5900119, -12218.7652584, -6752.55143032, 682.579005929,
        7117.05053439, 10357.520931, 9317.98709335, 5699.67542312,
        1249.87709445, -1518.65093983, -2306.65685389, -2378.05050348,
    ]),
    # sin A sin I / (Om cos lat)
    "GXYZ-ZB": ("azimuth", [
        0, 2336.77898846, 6061.52320836, 8371.02664235,
        7963.93859537, 3222.69665594, -4491.26318178, -12528.4606358,
        -17895.0822486, -17279.9435438, -10505.1051523, 1161.27276631,
        13818.4939737, 22814.4001623, 24874.0605668, 18444.5371189,
        5556.21798748, -9707.90509265, -22067.260742, -27285.0695607,
    ]),
    # sin A sin I / (Om cos lat)
    "GXYZ-ZRN": ("azimuth", [
        0, 2336.77898846, 6061.52320836, 8371.02664235,
        7963.93859537, 3222.69665594, -4491.26318178, -12528.4606358,
        -17895.0822486, -17279.9435438, -10505.1051523, 1161.27276631,
        13818.4939737, 22814.4001623, 24874.0605668, 18444.5371189,
        5556.21798748, -9707.90509265, -22067.260742, -27285.0695607,
    ]),
    # sin A sin^2 I / (Om cos lat)
    "GXYZ-ZG1": ("azimuth", [
        0, 365.552770977, 1466.41518479, 2586.78949285,
        3111.75871459, 1463.07366534, -2380.00688077, -7364.04439563,
        -11740.2302837, -12218.7652584, -8047.37742626, 939.489403053,
        11844.7611792, 20327.7793901, 23062.8273551, 17541.797217,
        5413.81248042, -9588.38467161, -21946.3739787, -27181.2416334,
    ]),
    # sin A cos I sin I / (Om cos lat)
    "GXYZ-ZG2": ("azimuth", [
        0, 2308.00936145, 5881.47006379, 7961.31943628,
        7330.84412964, 2871.44374592, -3808.80719065, -10135.7375677,
        -13505.5900119, -12218.7652584, -6752.55143032, 682.579005929,
        7117.05053439, 10357.520931, 9317.98709335, 5699.67542312,
        1249.87709445, -1518.65093983, -2306.65685389, -2378.05050348,
    ]),
    # tan(lat) sin A sin I cos I
    "GXYZ-SF": ("azimuth", [
        0, 0.145754428985, 0.37142410471, 0.502769870774,
        0.462954361424, 0.181336198431, -0.240532177407, -0.640087803019,
        -0.852899296323, -0.771634284885, -0.426434265976, 0.0431059400832,
        0.44945295891, 0.654093771977, 0.588445571653, 0.359943486612,
        0.0789317085299, -0.0959052004983, -0.145669016, -0.150177637501,
    ]),
    # 1 / cos(lat)
    "GXYZ-MIS": ("azimuth", [
        2, 2, 2, 2,
        2, 2, 2, 2,
        2, 2, 2, 2,
        2, 2, 2, 2,
        2, 2, 2, 2,
    ]),
    # cos A cos I / (Om cos lat)
    "GXY-G2": ("azimuth", [
        27322.5141167, 22718.9241893, 10824.1512315, -4080.51707872,
        -16893.2578471, -23604.8418568, -22120.9228992, -13963.8727154,
        -2163.6691933, 8804.5710014, 15267.7331754, 16099.023139,
        11428.0837295, 4462.23419199, -2136.14515448, -5992.99339783,
        -6034.8830739, -4005.5357483, -1685.11554112, -125.104405945,
    ]),
    # sin A / (Om cos lat)
    "GXY-G3": ("azimuth", [
        0, 14937.7503727, 25055.7031778, 27089.2112561,
        20382.1452009, 7098.59932705, -8475.37254242, -21314.6903344,
        -27276.6343543, -24437.5305167, -13713.4408409, 1435.41207958,
        16121.116569, 25605.1998981, 26827.5385128, 19393.7340241,
        5702.36934434, -9828.91535076, -22188.8133834, -27389.2940938,
    ]),
    # tan(lat) sin A tan I
    "GXY-SF": ("azimuth", [
        0, 0.149410770797, 0.394513481011, 0.555848698312,
        0.54636895494, 0.228414010231, -0.334450781975, -0.977967139876,
        -1.4974006946, -1.54326856977, -1.03208888624, 0.12476700507,
        1.69435953809, 3.17355832422, 4.19329546806, 3.76937712792,
        1.55982342231, -3.91901815068, -13.3320844293, -19.77029963,
    ]),
    # 1 / (cos(lat) cos I)
    "GXY-MIS": ("azimuth", [
        2.00763967509, 2.02493025158, 2.0612272587, 2.10292444848,
        2.17272075481, 2.24465247527, 2.35835680672, 2.472135955,
        2.6500259867, 2.82842712475, 3.11144765372, 3.40260323341,
        3.88320805282, 4.40537852917, 5.33893432511, 6.472135955,
        8.89082296517, 12.784906443, 19.133544467, 22.9474264913,
    ]),
    # h = h_prev + D / c  (h_prev 0.7, D 30 m, c 2160 m/hr)
    "GXYZ-GD": ("azimuth", [
        0.713888888889, 0.713888888889, 0.713888888889, 0.713888888889,
        0.713888888889, 0.713888888889, 0.713888888889, 0.713888888889,
        0.713888888889, 0.713888888889, 0.713888888889, 0.713888888889,
        0.713888888889, 0.713888888889, 0.713888888889, 0.713888888889,
        0.713888888889, 0.713888888889, 0.713888888889, 0.713888888889,
    ]),
    # h = sqrt(h_prev^2 + D / c)  (h_prev 0.4)
    "GXYZ-GRW": ("azimuth", [
        0.416999866773, 0.416999866773, 0.416999866773, 0.416999866773,
        0.416999866773, 0.416999866773, 0.416999866773, 0.416999866773,
        0.416999866773, 0.416999866773, 0.416999866773, 0.416999866773,
        0.416999866773, 0.416999866773, 0.416999866773, 0.416999866773,
        0.416999866773, 0.416999866773, 0.416999866773, 0.416999866773,
    ]),
    # h = sqrt(h_prev^2 + D / (c cos^2((I_prev + I) / 2)))  (I_prev = I - 2 deg)
    "GZ-GRW": ("azimuth", [
        0.417081289689, 0.41732866954, 0.417886549624, 0.418553581622,
        0.419709509184, 0.420942775834, 0.422969553073, 0.425086438866,
        0.428564921036, 0.432251129582, 0.438484566312, 0.44536264809,
        0.45766725244, 0.47224540521, 0.500971838441, 0.539475578971,
        0.630325794253, 0.787783789056, 1.04649135168, 1.19630873807,
    ]),
}


def _env(k):
    inc = math.radians(INC[k])
    return {
        "Inc": inc,
        "AzT": math.radians(AZ[k]),
        "Lat": math.radians(LAT),
        "EarthRate": EARTH_RATE,
        "GField": GRAVITY,
        "NoiseReductionFactor": NOISE_FACTOR,
        "IncCant": inc - math.radians(CANT),
        "MD": MD,
        "MDPrev": MD_PREV,
        "IncPrev": inc - math.radians(INC_PREV_OFFSET),
        "GXYZRunningSpeed": SPEED,
        "GZRunningSpeed": SPEED,
        "GXYRunningSpeed": SPEED,
        "XYZ_Gyro_Drift": DRIFT_PREV,
        "XYZ_Gyro_Random_Walk": WALK_PREV,
        "Z_Gyro_Random_Walk": WALK_PREV,
    }


def test_library_formulas_match_paper():
    assert set(EXPECTED) == set(DATA["terms"]) == set(LIBRARY["terms"])
    for name, (field, values) in EXPECTED.items():
        wf = LIBRARY["weighting_functions"][LIBRARY["terms"][name]["weighting_function"]]
        for k in range(20):
            env = _env(k)
            got = parse(wf[field]).evaluate(env)
            assert got == pytest.approx(values[k], rel=1e-9), (name, field, INC[k], AZ[k])
            for other in {"depth", "inclination", "azimuth"} - {field}:
                assert parse(wf[other]).evaluate(env) == 0, (name, other)


def test_library_terms_cite_their_table():
    for name, spec in DATA["terms"].items():
        wf = LIBRARY["weighting_functions"][LIBRARY["terms"][name]["weighting_function"]]
        assert wf["source"] == f"SPE 90408 {spec['table']}"
    assert {n for n, t in LIBRARY["terms"].items() if "mode" in t} == {
        n for n, s in DATA["terms"].items() if s["table"] in ("Table 3", "Table 4", "Table 6", "Table 8")
    }
    assert not set(LIBRARY["terms"]) & set(REV5["terms"])


def test_examples_validate():
    problems = [p for p in validate_repo(ROOT) if "SPE90408" in p.file or "spe90408" in p.file]
    assert problems == []


def _expected_terms(n):
    model = next(m for m in DATA["models"] if m["number"] == n)
    return {term: mag for g in model["groups"] for term, mag in DATA["groups"][g]}


@pytest.mark.parametrize("n", range(1, 7))
def test_example_terms_match_table_d7(n):
    model = MODELS[n]
    assert {t["term"]: t["magnitude"] for t in model["terms"]} == _expected_terms(n)
    assert [lib["id"] for lib in model["libraries"]] == ["iscwsa:rev5", "iscwsa:spe90408"]
    assert model["metadata"]["status"] == "reference"
    assert model["metadata"]["model_id"] == f"iscwsa:SPE90408_Ex{n}"
    assert model["metadata"]["source"] == f"SPE 90408 Appendix D, Example Model #{n}"


def test_table_d7_spot_checks():
    mags = {n: {t["term"]: t["magnitude"] for t in MODELS[n]["terms"]} for n in MODELS}
    assert mags[3]["GXY-GD"] == 0.5 and mags[3]["GXY-GRW"] == 0.5
    assert mags[2]["EXT-REF"] == 5.0 and mags[2]["GZ-GD"] == 1.0 and mags[2]["GZ-GRW"] == 1.0
    for n in MODELS:
        assert (mags[n]["DRFR"], mags[n]["DSFW"], mags[n]["DSTG"]) == (0.5, 0.001, 5e-07)
        assert [mags[n][f"XYM{i}"] for i in (1, 2, 3, 4)] == [0.1, 0.1, 0.2, 0.2] and mags[n]["SAG"] == 0.1


def test_example_gyro_blocks():
    g = {n: MODELS[n]["gyro"] for n in MODELS}
    assert [g[n]["accelerometer"] for n in range(1, 7)] == ["xy", "xy", "xyz", "xy", "xyz", "xyz"]
    for n in (1, 6):
        assert g[n]["continuous"] == [] and (g[n]["stationary"]["start_inc"]["value"], g[n]["stationary"]["end_inc"]["value"]) == (0, 150)
    assert g[2]["external_reference"] is True and "stationary" not in g[2]
    assert [(b["axes"], b["start_inc"]["value"], b["end_inc"]["value"], b["init_inc"]["value"]) for b in g[2]["continuous"]] == [("z", 0, 150, 0)]
    assert (g[2]["min_distance"]["value"], g[2]["init_factor"]["value"]) == (9999, 1)
    st = g[3]["stationary"]
    assert (st["axes"], st["start_inc"]["value"], st["end_inc"]["value"]) == ("xy", 0, 17)
    assert [(b["axes"], b["start_inc"]["value"], b["end_inc"]["value"], b["init_inc"]["value"]) for b in g[3]["continuous"]] == [("xy", 17, 150, 17)]
    assert (g[3]["min_distance"]["value"], g[3]["init_factor"]["value"]) == (2500, 0.5)
    assert "stationary" not in g[4] and g[4]["accelerometer_cant"]["value"] == 17 and g[4]["cant_switching"] is True
    assert [(b["axes"], b["start_inc"]["value"], b["end_inc"]["value"], b["init_inc"]["value"]) for b in g[4]["continuous"]] == [("z", 0, 17, 3), ("xy", 17, 150, 3)]
    assert (g[4]["min_distance"]["value"], g[4]["init_factor"]["value"]) == (2500, 1)
    assert "stationary" not in g[5]
    assert [(b["axes"], b["start_inc"]["value"], b["end_inc"]["value"], b["init_inc"]["value"]) for b in g[5]["continuous"]] == [("xyz", 0, 150, -1)]
    for n in (2, 3, 4, 5):
        assert all(b["gyro_speed"] == {"value": 2160, "unit": "m/hr", "text": "2160 m/hr"} for b in g[n]["continuous"])
    for n in (1, 2, 3, 5, 6):
        assert "accelerometer_cant" not in g[n] and "cant_switching" not in g[n]


def test_make_spe90408_deterministic():
    first, second = make_spe90408.build(), make_spe90408.build()
    assert first == second
    assert set(first) == {"library/iscwsa/spe90408.json"} | {f"conformance/models/iscwsa/SPE90408_Ex{n}.json" for n in range(1, 7)}
    for rel, text in first.items():  # the checked-in files are what the tool writes
        assert (ROOT / rel).read_bytes() == text.encode("utf-8"), rel


def test_no_depth_systematic_reference():
    for model in MODELS.values():
        depth = {}
        for t in model["terms"]:
            name = t["term"].split(":")[-1]
            entry = LIBRARY["terms"].get(name) or REV5["terms"][name]
            if entry["type"] == "Depth":
                depth[name] = entry["propagation"]
        assert depth == {"DRFR": "Random", "DSFW": "Well", "DSTG": "Global"}
