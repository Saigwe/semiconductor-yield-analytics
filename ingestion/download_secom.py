"""Download the UCI SECOM dataset (CC BY 4.0) into data/raw/.

Source: McCann, M. & Johnston, A. (2008). SECOM [Dataset]. UCI Machine Learning Repository.
https://doi.org/10.24432/C54305
"""
import argparse
import io
import pathlib
import urllib.request
import zipfile

SECOM_ZIP_URL = "https://archive.ics.uci.edu/static/public/179/secom.zip"
WANTED = {"secom.data", "secom_labels.data", "secom.names"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="data/raw")
    args = parser.parse_args()

    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {SECOM_ZIP_URL}")
    with urllib.request.urlopen(SECOM_ZIP_URL, timeout=60) as resp:
        payload = resp.read()

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for member in zf.namelist():
            name = pathlib.PurePosixPath(member).name
            if name in WANTED:  # only extract known files; never trust archive paths
                (out / name).write_bytes(zf.read(member))
                print(f"  wrote {out / name}")

    missing = WANTED - {p.name for p in out.iterdir()}
    if missing:
        raise SystemExit(f"Missing files after download: {sorted(missing)}")


if __name__ == "__main__":
    main()
