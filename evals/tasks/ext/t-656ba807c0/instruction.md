[FEATURE] Make DS algorithm takes the information from gold standard questions
### Problem description

In the real world, when doing truth inference, we have a small set of gold standard questions mixed in with other unlabeled questions. I thought it would help if we could use the true labels of these gold standard questions to adjust the estimation of the user confusion matrix and the prior distribution of the options.

### Feature description

Make ds algorithm accept an optional argument, `gt` for example, which can be used to adjust the estimation of user's confusion matrix and the priori distribution of options.

### Potential alternatives

_No response_

### Papers connected with feature

_No response_

### Additional information

This feature may make the EM process in DS more complicated if we add the argument and make some changes directly on the original implementation. Maybe there are better ways to do this?
