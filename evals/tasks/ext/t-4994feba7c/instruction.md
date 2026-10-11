Jensen model has odd power value
**Bug description**
Working on an example script I noticed that some turbines in a farm returned oddly low power levels

**To Reproduce**
Here is an example script to reproduce the behavior, notice one of the turbines produces much less power than the rest.  This is not consistent with the other wake models:
```
import numpy as np
import matplotlib.pyplot as plt
from floris.tools import FlorisInterface

fi = FlorisInterface("inputs/jensen.yaml")

# Make a 25 turbine farm
# Get number of turbines and make 0 yaw angle matrix
N = 5
yaw_angles = np.zeros((1, 1, N**2)) # 1 wd/ 1ws/ N*N turbines


# Define layout
X, Y = np.meshgrid(
    6 * fi.floris.turbine.rotor_diameter * np.arange(0, N, 1),
    6 * fi.floris.turbine.rotor_diameter * np.arange(0, N, 1),
)
X = X.flatten()
Y = Y.flatten()

fi.reinitialize( layout=( X, Y ), wind_speeds=[8.0], wind_directions=[285.], turbulence_intensity=0.06 )
fi.calculate_wake(yaw_angles)
print(fi.get_turbine_powers()/1000.)

plt.plot(fi.get_turbine_powers().flatten()/1000.)
plt.show()
```

**Expected behavior**
This pattern of turbine outputs doesn't make sense to me

**Screenshots, if applicable**
![image](https://user-images.githubusercontent.com/6117702/153516724-7590a49f-3075-45e9-b8aa-1c3d8dfd1102.png)


**Floris Version**
v3.0

**System Information (please complete the following information):** 
 - OS: mac
