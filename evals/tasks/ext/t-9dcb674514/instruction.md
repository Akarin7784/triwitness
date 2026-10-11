Attaching Images - Decode required for Python 3 compatibility
When attaching an image from a local file:

```
with open("some_image.jpg","rb") as f:
    img = f.read()
    image1.attach_image(data=img)
```

img will be bytes while the attachment needs to be a string to the JSONified. So in image.py:

```
def attach_image(self, data, filename=None):
    self.attributes["attachment"] = base64.b64encode(data).decode() #decode() for Python 3
    if filename:
        self.attributes["filename"] = filename
```

I am not sure how to keep it Python 2 compatible.
