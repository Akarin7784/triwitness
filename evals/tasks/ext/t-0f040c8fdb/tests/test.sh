#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  'tests/css/test_stylesheet.py::test_color_property_parsing[turquoise4-expectation3-expected_color3]' \
  'tests/css/test_stylesheet.py::test_color_property_parsing[red-expectation0-expected_color0]' \
  'tests/css/test_stylesheet.py::test_color_property_parsing[dark_cyan-expectation1-expected_color1]' \
  'tests/css/test_stylesheet.py::test_color_property_parsing[medium_turquoise-expectation2-expected_color2]' \
  'tests/css/test_stylesheet.py::test_color_property_parsing[#ffcc00-expectation4-expected_color4]' \
  'tests/css/test_stylesheet.py::test_color_property_parsing[#ffcc0033-expectation5-expected_color5]' \
  'tests/css/test_stylesheet.py::test_color_property_parsing[rgb(200,90,30)-expectation6-expected_color6]' \
  'tests/css/test_stylesheet.py::test_color_property_parsing[rgba(200,90,30,0.3)-expectation7-expected_color7]' \
  'tests/css/test_stylesheet.py::test_color_property_parsing[coffee-expectation8-None]' \
  'tests/css/test_stylesheet.py::test_color_property_parsing[turquoise10-expectation9-None]' \
  'tests/css/test_stylesheet.py::test_color_property_parsing[1-expectation11-None]' \
  'tests/css/test_stylesheet.py::test_color_property_parsing[()-expectation12-None]' \
  'tests/css/test_stylesheet.py::test_color_property_parsing[#09f-expectation13-None]'; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
