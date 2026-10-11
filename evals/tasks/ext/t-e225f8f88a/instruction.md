Billions followed by millions (e.g. 1,025,000,000) not converted for English, French
When the next multiplier is a million, following billions, it is not handled correctly. It is not detected as an expected valid multiplier. There is a "TODO" comment in the related code, I suspect it is about this issue.

It doesn't happen with Spanish because in Spanish billion is basically "thousand millions". 

If the next multiplier following billions is a thousand, it works fine, because 1000x1000=1,000,000 < 1 billion.

For now, I add the following check to the end of `is_coef_appliable()` method, before returning False, it works fine for me now:

```
        if coef > self.grp_val and coef * self.grp_val < self.n000_val:
            return True

```
It seems reasonable to me, but I may not be able to consider all possible cases, and for different languages. Just a suggestion for the time being.
