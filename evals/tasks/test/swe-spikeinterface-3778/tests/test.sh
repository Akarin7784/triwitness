#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  src/spikeinterface/core/tests/test_unitsaggregationsorting.py::test_unitsaggregationsorting_properties \
  src/spikeinterface/core/tests/test_unitsaggregationsorting.py::test_unitsaggregationsorting_spiketrains \
  src/spikeinterface/core/tests/test_unitsaggregationsorting.py::test_unitsaggregationsorting_annotations \
  src/spikeinterface/core/tests/test_unitsaggregationsorting.py::test_unit_aggregation_preserve_ids \
  src/spikeinterface/core/tests/test_unitsaggregationsorting.py::test_unit_aggregation_does_not_preserve_ids_if_not_unique \
  src/spikeinterface/core/tests/test_unitsaggregationsorting.py::test_unit_aggregation_does_not_preserve_ids_not_the_same_type \
  src/spikeinterface/postprocessing/tests/test_template_metrics.py::test_different_params_template_metrics \
  src/spikeinterface/postprocessing/tests/test_template_metrics.py::test_backwards_compat_params_template_metrics \
  src/spikeinterface/postprocessing/tests/test_template_metrics.py::test_compute_new_template_metrics \
  src/spikeinterface/postprocessing/tests/test_template_metrics.py::test_metric_names_in_same_order \
  src/spikeinterface/postprocessing/tests/test_template_metrics.py::test_save_template_metrics \
  'src/spikeinterface/postprocessing/tests/test_template_metrics.py::TestTemplateMetrics::test_extension[params0]' \
  'src/spikeinterface/postprocessing/tests/test_template_metrics.py::TestTemplateMetrics::test_extension[params1]' \
  'src/spikeinterface/postprocessing/tests/test_template_metrics.py::TestTemplateMetrics::test_extension[params2]' \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_compute_new_quality_metrics \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_metric_names_in_same_order \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_save_quality_metrics \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_unit_structure_in_output \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_unit_id_order_independence \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_synchrony_counts_no_sync \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_synchrony_counts_one_sync \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_synchrony_counts_one_quad_sync \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_synchrony_counts_not_all_units \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_mahalanobis_metrics \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_lda_metrics \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_nearest_neighbors_metrics \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_silhouette_score_metrics \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_simplified_silhouette_score_metrics \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_calculate_firing_rate_num_spikes \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_calculate_firing_range \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_calculate_amplitude_cutoff \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_calculate_amplitude_median \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_calculate_amplitude_cv_metrics \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_calculate_snrs \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_calculate_presence_ratio \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_calculate_isi_violations \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_calculate_sliding_rp_violations \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_calculate_rp_violations \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_synchrony_metrics \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_synchrony_metrics_unit_id_subset \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_synchrony_metrics_no_unit_ids \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_calculate_drift_metrics \
  src/spikeinterface/qualitymetrics/tests/test_metrics_functions.py::test_calculate_sd_ratio; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
