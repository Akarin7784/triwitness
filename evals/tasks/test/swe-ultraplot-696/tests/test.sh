#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  'ultraplot/tests/test_subplots.py::test_outer_legend_keeps_ticklabels_with_label_sharing[labs]' \
  'ultraplot/tests/test_subplots.py::test_outer_legend_keeps_ticklabels_with_label_sharing[lims]' \
  ultraplot/tests/test_subplots.py::test_align_labels \
  'ultraplot/tests/test_subplots.py::test_all_share_levels[0]' \
  'ultraplot/tests/test_subplots.py::test_all_share_levels[1]' \
  'ultraplot/tests/test_subplots.py::test_all_share_levels[2]' \
  'ultraplot/tests/test_subplots.py::test_all_share_levels[3]' \
  'ultraplot/tests/test_subplots.py::test_all_share_levels[4]' \
  ultraplot/tests/test_subplots.py::test_share_all_basic \
  ultraplot/tests/test_subplots.py::test_span_labels \
  ultraplot/tests/test_subplots.py::test_title_deflection \
  ultraplot/tests/test_subplots.py::test_complex_ticks \
  ultraplot/tests/test_subplots.py::test_both_ticklabels \
  ultraplot/tests/test_subplots.py::test_gridspec_copies \
  ultraplot/tests/test_subplots.py::test_aligned_outer_guides \
  'ultraplot/tests/test_subplots.py::test_reference_aspect[simple-1.5-kwargs0-None-None]' \
  'ultraplot/tests/test_subplots.py::test_reference_aspect[funky_layout-1.5-kwargs1-<lambda>-3]' \
  'ultraplot/tests/test_subplots.py::test_reference_aspect[with_panels-2.0-kwargs2-<lambda>-None]' \
  'ultraplot/tests/test_subplots.py::test_axis_sharing[limits]' \
  'ultraplot/tests/test_subplots.py::test_axis_sharing[labels]' \
  ultraplot/tests/test_subplots.py::test_subset_share_xlabels_override \
  ultraplot/tests/test_subplots.py::test_spanning_labels_excluded_from_tight_layout_bbox \
  ultraplot/tests/test_subplots.py::test_subset_share_xlabels_implicit \
  ultraplot/tests/test_subplots.py::test_subset_share_ylabels_override \
  ultraplot/tests/test_subplots.py::test_subset_share_xlabels_implicit_column \
  ultraplot/tests/test_subplots.py::test_subset_share_xlabels_overridden_by_global_format \
  ultraplot/tests/test_subplots.py::test_full_grid_clears_share_label_groups \
  ultraplot/tests/test_subplots.py::test_subset_share_ylabels_implicit_row \
  ultraplot/tests/test_subplots.py::test_subset_share_xlabels_clear \
  ultraplot/tests/test_subplots.py::test_subset_share_labels_method_both \
  ultraplot/tests/test_subplots.py::test_subset_share_labels_invalid_axis \
  ultraplot/tests/test_subplots.py::test_subset_share_xlabels_mixed_sides \
  ultraplot/tests/test_subplots.py::test_subset_share_xlabels_implicit_column_top \
  ultraplot/tests/test_subplots.py::test_subset_share_ylabels_implicit_row_right \
  'ultraplot/tests/test_subplots.py::test_label_sharing_top_right[layout0]' \
  'ultraplot/tests/test_subplots.py::test_label_sharing_top_right[layout1]' \
  'ultraplot/tests/test_subplots.py::test_label_sharing_top_right[layout2]' \
  'ultraplot/tests/test_subplots.py::test_label_sharing_top_right[layout3]' \
  'ultraplot/tests/test_subplots.py::test_label_sharing_top_right[layout4]' \
  'ultraplot/tests/test_subplots.py::test_panel_sharing_top_right[layout0]' \
  ultraplot/tests/test_subplots.py::test_uneven_span_subplots \
  'ultraplot/tests/test_subplots.py::test_panel_ticklabels_all_sides_share_and_no_share[True]' \
  'ultraplot/tests/test_subplots.py::test_panel_ticklabels_all_sides_share_and_no_share[False]' \
  ultraplot/tests/test_subplots.py::test_non_rectangular_outside_labels_top \
  ultraplot/tests/test_subplots.py::test_outside_labels_with_panels \
  ultraplot/tests/test_subplots.py::test_panel_group_membership_respects_figure_share_flags \
  ultraplot/tests/test_subplots.py::test_panel_share_flag_controls_group_membership \
  ultraplot/tests/test_subplots.py::test_ticklabels_with_guides_share_true_cartesian \
  ultraplot/tests/test_subplots.py::test_deep_panel_stacks_border_detection \
  ultraplot/tests/test_subplots.py::test_right_panel_and_right_colorbar_border_priority \
  ultraplot/tests/test_subplots.py::test_outer_legend_preserves_share_true_ticklabel_hiding; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
