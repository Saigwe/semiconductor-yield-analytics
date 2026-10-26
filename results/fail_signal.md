# Sensor fail signal: is it more than noise?

440 usable sensors, 104 failing and 1463 passing wafers.

- 22 sensors pass a 5% false discovery rate (Welch t-test, Benjamini-Hochberg).
- 5 sensors have |d| above 0.464, the 95th percentile of the largest |d| across all sensors when pass/fail labels are shuffled (500 times).

| Rank | Sensor | Synthetic name | Cohen's d | q value | Beats shuffle max |
|---:|---:|---|---:|---:|---|
| 1 | 60 | overlay_y_s060 | 0.632 | 0.0001 | yes |
| 2 | 104 | endpoint_time_s104 | 0.614 | 0.0001 | yes |
| 3 | 511 | contact_resistance_s511 | 0.533 | 0.0118 | yes |
| 4 | 349 | pad_pressure_s349 | 0.523 | 0.1331 | yes |
| 5 | 432 | tilt_angle_s432 | 0.491 | 0.1649 | yes |
| 6 | 435 | energy_s435 | 0.455 | 0.2469 | no |
| 7 | 431 | energy_s431 | 0.446 | 0.2298 | no |
| 8 | 436 | tilt_angle_s436 | 0.442 | 0.2621 | no |
| 9 | 22 | focus_offset_s022 | 0.440 | 0.0687 | no |
| 10 | 29 | exposure_dose_s029 | -0.435 | 0.0021 | no |
| 11 | 437 | beam_current_s437 | 0.433 | 0.2669 | no |
| 12 | 130 | rf_power_s130 | 0.416 | 0.0000 | no |
| 13 | 299 | removal_rate_s299 | 0.415 | 0.1649 | no |
| 14 | 211 | precursor_flow_s211 | 0.411 | 0.1649 | no |
| 15 | 164 | endpoint_time_s164 | 0.406 | 0.1649 | no |
