#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  'tests/test_colorama.py::test_honor_no_color_standard[__stdout__--True]' \
  'tests/test_colorama.py::test_honor_no_color_standard[__stderr__--True]' \
  'tests/test_colorama.py::test_honor_no_color_standard[stdout--True]' \
  'tests/test_colorama.py::test_honor_no_color_standard[stderr--True]' \
  'tests/test_colorama.py::test_honor_no_color_standard[--True]' \
  'tests/test_colorama.py::test_honor_force_color_standard[__stdout__-1-True]' \
  'tests/test_colorama.py::test_honor_force_color_standard[__stderr__-1-True]' \
  'tests/test_colorama.py::test_honor_force_color_standard[stdout-1-True]' \
  'tests/test_colorama.py::test_honor_force_color_standard[stderr-1-True]' \
  'tests/test_colorama.py::test_honor_force_color_standard[-1-True]' \
  tests/test_colorama.py::test_stream_is_none \
  tests/test_colorama.py::test_is_a_tty \
  tests/test_colorama.py::test_is_not_a_tty \
  tests/test_colorama.py::test_is_a_tty_exception \
  'tests/test_colorama.py::test_pycharm_fixed[__stdout__-True]' \
  'tests/test_colorama.py::test_pycharm_fixed[__stderr__-True]' \
  'tests/test_colorama.py::test_pycharm_fixed[stdout-False]' \
  'tests/test_colorama.py::test_pycharm_fixed[stderr-False]' \
  'tests/test_colorama.py::test_pycharm_fixed[-False]' \
  'tests/test_colorama.py::test_github_actions_fixed[__stdout__-True]' \
  'tests/test_colorama.py::test_github_actions_fixed[__stderr__-True]' \
  'tests/test_colorama.py::test_github_actions_fixed[stdout-False]' \
  'tests/test_colorama.py::test_github_actions_fixed[stderr-False]' \
  'tests/test_colorama.py::test_github_actions_fixed[-False]' \
  'tests/test_colorama.py::test_dumb_term_not_colored[__stdout__-False]' \
  'tests/test_colorama.py::test_dumb_term_not_colored[__stderr__-False]' \
  'tests/test_colorama.py::test_dumb_term_not_colored[stdout-True]' \
  'tests/test_colorama.py::test_dumb_term_not_colored[stderr-True]' \
  'tests/test_colorama.py::test_dumb_term_not_colored[-True]' \
  'tests/test_colorama.py::test_honor_no_color_standard[__stdout__-1-False]' \
  'tests/test_colorama.py::test_honor_no_color_standard[__stderr__-1-False]' \
  'tests/test_colorama.py::test_honor_no_color_standard[stdout-1-False]' \
  'tests/test_colorama.py::test_honor_no_color_standard[stderr-1-False]' \
  'tests/test_colorama.py::test_honor_no_color_standard[-1-False]' \
  'tests/test_colorama.py::test_honor_force_color_standard[__stdout__--False]' \
  'tests/test_colorama.py::test_honor_force_color_standard[__stderr__--False]' \
  'tests/test_colorama.py::test_honor_force_color_standard[stdout--False]' \
  'tests/test_colorama.py::test_honor_force_color_standard[stderr--False]' \
  'tests/test_colorama.py::test_honor_force_color_standard[--False]' \
  'tests/test_colorama.py::test_mintty_not_fixed_linux[__stdout__-False]' \
  'tests/test_colorama.py::test_mintty_not_fixed_linux[__stderr__-False]' \
  'tests/test_colorama.py::test_mintty_not_fixed_linux[stdout-False]' \
  'tests/test_colorama.py::test_mintty_not_fixed_linux[stderr-False]' \
  'tests/test_colorama.py::test_mintty_not_fixed_linux[-False]' \
  'tests/test_colorama.py::test_jupyter_fixed[stdout-StreamIsattyFalse-True]' \
  'tests/test_colorama.py::test_jupyter_fixed[stderr-StreamIsattyFalse-True]' \
  'tests/test_colorama.py::test_jupyter_fixed[__stdout__-StreamIsattyFalse-False]' \
  'tests/test_colorama.py::test_jupyter_fixed[__stderr__-StreamIsattyFalse-False]' \
  'tests/test_colorama.py::test_jupyter_fixed[stdout-StreamIsattyTrue-False]' \
  'tests/test_colorama.py::test_jupyter_fixed[stderr-StreamIsattyTrue-False]' \
  'tests/test_colorama.py::test_jupyter_fixed[-StreamIsattyFalse-False]' \
  tests/test_colorama.py::test_jupyter_missing_lib \
  'tests/test_colorama.py::test_dont_wrap_on_linux[__stdout__]' \
  'tests/test_colorama.py::test_dont_wrap_on_linux[__stderr__]'; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
