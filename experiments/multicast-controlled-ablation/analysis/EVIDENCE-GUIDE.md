# Bounded evidence guide

All times with a `_ps` suffix are picoseconds; divide by 1,000,000 for microseconds. Packet residence means and maxima use their stated cohorts, not elapsed critical-path shares. Window1024/2048 results are interventions, never original Multicast v2 performance.

- `data/timing.csv`: six cells, both endpoints and within-strategy effects. `contrasts.csv`: three same-window gaps and difference-in-differences.
- `occupancy.csv`: selected source/pair and all-pair aggregate rows. Integrals use the named phase. Peaks, full-interval counts/maxima and other counters have whole-observed-run scope. Sums are Jetty-time, not elapsed wall time. Observed-run exposure includes empty/completed time through diagnostic writeout.
- `latency.csv`: three distinct latency boundaries for selected weight-admission cohorts, possibly completing after WeightReady. `all_pairs` means all selected TA samples, not all network pairs.
- `histogram.csv`: aggregate occupancy bins, not individual TA records or invented percentiles.
- `partitions.csv`, `switch_cohorts.csv`, `tp_reasons.csv`, `allready.csv`: only selected resources/queries. Phase partitions are disjoint; residence sums, Jetty exposures and AllReady observation spans overlap and cannot be added.
- `critical.csv`: actual terminal receiver dependencies, with selected source-prefix accounting. No full per-expert/per-node output is included.
- `selected_events.csv`, `selected_rtt.csv`: bounded Jetty transition and source3→59 TA selections. `4294967295` is an unset/sentinel identifier, not another node.
- `feedback/`: fixed source3 return-port and selected terminal-control aggregates, packet conservation, retained-tail capacity, frontiers and disjoint postweight landmarks. Compute landmarks explicitly refer to node batches, not individual expert starts. Selected feedback paths match chronological physical occurrences, not UID alone.
- `evidence/selected-baseline-*`: one local full→TAACK→release→admission cycle. The releasing packet's queue entry is censored; no exact queue residence is claimed.

The detailed selected-event/sample budget is87 rows: main Jetty28 + main TA12 + native feedback36 + baseline cycle6 + baseline native4 + final TA1. This counts records across views, not87 distinct events. The other path/frontier/terminal summaries are explicitly bounded aggregate selections. Complete raw rings, per-token, per-expert, full per-node and payload dumps are excluded.

`artifact-manifest.json` lists every published analysis artifact with its SHA-256 and CSV row count. Input fingerprints use case IDs and basenames only. Private raw inputs are not bundled. The unchanged experiment `analyze.py` and `plot.py` reproduce main aggregates/figures from verified run inputs; supplemental-analysis/collect-feedback.py and plot-feedback.py reproduce the return-port supplement. To redraw from this package, run the experiment plot.py against data/ with a new child output directory, and supplemental-analysis/plot-feedback.py against feedback/ with a new output directory. Neither operation runs a simulation.

All five PNG figures were visually inspected at final six-cell rendering; axes, intervention labels, scope notes and legends were legible without clipping.
