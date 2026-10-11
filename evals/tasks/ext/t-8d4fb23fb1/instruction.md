boundary_width in snow2 breaks when trying to specify padding on both ends of all axes
This works:
`b = ps.networks.snow2(im, boundary_width=[[5, 15], 10])`

This breaks:
`b = ps.networks.snow2(im, boundary_width=[[5, 15], [10, 10]])`

The complaint is coming from `np.pad`: `TypeError: `pad_width` must be of integral type.`
