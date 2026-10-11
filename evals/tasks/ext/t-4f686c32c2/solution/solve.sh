#!/usr/bin/env bash
# gold patch 之后的完整文件
set -euo pipefail
cd /workspace/repo
mkdir -p h_transport_materials
cat > h_transport_materials/plotting.py <<'TW_EOF'
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import ArrayLike
import pint
from h_transport_materials import Property, PropertiesGroup, ureg
import math
import matplotlib as mpl
from typing import Union


def plot(
    prop: Union[Property, PropertiesGroup],
    T_bounds=(300, 1200),
    inverse_temperature=True,
    auto_label=True,
    **kwargs
):
    """Plots a Property object on a temperature plot

    Args:
        prop (Property or PropertiesGroup): the property (or group of properties)
            to plot.
        T_bounds (tuple, optional): If the property doesn't have
            a temperature range, this range will be used. Defaults
            to (300, 1200).
        inverse_temperature (bool, optional): If True, the x axis
            will be the inverse temperature (in K^-1). Defaults to True.
        auto_label (bool, optional): If True, a label will be automatically
            generated from the isotope, author and year. Ignored if label is set in kwargs.
            Defaults to True.
        kwargs: other matplotlib.pyplot.plot arguments
    Returns:
        matplotlib.lines.Line2D: the Line2D artist
    """
    if isinstance(prop, Property):
        if prop.range is None:
            range = T_bounds
        else:
            range = prop.range
        T = np.linspace(*range, num=50)
        if not isinstance(T, pint.Quantity):
            T *= ureg.K
        if inverse_temperature:
            plt.xlabel("1/T (K$^{-1}$)")
            x = (1 / T)[::-1]
            y = prop.value(T)[::-1]
        else:
            plt.xlabel("T (K)")
            x = T
            y = prop.value(T)

        if auto_label and "label" not in kwargs.keys():
            label = "{} {} ({})".format(
                prop.isotope, prop.author.capitalize(), prop.year
            )
            kwargs["label"] = label

        return plt.plot(x, y, **kwargs)
    elif isinstance(prop, PropertiesGroup):
        for prop2 in prop:
            plot(
                prop2,
                T_bounds=T_bounds,
                inverse_temperature=inverse_temperature,
                auto_label=auto_label,
                **kwargs
            )


def line_labels(
    ax=None,
    min_label_distance: float or str = "auto",
    alpha: float = 1.0,
    **text_kwargs
):
    """Adapted from matplotx"""
    ax = ax or plt.gca()

    logy = ax.get_yscale() == "log"
    logx = ax.get_xscale() == "log"

    if min_label_distance == "auto":
        # Make sure that the distance is alpha * fontsize. This needs to be translated
        # into axes units.
        fig = plt.gcf()
        fig_height_inches = fig.get_size_inches()[1]
        ax = plt.gca()
        ax_pos = ax.get_position()
        ax_height = ax_pos.y1 - ax_pos.y0
        ax_height_inches = ax_height * fig_height_inches
        ylim = ax.get_ylim()
        if logy:
            ax_height_ylim = math.log10(ylim[1]) - math.log10(ylim[0])
        else:
            ax_height_ylim = ylim[1] - ylim[0]
        # 1 pt = 1/72 in
        fontsize = mpl.rcParams["font.size"]
        assert fontsize is not None
        min_label_distance_inches = fontsize / 72 * alpha
        min_label_distance = (
            min_label_distance_inches / ax_height_inches * ax_height_ylim
        )

    # find all Line2D objects with a valid label and valid data
    lines = [
        child
        for child in ax.get_children()
        # https://stackoverflow.com/q/64358117/353337
        if (
            isinstance(child, mpl.lines.Line2D)
            and child.get_label()[0] != "_"
            and not np.all(np.isnan(child.get_ydata()))
        )
    ]

    if len(lines) == 0:
        return

    # Add "legend" entries.
    # Get last non-nan y-value.
    targets, targets_x = [], []
    for line in lines:
        ydata = line.get_ydata()
        xdata = line.get_xdata()
        targets.append(ydata[~np.isnan(ydata)][-1])
        targets_x.append(xdata[~np.isnan(xdata)][-1])

    if logy:
        targets = [math.log10(t) for t in targets]

    if logx:
        targets_x = [math.log10(t) for t in targets_x]

    # Sometimes, the max value if beyond ymax. It'd be cool if in this case we could put
    # the label above the graph (instead of the to the right), but for now let's just
    # cap the target y.
    ymax = ax.get_ylim()[1]
    targets = [min(target, ymax) for target in targets]

    targets = _move_min_distance(targets, min_label_distance)
    if logy:
        targets = [10**t for t in targets]
    # if logx:
    #     targets_x = [10**t for t in targets_x]

    labels = [line.get_label() for line in lines]
    colors = [line.get_color() for line in lines]

    # Leave the labels some space to breathe. If they are too close to the
    # lines, they can get visually merged.
    # <https://twitter.com/EdwardTufte/status/1416035189843714050>
    # Don't forget to transform to axis coordinates first. This makes sure the
    # https://stackoverflow.com/a/40475221/353337
    # axis_to_data = ax.transAxes + ax.transData.inverted()
    # xpos = axis_to_data.transform([1.03, 1.0])[0]
    for label, xpos, ypos, color in zip(labels, targets_x, targets, colors):
        plt.text(
            xpos, ypos, label, verticalalignment="center", color=color, **text_kwargs
        )


def _move_min_distance(targets: ArrayLike, min_distance: float) -> np.ndarray:
    """Move the targets such that they are close to their original positions, but keep
    min_distance apart.
    https://math.stackexchange.com/a/3705240/36678
    """
    # sort targets
    idx = np.argsort(targets)
    targets = np.sort(targets)

    n = len(targets)
    x0_min = targets[0] - n * min_distance
    A = np.tril(np.ones([n, n]))
    b = targets - (x0_min + np.arange(n) * min_distance)

    # import scipy.optimize
    # out, _ = scipy.optimize.nnls(A, b)

    out = nnls(A, b)

    sol = np.cumsum(out) + x0_min + np.arange(n) * min_distance

    # reorder
    idx2 = np.argsort(idx)
    return sol[idx2]


def nnls(A, b, eps: float = 1.0e-10, max_steps: int = 100):
    # non-negative least-squares after
    # <https://en.wikipedia.org/wiki/Non-negative_least_squares>
    A = np.asarray(A)
    b = np.asarray(b)

    AtA = A.T @ A
    Atb = A.T @ b

    m, n = A.shape
    assert m == b.shape[0]
    mask = np.zeros(n, dtype=bool)
    x = np.zeros(n)
    w = Atb
    s = np.zeros(n)
    k = 0
    while sum(mask) != n and max(w) > eps:
        if k >= max_steps:
            break
        mask[np.argmax(w)] = True

        s[mask] = np.linalg.lstsq(AtA[mask][:, mask], Atb[mask], rcond=None)[0]
        s[~mask] = 0.0

        while np.min(s[mask]) <= 0:
            alpha = np.min(x[mask] / (x[mask] - s[mask]))
            x += alpha * (s - x)
            mask[np.abs(x) < eps] = False

            s[mask] = np.linalg.lstsq(AtA[mask][:, mask], Atb[mask], rcond=None)[0]
            s[~mask] = 0.0

        x = s.copy()
        w = Atb - AtA @ x

        k += 1

    return x
TW_EOF
mkdir -p h_transport_materials
cat > h_transport_materials/properties_group.py <<'TW_EOF'
import numpy as np
import json
from pybtex.database import BibliographyData
import pint

from h_transport_materials.fitting import fit_arhenius
from h_transport_materials import ureg


class PropertiesGroup(list):
    @property
    def bibdata(self):
        bibdata = {}

        for prop in self:
            if prop.bibsource is None:
                print("{} is not a bibsource".format(prop.source))
                continue
            key = prop.bibsource.key
            bibdata[key] = prop.bibsource

        return BibliographyData(bibdata)

    def filter(self, exclude=False, **kwargs):
        """Returns properties that match the specified arguments.
        Usage:
        ```
        group = htm.diffusivities

        # filter tungsten and authors esteban or heinola
        filtered_props = group.filter(material="tungsten").filter(author=["esteban", "heinola"])

        # exclude isotope T
        filtered_props = filtered_props.filter(exclude=True, isotope="T")

        property = filtered_props[0]
        ```

        Args:
            exclude (bool, optional): if True, the searched
                keys will be excluded. Defaults to False.
            kwargs: attributes of properties (ex: material="tungsten").
                String values must be lowercase to ensure good comparison.

        Returns:
            PropertiesGroup: the resulting properties
        """
        filtered_props = PropertiesGroup()

        # iterate through properties
        for prop in self:
            match = True
            for attr, value in kwargs.items():
                prop_attr = getattr(prop, attr)

                if isinstance(prop_attr, str):
                    # make sure prop_attr are lower
                    prop_attr = prop_attr.lower()

                if isinstance(value, list):
                    if prop_attr not in value:
                        match = False
                elif prop_attr != value:
                    match = False

            # append the property to the filtered list
            if (match and not exclude) or (not match and exclude):
                filtered_props.append(prop)

        return filtered_props

    def mean(self, samples_per_line=5, default_range=(300, 1200)):
        """Fits all the data and returns the mean pre-exponential
        factor and activation energy.

        Args:
            samples_per_line (int, optional): number of points taken
                per Property if it doesn't have any data. Defaults to 5.
            default_range (tuple, optional): temperature range taken if
                a Property doesn't have range. Defaults to (300, 1200).

        Returns:
            float, float: pre-exponential factor, activation energy (eV)
        """
        # initialise data points
        data_T = np.array([])
        data_y = np.array([])

        # add data points
        for prop in self:
            # if the property has data points, use them
            if prop.data_T is not None:
                prop_T = prop.data_T
                prop_y = prop.data_y
            # else, take samples
            else:
                T_range = prop.range
                if prop.range == None:
                    T_range = default_range
                prop_T = np.linspace(T_range[0], T_range[1], num=samples_per_line)
                if not isinstance(prop_T, pint.Quantity):
                    prop_T = ureg.Quantity(prop_T, ureg.K)
                prop_y = prop.value(prop_T)

            data_T = np.concatenate((data_T, prop_T))
            data_y = np.concatenate((data_y, prop_y))

        # fit all the data
        pre_exp, act_energy = fit_arhenius(data_y, data_T)
        return pre_exp, act_energy

    def export_bib(self, filename: str):
        """Exports the bibliography data

        Args:
            filename (str): the path of the exported file
        """

        self.bibdata.to_file(filename)

    def export_to_json(self, filename: str):
        keys = [
            "material",
            "pre_exp",
            "act_energy",
            "isotope",
            "author",
            "source",
            "range",
            "doi",
            "units",
        ]

        data = []
        for prop in self:

            prop_dict = {key: getattr(prop, key) for key in keys if hasattr(prop, key)}
            if "units" in prop_dict:
                prop_dict["units"] = f"{prop_dict['units']:~}"
            data.append(prop_dict)

        with open(filename, "w") as outfile:
            json.dump(data, outfile, indent=4)
TW_EOF
mkdir -p h_transport_materials
cat > h_transport_materials/property.py <<'TW_EOF'
from collections.abc import Iterable
import numpy as np
from crossref.restful import Works, Etiquette
import pint
from pybtex.database import BibliographyData, parse_string
from h_transport_materials import k_B, bib_database, ureg
from h_transport_materials.fitting import fit_arhenius

import warnings

DEFAULT_ENERGY_UNITS = ureg.eV * ureg.particle**-1


class Property:
    def __init__(
        self,
        material: str = "",
        source: str = "",
        name: str = "",
        range: tuple = None,
        year: int = None,
        isotope: str = None,
        author: str = "",
        note: str = None,
    ) -> None:
        """Inits Property

        Args:
            material (str, optional): name of the material. Defaults to "".
            source (str, optional): bibliographic reference. Defaults to "".
            name (str, optional): name of the property. Defaults to "".
            range (tuple, optional): temperature validity range in K.
                Defaults to None.
            year (int, optional): year of publication. Defaults to None.
            isotope (str, optional): isotope of the property ("H", "D" or "T").
                Defaults to None.
            author (str, optional): name of the author. Defaults to "".
            note (str, optional): additional information. Defaults to None.
        """

        self.material = material
        self.source = source
        self.name = name
        self.range = range
        self.isotope = isotope
        self.note = note

        self.nb_citations = None

        # make bibsource
        if source in bib_database.entries:
            self.bibsource = bib_database.entries[source]
        elif self.source.startswith("@"):
            self.bibsource = list(
                parse_string(self.source, bib_format="bibtex").entries.values()
            )[0]
        else:
            self.bibsource = None

        # try get year and author from bibsource
        if self.bibsource:
            self.year = int(self.bibsource.fields["year"])
            if year is not None:
                warnings.warn(
                    "year argument will be ignored since a bib source was found"
                )
            self.author = self.bibsource.persons["author"][0].last_names[0].lower()
            if author != "":
                warnings.warn(
                    "author argument will be ignored since a bib source was found"
                )
        else:
            self.author = author
            self.year = year

    @property
    def bibdata(self):
        if self.bibsource is None:
            raise ValueError("No bibsource found")

        bibdata = {self.bibsource.key: self.bibsource}
        return BibliographyData(bibdata)

    @property
    def range(self):
        return self._range

    @range.setter
    def range(self, value):
        if value:
            if not isinstance(value, Iterable):
                raise TypeError("range should be an iterable containing two values")
            if len(value) != 2:
                raise TypeError("range should be an iterable containing two values")

            if value[0] <= 0 or value[1] <= 0:
                raise ValueError("temperature range must be stricly positive (Kelvin)")

        self._range = value

    @property
    def doi(self):
        self._doi = None
        if self.bibsource:
            if "doi" in self.bibsource.fields:
                self._doi = self.bibsource.fields["doi"]

        return self._doi

    @doi.setter
    def doi(self, value):
        self._doi = value

    @property
    def nb_citations(self):
        # if nb_citations doesn't already exist, compute it
        if self._nb_citations is None:
            if self.bibsource is None:
                self.nb_citations = 0
            elif self.doi:
                self.nb_citations = get_nb_citations(self.doi)
            else:
                self.nb_citations = 0
        return self._nb_citations

    @nb_citations.setter
    def nb_citations(self, value):
        self._nb_citations = value

    def export_bib(self, filename: str):
        """Exports the property reference to bib

        Args:
            filename (str): the filename

        Raises:
            ValueError: if the property bibsource attribute is None
        """

        self.bibdata.to_file(filename)

    def value(self, T):
        pass


class ArrheniusProperty(Property):
    def __init__(
        self,
        pre_exp: float = None,
        act_energy: float = None,
        data_T: list = None,
        data_y: list = None,
        **kwargs,
    ) -> None:
        """Inits ArrheniusProperty
        property = pre_exp * exp( - act_energy/(k_B T) )

        Args:
            pre_exp (float or pint.Quantity, optional): the pre-exponential factor. Defaults to None.
            act_energy (float or pint.Quantity, optional): the activation energy. Defaults to None.
            data_T (list, optional): list of temperatures in K. Used to automatically
                fit experimental points. Defaults to None.
            data_y (list, optional): list of y data. Used to automatically
                fit experimental points. Defaults to None.
            kwargs: other Property arguments
        """
        self.pre_exp = pre_exp
        self.act_energy = act_energy
        self.data_T = data_T
        self.data_y = data_y
        super().__init__(**kwargs)

    def __str__(self) -> str:
        val = f"""
        Author: {self.author.capitalize()}
        Material: {self.material}
        Year: {self.year}
        Isotope: {self.isotope}
        Pre-exponential factor: {self.pre_exp}
        Activation energy: {self.act_energy} eV
        """
        return val

    @property
    def units(self):
        return ureg.dimensionless

    @property
    def range(self):
        if self._range is None and self.data_T is not None:
            self.fit()
        return self._range

    @range.setter
    def range(self, value):
        self._range = value

    @property
    def pre_exp(self):
        if self._pre_exp is None and self.data_T is not None:
            self.fit()
        return self._pre_exp

    @pre_exp.setter
    def pre_exp(self, value):
        if isinstance(value, pint.Quantity):
            if self.units != ureg.dimensionless:
                self._pre_exp = value.to(self.units).magnitude
            else:
                self._pre_exp = value.magnitude

        elif value is not None:
            # assume it's given in the correct units
            warnings.warn(
                f"no units were given with pre-exponential factor, assuming {self.units:~}"
            )
            self._pre_exp = value
        else:
            self._pre_exp = value

    @property
    def act_energy(self):
        if self._act_energy is None and self.data_T is not None:
            self.fit()
        return self._act_energy

    @act_energy.setter
    def act_energy(self, value):
        if isinstance(value, pint.Quantity):
            self._act_energy = value.to(DEFAULT_ENERGY_UNITS).magnitude
        elif value is not None:
            # assume it's given in DEFAULT_ENERGY_UNITS
            warnings.warn(
                f"no units were given with activation energy, assuming {DEFAULT_ENERGY_UNITS:~}"
            )
            self._act_energy = value
        else:
            self._act_energy = value

    @property
    def data_T(self):
        return self._data_T

    @data_T.setter
    def data_T(self, value):
        if value is None:
            self._data_T = value
            return
        if isinstance(value, pint.Quantity):
            # convert to K
            value = value.to(ureg.K).magnitude
        else:
            warnings.warn(f"no units were given with data_T, assuming {self.units:~}")
        if not isinstance(value, (list, np.ndarray)):
            raise TypeError("data_T accepts list or np.ndarray")
        elif isinstance(value, list):
            value_as_array = np.array(value)
            self._data_T = value_as_array[
                ~np.isnan(value_as_array)
            ]  # remove nan values
        else:
            self._data_T = value[~np.isnan(value)]

    @property
    def data_y(self):
        return self._data_y

    @data_y.setter
    def data_y(self, value):
        if value is None:
            self._data_y = value
            return
        if isinstance(value, pint.Quantity):
            # convert to right units
            if self.units != ureg.dimensionless:
                value = value.to(self.units).magnitude
            else:
                value = value.magnitude
        else:
            warnings.warn(f"no units were given with data_y, assuming {self.units:~}")
        if not isinstance(value, (list, np.ndarray)):
            raise TypeError("data_y accepts list or np.ndarray")
        elif isinstance(value, list):
            value_as_array = np.array(value)
            self._data_y = value_as_array[
                ~np.isnan(value_as_array)
            ]  # remove nan values
        else:
            self._data_y = value[~np.isnan(value)]

    def fit(self):
        pre_exp, act_energy = fit_arhenius(self.data_y, self.data_T)
        self.pre_exp, self.act_energy = (
            pre_exp * self.units,
            act_energy * DEFAULT_ENERGY_UNITS,
        )
        self.range = (self.data_T.min(), self.data_T.max())

    def value(self, T, exp=np.exp):
        if not isinstance(T, pint.Quantity):
            warnings.warn(f"no units were given with T, assuming {ureg.K}")
            T = T * ureg.K
        if not isinstance(self.pre_exp, pint.Quantity):
            pre_exp = self.pre_exp * self.units
        if not isinstance(self.act_energy, pint.Quantity):
            act_energy = self.act_energy * DEFAULT_ENERGY_UNITS
        k_B_u = k_B * ureg.eV * ureg.particle**-1 * ureg.K**-1
        return pre_exp * exp(-act_energy / k_B_u / T)


class Solubility(ArrheniusProperty):
    """Solubility class

    Args:
        units (str): units of the solubility "m-3 Pa-1/2" or "m-3 Pa-1".
        S_0 (float or pint.Quantity, optional): pre-exponential factor. Defaults to None.
        E_S (float or pint.Quantity, optional): activation energy. Defaults to None.
    """

    def __init__(
        self, units: str, S_0: float = None, E_S: float = None, **kwargs
    ) -> None:
        self.units = units
        super().__init__(pre_exp=S_0, act_energy=E_S, **kwargs)

    @property
    def units(self):
        return self._units

    @units.setter
    def units(self, value):
        acceptable_units = ["m-3 Pa-1/2", "m-3 Pa-1"]
        if value == "m-3 Pa-1/2":
            self._units = ureg.particle * ureg.meter**-3 * ureg.Pa**-0.5
        elif value == "m-3 Pa-1":
            self._units = ureg.particle * ureg.meter**-3 * ureg.Pa**-1
        else:
            raise ValueError("units can only accept {} or {}".format(*acceptable_units))

    def __str__(self) -> str:
        val = f"""
        Author: {self.author.capitalize()}
        Material: {self.material}
        Year: {self.year}
        Isotope: {self.isotope}
        Pre-exponential factor: {self.pre_exp} {self.units:~}
        Activation energy: {self.act_energy} eV
        """
        return val


class Diffusivity(ArrheniusProperty):
    """Diffusivity class

    Args:
        D_0 (float or pint.Quantity, optional): pre-exponential factor. Defaults to None.
        E_D (float or pint.Quantity, optional): activation energy. Defaults to None.
    """

    def __init__(self, D_0: float = None, E_D: float = None, **kwargs) -> None:
        super().__init__(pre_exp=D_0, act_energy=E_D, **kwargs)

    def __str__(self) -> str:
        val = f"""
        Author: {self.author.capitalize()}
        Material: {self.material}
        Year: {self.year}
        Isotope: {self.isotope}
        Pre-exponential factor: {self.pre_exp} {self.units:~}
        Activation energy: {self.act_energy} eV
        """
        return val

    @property
    def units(self):
        return ureg.meter**2 * ureg.second**-1


class Permeability(ArrheniusProperty):
    """Permeability class"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def __str__(self) -> str:
        val = f"""
        Author: {self.author.capitalize()}
        Material: {self.material}
        Year: {self.year}
        Isotope: {self.isotope}
        Pre-exponential factor: {self.pre_exp} {self.units:~}
        Activation energy: {self.act_energy} eV
        """
        return val

    @property
    def units(self):
        return ureg.particle * ureg.meter**-1 * ureg.second**-1 * ureg.Pa**-0.5


class RecombinationCoeff(ArrheniusProperty):
    """RecombinationCoeff class"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def __str__(self) -> str:
        val = f"""
        Author: {self.author.capitalize()}
        Material: {self.material}
        Year: {self.year}
        Isotope: {self.isotope}
        Pre-exponential factor: {self.pre_exp} {self.units:~}
        Activation energy: {self.act_energy} eV
        """
        return val

    @property
    def units(self):
        return ureg.meter**4 * ureg.second**-1


class DissociationCoeff(ArrheniusProperty):
    """DissociationCoeff class"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def __str__(self) -> str:
        val = f"""
        Author: {self.author.capitalize()}
        Material: {self.material}
        Year: {self.year}
        Isotope: {self.isotope}
        Pre-exponential factor: {self.pre_exp} {self.units:~}
        Activation energy: {self.act_energy} eV
        """
        return val

    @property
    def units(self):
        return ureg.meter**-3 * ureg.Pa**-1


def get_nb_citations(doi: str):
    """Returns the number of citations of a given doi in the crossref database

    Args:
        doi (str): the DOI of the source

    Returns:
        int: the number of citations according to crossref
    """
    record = works.doi(doi)
    if record:
        nb_citations = record["is-referenced-by-count"]
    else:
        nb_citations = 0
    return nb_citations


my_etiquette = Etiquette(
    "H-transport-materials",
    "latest",
    "https://github.com/RemDelaporteMathurin/h-transport-materials",
    "rdelaportemathurin@gmail.com",
)

works = Works(etiquette=my_etiquette)
TW_EOF
