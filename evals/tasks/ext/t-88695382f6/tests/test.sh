#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test/test_pipeline.py::TestRunner::testSleep \
  test/test_pipeline.py::TestRunner::testSleepNotCalledWhenZero \
  test/test_pipeline.py::TestRunner::testAccessAndExistsAreCalled \
  test/test_pipeline.py::TestRunner::testCwdWithRelativeScriptPath \
  test/test_pipeline.py::TestRunner::testDuplicateName \
  test/test_pipeline.py::TestRunner::testEmptyJSON \
  test/test_pipeline.py::TestRunner::testFirstStep \
  test/test_pipeline.py::TestRunner::testFirstStepAndLastStepDifferent \
  test/test_pipeline.py::TestRunner::testFirstStepAndLastStepSame \
  test/test_pipeline.py::TestRunner::testForce \
  test/test_pipeline.py::TestRunner::testInvalidJSON \
  test/test_pipeline.py::TestRunner::testJSONList \
  test/test_pipeline.py::TestRunner::testLastStepBeforeFirstStep \
  test/test_pipeline.py::TestRunner::testList \
  test/test_pipeline.py::TestRunner::testNoSteps \
  test/test_pipeline.py::TestRunner::testNonDictionaryStep \
  test/test_pipeline.py::TestRunner::testNonExistentDependency \
  test/test_pipeline.py::TestRunner::testNonListDependencies \
  test/test_pipeline.py::TestRunner::testNonStringName \
  test/test_pipeline.py::TestRunner::testNonStringScript \
  test/test_pipeline.py::TestRunner::testNonYetDefinedDependency \
  test/test_pipeline.py::TestRunner::testNonexistentFirstStep \
  test/test_pipeline.py::TestRunner::testNonexistentLastStep \
  test/test_pipeline.py::TestRunner::testNonexistentScript \
  test/test_pipeline.py::TestRunner::testReSchedule \
  test/test_pipeline.py::TestRunner::testRepeatedTaskJobId \
  test/test_pipeline.py::TestRunner::testRepeatedTaskName \
  test/test_pipeline.py::TestRunner::testScheduledTime \
  test/test_pipeline.py::TestRunner::testScriptArgs \
  test/test_pipeline.py::TestRunner::testSingleCollectorDependencyTaskNamesAndJobIds \
  test/test_pipeline.py::TestRunner::testSingleDependencySynchronousTaskNamesJobIdsAndCalls \
  test/test_pipeline.py::TestRunner::testSingleDependencyTaskNamesJobIdsAndCalls \
  test/test_pipeline.py::TestRunner::testSleepNotCalledByDefault \
  test/test_pipeline.py::TestRunner::testSpecificationIsStored \
  test/test_pipeline.py::TestRunner::testStepStdout \
  test/test_pipeline.py::TestRunner::testStepWithoutName \
  test/test_pipeline.py::TestRunner::testStepWithoutScript \
  test/test_pipeline.py::TestRunner::testStepsDict \
  test/test_pipeline.py::TestRunner::testStepsMustBeAList \
  test/test_pipeline.py::TestRunner::testTaskScheduleTime \
  test/test_pipeline.py::TestRunner::testTasksFollowingSchedule; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
