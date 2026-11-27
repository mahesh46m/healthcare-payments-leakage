"""Download real public healthcare payment data.

Sources (all real, all public, no synthetic data):
  1. CMS Medicare Physician & Other Practitioners - by Provider and Service (2024)
     Maryland subset via the data.cms.gov API.
  2. CMS Medicare Physician & Other Practitioners - by Provider (2024), Maryland subset.
  3. CMS Medicare Inpatient Hospitals - by Provider (FY2024), national.
  4. HHS OIG List of Excluded Individuals/Entities (LEIE), current monthly file.

Run: python src/download.py
"""
import csv, json, time, urllib.parse, urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

API = "https://data.cms.gov/data-api/v1/dataset/{ds}/data"
DATASETS = {
    "partb_provider_service_md_2024.csv": (
        "92396110-2aed-4d63-a6a2-5d6207d46a29",
        {"filter[Rndrng_Prvdr_State_Abrvtn]": "MD"},
    ),
    "partb_provider_md_2024.csv": (
        "8889d81e-2ee7-448f-8713-f071038289b5",
        {"filter[Rndrng_Prvdr_State_Abrvtn]": "MD"},
    ),
    "inpatient_provider_fy2024.csv": (
        "ee6fb1a5-39b9-46b3-a980-a7284551a732",
        {},
    ),
}
LEIE_URL = "https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv"


def paged_download(ds, params, out_path):
    size = 5000
    done = 0
    fieldnames = None
    if out_path.exists():
        with open(out_path) as f:
            done = sum(1 for _ in f) - 1
        print(f"  resuming {out_path.name} at row {done}")
    mode = "a" if done else "w"
    with open(out_path, mode, newline="") as f:
        w = None
        offset = done
        while True:
            q = dict(params, size=size, offset=offset)
            url = API.format(ds=ds) + "?" + urllib.parse.urlencode(q)
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(url, timeout=60) as r:
                        batch = json.load(r)
                    break
                except Exception as e:
                    if attempt == 3:
                        raise
                    print(f"  retry {attempt+1} after {e}")
                    time.sleep(5)
            if not batch:
                break
            if w is None:
                fieldnames = list(batch[0].keys())
                w = csv.DictWriter(f, fieldnames=fieldnames)
                if mode == "w":
                    w.writeheader()
            w.writerows(batch)
            done += len(batch)
            offset += size
            print(f"  {out_path.name}: {done} rows", flush=True)
            if len(batch) < size:
                break
    print(f"saved {out_path} ({done} rows)")


def main():
    for name, (ds, params) in DATASETS.items():
        out = RAW / name
        if out.exists():
            print(f"skip {name}, already downloaded")
            continue
        print(f"downloading {name}")
        paged_download(ds, params, out)
    leie = RAW / "leie.csv"
    if not leie.exists():
        print("downloading OIG LEIE")
        urllib.request.urlretrieve(LEIE_URL, leie)
        print(f"saved {leie}")


if __name__ == "__main__":
    main()
