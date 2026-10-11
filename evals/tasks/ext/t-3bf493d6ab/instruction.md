mb_artistid and mb_albumartistid should be lists
Hey!
When trying to fix my PR (#42) I found error I can't fix myself.

`mb_artistid` and `mb_albumartistid` should be lists!
`mediafile`'s version:
```python
>>> mf = MediaFile('/home/juniorjpdj/temp/Szpadyzor crew.flac')
>>> mf.mb_artistid
'164ed128-525d-4798-883f-be13502de86b'
>>> mf.mb_albumartistid
'164ed128-525d-4798-883f-be13502de86b'
```

Picard is tagging it like that (mutagen dump):
FLAC:  `'musicbrainz_artistid': ['164ed128-525d-4798-883f-be13502de86b', 'ded6b91b-26d8-4bc0-8aa9-fab9b54cd157'],`
MP3 (ID3v2.3): ` 'TXXX:MusicBrainz Artist Id': TXXX(encoding=<Encoding.UTF16: 1>, desc='MusicBrainz Artist Id', text=['ca780457-5bf6-4a7d-95fa-0d0d4920f26f/258a67d1-172d-4d16-8d6c-09efde60896f/af262d86-542d-4864-8527-083065166d6c']),`

Fixing FLAC parsing is easy I can't make it work in MP3 case.

Current code is returning only the first author in case of FLAC and `'/'` separated string in case of MP3.

Helping fixing this will also help me solve some problems with #42 ;D
