Encode URLs in redirect responses
* **I'm submitting a ...**
[x] bug report
[ ] feature request
[ ] question about the decisions made in the repository

* **What is the current behavior?**
The standard response page for 30x errors contains the target URL as `href` as well as clear text.

* **What is the expected behavior?**
Even though browsers *mostly* will not display the result, but redirect instead, you never know:
Any input from unknown sources should be html-escaped.

* **Please tell us about your environment:**
CherryPy 3.8 until 10.1
