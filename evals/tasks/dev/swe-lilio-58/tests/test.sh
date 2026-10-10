#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_resample.py::TestResampleChecks::test_empty_calendar \
  tests/test_resample.py::TestResample::test_non_mapped_calendar \
  'tests/test_resample.py::TestResample::test_nontime_index[20151020]' \
  'tests/test_resample.py::TestResample::test_nontime_index[20191015]' \
  'tests/test_resample.py::TestResample::test_series[20151020]' \
  'tests/test_resample.py::TestResample::test_series[20191015]' \
  'tests/test_resample.py::TestResample::test_unnamed_series[20151020]' \
  'tests/test_resample.py::TestResample::test_unnamed_series[20191015]' \
  'tests/test_resample.py::TestResample::test_dataframe[20151020]' \
  'tests/test_resample.py::TestResample::test_dataframe[20191015]' \
  'tests/test_resample.py::TestResample::test_dataarray[20151020]' \
  'tests/test_resample.py::TestResample::test_dataarray[20191015]' \
  'tests/test_resample.py::TestResample::test_dataset[20151020]' \
  'tests/test_resample.py::TestResample::test_dataset[20191015]' \
  tests/test_resample.py::TestResample::test_multidim_dataset \
  'tests/test_resample.py::TestResample::test_target_period_dataframe[1-20151020]' \
  'tests/test_resample.py::TestResample::test_target_period_dataframe[1-20191015]' \
  'tests/test_resample.py::TestResample::test_target_period_dataframe[2-20151020]' \
  'tests/test_resample.py::TestResample::test_target_period_dataframe[2-20191015]' \
  'tests/test_resample.py::TestResample::test_target_period_dataset[1-20151020]' \
  'tests/test_resample.py::TestResample::test_target_period_dataset[1-20191015]' \
  'tests/test_resample.py::TestResample::test_target_period_dataset[2-20151020]' \
  'tests/test_resample.py::TestResample::test_target_period_dataset[2-20191015]' \
  tests/test_resample.py::TestResample::test_allow_overlap_dataframe \
  tests/test_resample.py::TestResample::test_1day_freq_dataframe \
  'tests/test_resample.py::TestResample::test_to_netcdf[20151020]' \
  'tests/test_resample.py::TestResample::test_to_netcdf[20191015]' \
  tests/test_resample.py::TestResample::test_overlapping \
  'tests/test_resample.py::TestResample::test_dataset_attrs[20151020]' \
  'tests/test_resample.py::TestResample::test_dataset_attrs[20191015]' \
  'tests/test_resample.py::TestResample::test_dataarray_attrs[20151020]' \
  'tests/test_resample.py::TestResample::test_dataarray_attrs[20191015]' \
  tests/test_resample.py::TestResampleChecks::test_low_freq_warning_dataframe \
  tests/test_resample.py::TestResampleChecks::test_too_low_freq_dataframe \
  tests/test_resample.py::TestResampleChecks::test_low_freq_warning_dataset \
  tests/test_resample.py::TestResampleChecks::test_too_low_freq_dataset \
  tests/test_resample.py::TestResampleChecks::test_low_freq_month_fmt_dataframe \
  tests/test_resample.py::TestResampleChecks::test_reserved_names_dataframe \
  tests/test_resample.py::TestResampleChecks::test_single_target \
  tests/test_resample.py::TestResampleChecks::test_single_precursor \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[mean]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[min]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[max]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[median]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[std]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[var]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[ptp]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[nanmean]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[nanmedian]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[nanstd]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[nanvar]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[sum]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[nansum]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[size]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataframe[count_nonzero]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[mean]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[min]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[max]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[median]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[std]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[var]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[ptp]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[nanmean]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[nanmedian]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[nanstd]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[nanvar]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[sum]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[nansum]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[size]' \
  'tests/test_resample.py::TestResampleMethods::test_all_methods_dataset[count_nonzero]' \
  tests/test_resample.py::TestResampleMethods::test_func_input_dataframe \
  tests/test_resample.py::TestResampleMethods::test_func_input_dataset \
  tests/test_resample.py::TestResampleDask::test_dask_resample; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
