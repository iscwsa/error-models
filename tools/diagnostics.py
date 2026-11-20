# This file was written by Claude Code (AI) on behalf of Kyle R. (@0xBEEFCAFE). Please review carefully.
"""Reader for ISCWSA published error-model diagnostics ("HPT ERROR MODEL" .dat files)."""
from dataclasses import dataclass, field
from pathlib import Path

_SOURCE_KEYS = ("name", "leg", "magnitude", "units", "prop_mode", "lower_inc", "upper_inc")


@dataclass
class Station:
    md: float
    inc: float
    azt: float
    tf: float
    tvd: float
    mode: str
    # term name (including "TOTAL") -> (NN, EE, VV, NE, NV, EV) in m^2, as printed
    terms: dict = field(default_factory=dict)


@dataclass
class Diagnostics:
    well: dict
    sources: list
    stations: list


def _is_rule(line: str) -> bool:
    s = line.strip()
    return len(s) > 10 and set(s) == {"*"}


def read_hpt(path: Path) -> Diagnostics:
    lines = Path(path).read_text(encoding="ascii").splitlines()
    well: dict = {}
    sources: list = []
    stations: list = []
    section = None
    station = None
    expect_name = False
    for line in lines:
        s = line.strip()
        if _is_rule(line):
            expect_name = True
            continue
        if expect_name:
            if not s:
                continue
            expect_name = False
            # A rule inside COVARIANCE OUTPUTS just separates stations; the next
            # line is then a station header ("MD INC AZT ..."), not a section name.
            if section == "COVARIANCE OUTPUTS" and s.split()[0] == "MD":
                continue
            section = s
            continue
        if not s:
            continue
        if section == "WELL REFERENCE PARAMETERS":
            parts = s.replace(":", " ").split()
            well = {parts[i]: float(parts[i + 1]) for i in range(0, len(parts), 2)}
        elif section == "COMPILED ERROR SOURCES":
            f = s.split()
            if f[0] == "Name":
                continue
            sources.append({"name": f[0], "leg": int(f[1]), "magnitude": float(f[2]),
                            "units": f[3], "prop_mode": f[4],
                            "lower_inc": float(f[5]), "upper_inc": float(f[6])})
        elif section == "COVARIANCE OUTPUTS":
            f = s.split()
            if f[0] == "SURVEY":
                md, inc, azt, tf, tvd = (float(x) for x in f[1:6])
                station = Station(md, inc, azt, tf, tvd, f[6])
                stations.append(station)
            elif f[0] == "MD" or f[1:2] == ["MD"]:
                continue  # column headers
            elif station is not None and len(f) == 9 and f[1] == "nev":
                station.terms[f[0]] = tuple(float(x) for x in f[3:9])
    return Diagnostics(well, sources, stations)
