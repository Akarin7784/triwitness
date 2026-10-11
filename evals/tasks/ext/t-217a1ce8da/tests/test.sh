#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test/unit/test_filters.py::FilterTest::test_trim_nearby_peaks_threshold \
  test/unit/test_filters.py::FilterTest::test_im_in_not_im_out \
  test/unit/test_filters.py::FilterTest::test_porosimetry_compare_modes_2d \
  test/unit/test_filters.py::FilterTest::test_porosimetry_num_points \
  test/unit/test_filters.py::FilterTest::test_porosimetry_compare_modes_3d \
  test/unit/test_filters.py::FilterTest::test_porosimetry_with_sizes \
  test/unit/test_filters.py::FilterTest::test_porosimetry_mio_mode_without_fft \
  test/unit/test_filters.py::FilterTest::test_porosimetry_hybrid_mode_without_fft \
  test/unit/test_filters.py::FilterTest::test_apply_chords_axis0 \
  test/unit/test_filters.py::FilterTest::test_apply_chords_axis1 \
  test/unit/test_filters.py::FilterTest::test_apply_chords_axis2 \
  test/unit/test_filters.py::FilterTest::test_apply_chords_with_negative_spacing \
  test/unit/test_filters.py::FilterTest::test_apply_chords_without_trimming \
  test/unit/test_filters.py::FilterTest::test_apply_chords_3D \
  test/unit/test_filters.py::FilterTest::test_flood \
  test/unit/test_filters.py::FilterTest::test_find_disconnected_voxels_2d \
  test/unit/test_filters.py::FilterTest::test_find_disconnected_voxels_2d_conn4 \
  test/unit/test_filters.py::FilterTest::test_find_disconnected_voxels_3d \
  test/unit/test_filters.py::FilterTest::test_find_disconnected_voxels_3d_conn6 \
  test/unit/test_filters.py::FilterTest::test_trim_nonpercolating_paths_2d_axis0 \
  test/unit/test_filters.py::FilterTest::test_trim_nonpercolating_paths_2d_axis1 \
  test/unit/test_filters.py::FilterTest::test_trim_nonpercolating_paths_no_paths \
  test/unit/test_filters.py::FilterTest::test_trim_nonpercolating_paths_3d_axis2 \
  test/unit/test_filters.py::FilterTest::test_trim_nonpercolating_paths_3d_axis1 \
  test/unit/test_filters.py::FilterTest::test_trim_nonpercolating_paths_3d_axis0 \
  test/unit/test_filters.py::FilterTest::test_trim_disconnected_blobs \
  test/unit/test_filters.py::FilterTest::test_fill_blind_pores \
  test/unit/test_filters.py::FilterTest::test_trim_floating_solid \
  test/unit/test_filters.py::FilterTest::test_trim_extrema_min \
  test/unit/test_filters.py::FilterTest::test_trim_extrema_max \
  test/unit/test_filters.py::FilterTest::test_local_thickness \
  test/unit/test_filters.py::FilterTest::test_local_thickness_known_sizes \
  test/unit/test_filters.py::FilterTest::test_porosimetry \
  test/unit/test_filters.py::FilterTest::test_morphology_fft_dilate_2d \
  test/unit/test_filters.py::FilterTest::test_morphology_fft_erode_2d \
  test/unit/test_filters.py::FilterTest::test_morphology_fft_opening_2d \
  test/unit/test_filters.py::FilterTest::test_morphology_fft_closing_2d \
  test/unit/test_filters.py::FilterTest::test_morphology_fft_dilate_3d \
  test/unit/test_filters.py::FilterTest::test_morphology_fft_erode_3d \
  test/unit/test_filters.py::FilterTest::test_morphology_fft_opening_3d \
  test/unit/test_filters.py::FilterTest::test_morphology_fft_closing_3d \
  test/unit/test_filters.py::FilterTest::test_reduce_peaks \
  test/unit/test_filters.py::FilterTest::test_nphase_border_2d_no_diagonals \
  test/unit/test_filters.py::FilterTest::test_nphase_border_2d_diagonals \
  test/unit/test_filters.py::FilterTest::test_nphase_border_3d_no_diagonals \
  test/unit/test_filters.py::FilterTest::test_nphase_border_3d_diagonals \
  test/unit/test_filters.py::FilterTest::test_find_dt_artifacts \
  test/unit/test_filters.py::FilterTest::test_snow_partitioning_n \
  test/unit/test_filters.py::FilterTest::test_snow_partitioning_parallel \
  test/unit/test_filters.py::FilterTest::test_chunked_func_2d \
  test/unit/test_filters.py::FilterTest::test_chunked_func_3d \
  test/unit/test_filters.py::FilterTest::test_chunked_func_3d_w_strel \
  test/unit/test_filters.py::FilterTest::test_chunked_func_w_ill_defined_filter \
  test/unit/test_filters.py::FilterTest::test_apply_padded \
  test/unit/test_filters.py::FilterTest::test_trim_small_clusters \
  test/unit/test_filters.py::FilterTest::test_hold_peaks_input \
  test/unit/test_filters.py::FilterTest::test_hold_peaks_algorithm; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
