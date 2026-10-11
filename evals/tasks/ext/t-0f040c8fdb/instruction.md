[textual][bug] CSS rule parsing fails when the name of the colour we pass contains a digit
So while this is working correctly:
```css
#my_widget {
  background: dark_cyan;
}
```

...this fails:
```css
#my_widget {
  background: turquoise4;
}
```
...with the following error:
```
 • failed to parse color 'turquoise';                                                                                                                                         
 • failed to parse 'turquoise' as a color;  
```
(maybe just a regex that doesn't take into account the fact that colour names can include numbers?)
