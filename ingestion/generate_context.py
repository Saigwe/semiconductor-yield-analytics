"""Generate SYNTHETIC fab context for SECOM runs: process steps, tools, sensor catalogue, lot/wafer map.

SECOM is anonymised, so this context exists only to demonstrate dimensional modelling.
It is deterministic (fixed seed) and does not describe any real fab.
"""
import argparse
import random

import duckdb
import pandas as pd

SEED = 42
WAFERS_PER_LOT = 25
STEPS = [
    (1, "lithography", ["exposure_dose", "focus_offset", "overlay_x", "overlay_y"]),
    (2, "etch", ["chamber_pressure", "rf_power", "gas_flow_cf4", "endpoint_time"]),
    (3, "deposition", ["film_thickness", "chamber_temp", "precursor_flow", "deposition_rate"]),
    (4, "cmp", ["pad_pressure", "slurry_flow", "removal_rate", "platen_speed"]),
    (5, "implant", ["beam_current", "dose", "energy", "tilt_angle"]),
    (6, "electrical_test", ["leakage_current", "threshold_voltage", "contact_resistance", "drive_current"]),
]
UNITS = {
    "exposure_dose": "mJ/cm2", "focus_offset": "nm", "overlay_x": "nm", "overlay_y": "nm",
    "chamber_pressure": "mTorr", "rf_power": "W", "gas_flow_cf4": "sccm", "endpoint_time": "s",
    "film_thickness": "nm", "chamber_temp": "C", "precursor_flow": "sccm", "deposition_rate": "nm/min",
    "pad_pressure": "psi", "slurry_flow": "ml/min", "removal_rate": "nm/min", "platen_speed": "rpm",
    "beam_current": "mA", "dose": "ions/cm2", "energy": "keV", "tilt_angle": "deg",
    "leakage_current": "nA", "threshold_voltage": "V", "contact_resistance": "ohm", "drive_current": "uA",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="warehouse/bt2.duckdb")
    args = parser.parse_args()
    rng = random.Random(SEED)

    con = duckdb.connect(args.db)
    runs = con.execute(
        "select run_id, run_ts_raw from bronze.secom_runs order by run_id"
    ).df()
    sensor_ids = [r[0] for r in con.execute(
        "select distinct sensor_id from bronze.secom_sensor_readings order by 1"
    ).fetchall()]

    steps = pd.DataFrame([(s, n, s) for s, n, _ in STEPS], columns=["step_id", "step_name", "step_seq"])

    tools = []
    for step_id, step_name, _ in STEPS:
        for k in range(1, 3 + 1):
            tools.append((f"{step_name[:4].upper()}-{k:02d}", step_name, step_id, rng.randint(1, 4)))
    tools = pd.DataFrame(tools, columns=["tool_id", "tool_type", "step_id", "chamber_count"])

    # Sensors are spread evenly across steps in id order, then assigned a tool of that step.
    catalog = []
    per_step = -(-len(sensor_ids) // len(STEPS))
    for idx, sensor_id in enumerate(sensor_ids):
        step_id, step_name, params = STEPS[min(idx // per_step, len(STEPS) - 1)]
        param = params[idx % len(params)]
        step_tools = tools[tools.step_id == step_id].tool_id.tolist()
        catalog.append((sensor_id, step_id, rng.choice(step_tools), f"{param}_s{sensor_id:03d}", UNITS[param]))
    catalog = pd.DataFrame(catalog, columns=["sensor_id", "step_id", "tool_id", "parameter_name", "unit"])

    # Lots follow test order (run_id order mirrors file order, which is time-ordered in SECOM).
    lot_map = pd.DataFrame({
        "run_id": runs.run_id,
        "lot_id": [f"LOT{(i // WAFERS_PER_LOT) + 1:04d}" for i in range(len(runs))],
        "slot_no": [(i % WAFERS_PER_LOT) + 1 for i in range(len(runs))],
    })
    lot_map["wafer_id"] = lot_map.lot_id + "-W" + lot_map.slot_no.astype(str).str.zfill(2)

    for name, df in {
        "context_process_steps": steps,
        "context_tools": tools,
        "context_sensor_catalog": catalog,
        "context_lot_wafer_map": lot_map,
    }.items():
        con.register("df", df)
        con.execute(f"create or replace table bronze.{name} as select * from df")
        con.unregister("df")
    con.close()
    print(f"context generated: {len(steps)} steps, {len(tools)} tools, "
          f"{len(catalog)} sensors, {lot_map.lot_id.nunique()} lots (synthetic, seed={SEED})")


if __name__ == "__main__":
    main()
