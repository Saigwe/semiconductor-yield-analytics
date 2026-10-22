"""Write a small SECOM-format fixture (no download needed) for CI and local smoke tests.

60 runs x 25 sensors, ~10% fails, some NaNs, one constant sensor, and a mean shift on
sensors 3 and 7 for failing runs so the fail-signal report has something to find.
"""
import argparse
import datetime as dt
import pathlib
import random

N_RUNS, N_SENSORS, SEED = 60, 25, 7


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="data/raw_fixture")
    args = parser.parse_args()
    rng = random.Random(SEED)
    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    start = dt.datetime(2008, 7, 19, 11, 55)
    feature_lines, label_lines = [], []
    for run in range(N_RUNS):
        fail = rng.random() < 0.10 or run in (5, 41)  # guarantee at least two fails
        values = []
        for s in range(1, N_SENSORS + 1):
            if s == 12:
                values.append("100")  # constant sensor
            elif rng.random() < 0.04:
                values.append("NaN")
            else:
                shift = 2.5 if fail and s in (3, 7) else 0.0
                values.append(f"{rng.gauss(10 + s + shift, 1.0):.4f}")
        feature_lines.append(" ".join(values))
        ts = start + dt.timedelta(hours=6 * run)
        label_lines.append(f'{1 if fail else -1} "{ts:%d/%m/%Y %H:%M:%S}"')

    (out / "secom.data").write_text("\n".join(feature_lines) + "\n")
    (out / "secom_labels.data").write_text("\n".join(label_lines) + "\n")
    print(f"fixture written to {out} ({N_RUNS} runs x {N_SENSORS} sensors)")


if __name__ == "__main__":
    main()
