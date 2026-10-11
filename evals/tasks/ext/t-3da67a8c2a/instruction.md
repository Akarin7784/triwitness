AppriseLocale.py TypeError: 'NoneType' object has no attribute '__getitem__'
An system without any universal language identifier existing in it's environment at all causes an unhanded exception:
```python
  File "/usr/lib/python2.7/site-packages/apprise/Apprise.py", line 78, in __init__
    self.locale = AppriseLocale()
  File "/usr/lib/python2.7/site-packages/apprise/AppriseLocale.py", line 111, in __init__
    self.lang = AppriseLocale.detect_language(language)
  File "/usr/lib/python2.7/site-packages/apprise/AppriseLocale.py", line 207, in detect_language
    return lang[0:2].lower()
TypeError: 'NoneType' object has no attribute '__getitem__'
```

This was identified [here](https://github.com/linuxserver/docker-lazylibrarian/issues/30).
