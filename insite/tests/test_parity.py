from insite.calc.measures import compute

# Oracle: values verified against the legacy `contracting` engine + its 11 unit tests.
CASES = [
    ("area",        dict(height=1.5, width=2.8, count=40),           168.0),
    ("area",        dict(height=1.2, width=2.4, count=3),            8.64),
    ("perimeter",   dict(height=1.5, width=2.8, count=40),           344.0),
    ("linear",      dict(length=3.0, count=60),                      180.0),
    ("piece_waste", dict(count=500, wastage=1.1),                    550.0),
    ("count",       dict(count=25),                                  25.0),
    ("formula",     dict(height=1.5, width=2.8, count=40,
                         formula="height * width * count"),          168.0),
]

def test_parity_matches_oracle():
    for measure, kw, expected in CASES:
        got = compute(measure, **kw)
        assert abs(got - expected) < 1e-9, f"{measure} {kw}: {got} != {expected}"

if __name__ == "__main__":
    import sys
    try:
        test_parity_matches_oracle(); print("PASS parity"); sys.exit(0)
    except BaseException as e:  # noqa
        print("FAIL parity ->", repr(e)); sys.exit(1)
