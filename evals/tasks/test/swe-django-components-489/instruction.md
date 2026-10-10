template_loader blocks on STATICFILES_DIRS if there are tuples
## How to reproduce

Simply run django with, in your _settings.py_, something like :
```
STATICFILES_DIRS = [
    # ...
    ("downloads", "/opt/webfiles/stats"),
]
```

(as made possible [natively in Django](https://docs.djangoproject.com/en/3.2/ref/settings/#std-setting-STATICFILES_DIRS))

## Current behaviour

Getting `TypeError: expected str, bytes or os.PathLike object, not tuple` given [this line] (https://github.com/EmilStenstrom/django-components/blob/e566d8ecbb7016cf3a8861a47a4a52e4a503b838/src/django_components/template_loader.py#L49) 


## Expected

`class Loader` from _src/django_components/template_loader.py_ should consider the second item of STATICFILES_DIRS list item when not a str.

## Furthermore

Thank you a lot, sir, for this django library. It helped us, a French news company, a lot to center our codebase almost fully on Django.
I might try to suggest a clean PR for this
