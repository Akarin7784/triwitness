.value() method should work with units
Users should be able to do:

```python
import h_transport_materials as htm

ureg = htm.ureg

T = ureg.Quantity(900, ureg.K)

D = htm.Diffusivity(1 * ureg.m**2 * ureg.s**-1, 0.1 * ureg.eV)

value = D.value(T)

value.to(ureg.mm**2 * ureg.s**-1)
```

- .value() should return a pint.Quantity object
- .value() should accept a pint.Quantity object for argument
