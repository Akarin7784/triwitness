Issues with parshing PASHR sentences
Hi,

Just ran into some troubles when trying to parse an NMEA stream containing PASHR sentences, like below:
```
$PASHR,122144.75,240.68,T,,,,,,,2*04
$PASHR,122144.96,240.30,T,,,,,,,2*04
$PASHR,122145.18,239.91,T,,,,,,,2*06
$PASHR,122145.61,239.04,T,,,,,,,2*04
$PASHR,122145.83,238.59,T,,,,,,,2*01
$PASHR,122146.05,238.13,T,,,,,,,2*02
```

Seems like the special logic for these messages (see [here](https://github.com/Knio/pynmea2/blob/master/pynmea2/types/proprietary/ash.py#L24-L26) and [here](https://github.com/Knio/pynmea2/blob/master/pynmea2/types/proprietary/ash.py#L35-L37)) does not fit the messages that I have. 

The regex in the the last link is not catching the messages due to different number of decimal values in the timestamp. I.e. `122144.75` does not give a match with `'^\d{6}\.\d{3}$'`. Changing the regex to `'^\d{6}\.\d{2,3}$'` seems to do the trick.
