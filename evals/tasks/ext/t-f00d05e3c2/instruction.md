Issue with PostUpdate and <1MB mp4 media files
When trying post an update using the following code:
```python
api = twitter.Api(options)
api.VerifyCredentials()
api.PostUpdate('My status', media='/my/local/file.mp4')
```
Twitter would respond with the error 'media type unrecognized'.  The call worked sometimes but not always but I was finally able to narrow down the issue to the size of the mp4 file. While searching for the error message I found this http://stackoverflow.com/a/32250580.  According to the author if the upload is a video file (mp4) it must always be uploaded via the chunked upload API endpoint.  I was unable to verify this in the Twitter API docs (like here: https://dev.twitter.com/rest/media/uploading-media.html) but once I added a smaller chunk_size to my init (chunk_size=1024*16) all PostUpdate calls worked as expected. This (to me) is a dirty fix but it works for me and it should work for anyone else with a similar issue.

The question is should the library here be updated to automatically reduce the chunk size when uploading mp4 files?  I am not sure as I was unable to find any other information in the Twitter docs as to this mp4 chunked upload only restriction. But if the linked article is correct there should probably be some logic added into the PostUpdate code that would take into account if the video file is < 1MB in size.
