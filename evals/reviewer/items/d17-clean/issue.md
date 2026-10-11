Better handling of when a branch already exists
Currently, in `github_resolver/send_pull_request.py`, when pushing to github for a particular issue, the branch name is fixed here:
https://github.com/All-Hands-AI/openhands-resolver/blob/44aa2907d70852b7f98786c673304cc18b76d43e/openhands_resolver/send_pull_request.py#L162

However, if the github resolver has already tried to solve the issue and failed, the branch may already exist. Because of this, it would be better to check if the branch already exists, and if it does, further append `-try2`, `-try3`, until it finds a branch that doesn't exist.
