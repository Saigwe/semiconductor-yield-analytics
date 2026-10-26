---
title: Semiconductor Yield & Test Analytics
---

Yield, process control and failure signals for 1,567 real wafer test runs from the UCI SECOM dataset (July to October
2008, 590 sensors). Pass/fail results and sensor readings are **real**. Lots, tools, process steps and sensor names
are **synthetic** context, because SECOM is anonymised. Source:
[github.com/Saigwe/semiconductor-yield-analytics](https://github.com/Saigwe/semiconductor-yield-analytics).

```sql kpis
select * from secom.kpis
```

<BigValue data={kpis} value=wafers title="Wafers tested" fmt=num0 />
<BigValue data={kpis} value=yield_rate title="Yield" fmt=pct1 />
<BigValue data={kpis} value=usable_sensors title="Usable sensors (of 590)" fmt=num0 />
<BigValue data={kpis} value=days_above_limit title="Days above the p-chart limit" fmt=num0 />

## Yield trend: daily fail-rate p-chart

The centre line is the fail rate in the reference period (the first half of runs). Limits are 3 sigma for each day's
wafer count, so they widen on days with few wafers.

```sql p_chart
select test_date, fail_rate, upper_limit, centre_line, wafers_tested, wafers_failed
from secom.yield_p_chart order by test_date
```

<LineChart data={p_chart} x=test_date y={['fail_rate', 'upper_limit', 'centre_line']} yFmt=pct0
           colorPalette={['#c2410c', '#94a3b8', '#475569']} title="Daily fail rate vs control limits" />

```sql signals
select test_date, wafers_tested, wafers_failed, fail_rate, upper_limit
from secom.yield_p_chart where is_above_limit order by test_date
```

<DataTable data={signals}>
  <Column id=test_date title="Day above the limit" />
  <Column id=wafers_tested title="Wafers" />
  <Column id=wafers_failed title="Failed" />
  <Column id=fail_rate title="Fail rate" fmt=pct1 />
  <Column id=upper_limit title="Upper limit" fmt=pct1 />
</DataTable>

```sql lots
select lot_id, yield_rate, wafers_tested, wafers_failed from secom.yield_by_lot order by yield_rate, lot_id limit 15
```

<BarChart data={lots} x=lot_id y=yield_rate sort=false yFmt=pct0 title="15 lowest-yield lots (synthetic 25-wafer lots)" />

## Sensor Pareto: which signals separate failing wafers?

Ranked by Cohen's d between failing and passing wafers. With 440 sensors, some will look different by chance, so each
is checked two ways: a 5% false discovery rate, and the largest effect seen when pass/fail labels are shuffled 500
times. Only sensors 60, 104 and 511 pass both.

```sql pareto
select cast(sensor_id as varchar) as sensor, abs_effect_size, signal_rank,
       case when passes_fdr and beats_shuffle_max then 'Passes both checks'
            when passes_fdr or beats_shuffle_max then 'Passes one check'
            else 'Not significant' end as evidence
from secom.sensor_signal where signal_rank <= 20 order by signal_rank
```

<BarChart data={pareto} x=sensor y=abs_effect_size series=evidence sort=false yFmt=num2
          title="Top 20 sensors by |effect size|" />

```sql signal_table
select signal_rank, sensor_id, parameter_name, step_name, effect_size, q_value, passes_fdr, beats_shuffle_max
from secom.sensor_signal order by signal_rank
```

<DataTable data={signal_table} rows=10>
  <Column id=signal_rank title="Rank" />
  <Column id=sensor_id title="Sensor" />
  <Column id=parameter_name title="Synthetic name" />
  <Column id=effect_size title="Cohen's d" fmt=num3 />
  <Column id=q_value title="q value" fmt=num4 />
  <Column id=passes_fdr title="FDR 5%" />
  <Column id=beats_shuffle_max title="Beats shuffle" />
</DataTable>

## Process drift: why static limits go stale

```sql ooc
select period, outcome, avg_out_of_control, wafers from secom.ooc_by_period
order by case when period like 'Reference%' then 0 else 1 end, outcome
```

<BarChart data={ooc} x=period y=avg_out_of_control series=outcome type=grouped sort=false yFmt=num1
          title="Out-of-control readings per wafer (limits from the reference period)" />

In the later half, passing wafers trip more than twice as many static limits as in the reference period, and failing
wafers no longer stand out. The process drifted, so limits and models have to be refreshed as new wafers are tested.

## Which wafers to inspect first?

Every method was trained or calibrated on the first 784 wafers and scored on the later 783 (37 fails, base rate 4.7%).
All variants tried are shown. Average precision is the area under the precision-recall curve; random scores about the
base rate.

```sql methods
select case method
         when 'random' then 'Random'
         when 'spc_ooc_count' then 'Static SPC count'
         when 'isolation_forest' then 'Isolation Forest (one fit)'
         when 'logistic_l2' then 'Logistic regression (one fit)'
         when 'spc_rolling_w100' then 'Rolling SPC, 100 wafers'
         when 'spc_rolling_w200' then 'Rolling SPC, 200 wafers'
         when 'spc_rolling_w400' then 'Rolling SPC, 400 wafers'
         when 'wf_logistic_l2' then 'Walk-forward logistic'
         when 'wf_gbm' then 'Walk-forward gradient boosting'
         when 'wf_isolation_forest' then 'Walk-forward Isolation Forest'
       end as method,
       average_precision, ap_low, ap_high, roc_auc, roc_auc_low, roc_auc_high, precision_at_10, recall_top_10pct
from secom.ranking_methods order by average_precision
```

<BarChart data={methods} x=method y=average_precision swapXY=true sort=false yFmt=num3
          title="Average precision on the later half (base rate 0.047)" />

<DataTable data={methods}>
  <Column id=method />
  <Column id=average_precision title="Avg precision" fmt=num3 />
  <Column id=ap_low title="95% CI low" fmt=num3 />
  <Column id=ap_high title="95% CI high" fmt=num3 />
  <Column id=roc_auc title="ROC AUC" fmt=num3 />
  <Column id=roc_auc_low title="95% CI low" fmt=num3 />
  <Column id=roc_auc_high title="95% CI high" fmt=num3 />
  <Column id=precision_at_10 title="Precision@10" fmt=pct0 />
  <Column id=recall_top_10pct title="Fails in top 10%" fmt=pct0 />
</DataTable>

## Asking questions in plain English, safely

The NL-to-SQL agent may only read approved gold tables. Its guardrail uses DuckDB's own parser, and the query runs on a
read-only connection with file access disabled.

```sql guard
select guardrail, correct, cases from secom.guardrail
```

<DataTable data={guard}>
  <Column id=guardrail title="Guardrail" />
  <Column id=correct title="Correct" />
  <Column id=cases title="Cases (20 attacks, 8 legitimate)" />
</DataTable>
