Tests in test_angle.py aren't being ran
I don't think the tests in stonesoup/types/test/test_angle.py are being ran. They aren't running for me locally and I can't see the test results in junit files ([recent example](https://circleci-tasks-prod.s3.us-east-1.amazonaws.com/storage/artifacts/d67db25e-036c-4c24-b454-b7cd79f21f70/2d6a1833-ce1d-4d33-ac90-e10421312792/0/test-reports/junit.xml?[已移除签名链接])).

Maybe there is an issue with the function [`pytest_generate_tests`]([链接已移除])
