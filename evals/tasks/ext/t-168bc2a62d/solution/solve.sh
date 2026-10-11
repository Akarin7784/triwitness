#!/usr/bin/env bash
# gold patch 之后的完整文件
set -euo pipefail
cd /workspace/repo
mkdir -p pycytominer/cyto_utils
cat > pycytominer/cyto_utils/features.py <<'TW_EOF'
"""
Utility function to manipulate cell profiler features
"""

import os
import pandas as pd

blocklist_file = os.path.join(
    os.path.dirname(__file__), "..", "data", "blocklist_features.txt"
)


def get_blocklist_features(blocklist_file=blocklist_file, population_df=None):
    """Get a list of blocklist features.

    Parameters
    ----------
    blocklist_file : path-like object
        Location of the dataframe with features to exclude.
    population_df : pandas.core.frame.DataFrame, optional
        Profile dataframe used to subset blocklist features.

    Returns
    -------
    blocklist_features : list of str
        Features to exclude from downstream analysis.
    """

    blocklist = pd.read_csv(blocklist_file)

    assert any(
        [x == "blocklist" for x in blocklist.columns]
    ), "one column must be named 'blocklist'"

    blocklist_features = blocklist.blocklist.to_list()
    if isinstance(population_df, pd.DataFrame):
        population_features = population_df.columns.tolist()
        blocklist_features = [x for x in blocklist_features if x in population_features]

    return blocklist_features


def label_compartment(cp_features, compartment, metadata_cols):
    """Assign compartment label to each features as a prefix.

    Parameters
    ----------
    cp_features : list of str
        All features being used.
    compartment : str
       Measured compartment.
    metadata_cols : list
        Columns that should be considered metadata.

    Returns
    -------
    cp_features: list of str
        Recoded column names with appropriate metadata and compartment labels.
    """

    compartment = compartment.Title()
    avail_compartments = ["Cells", "Cytoplasm", "Nuceli", "Image", "Barcode"]

    assert (
        compartment in avail_compartments
    ), "provide valid compartment. One of: {}".format(avail_compartments)

    cp_features = [
        "Metadata_{}".format(x)
        if x in metadata_cols
        else "{}_{}".format(compartment, x)
        for x in cp_features
    ]

    return cp_features


def infer_cp_features(
    population_df,
    compartments=["Cells", "Nuclei", "Cytoplasm"],
    metadata=False,
    image_features=False,
):
    """Given a dataframe, output features that we expect to be Cell Painting features.

    Parameters
    ----------
    population_df : pandas.core.frame.DataFrame
        DataFrame from which features are to be inferred.
    compartments : list of str, default ["Cells", "Nuclei", "Cytoplasm"]
        Compartments from which Cell Painting features were extracted.
    metadata : bool, default False
        Whether or not to infer metadata features.
    image_features : bool, default False
        Whether or not the profiles contain image features.

    Returns
    -------
    features: list of str
        List of Cell Painting features.
    """

    compartments = convert_compartment_format_to_list(compartments)
    compartments = [x.title() for x in compartments]

    if image_features:
        compartments = list(set(["Image"] + compartments))

    features = []
    for col in population_df.columns.tolist():
        if any([col.startswith(x.title()) for x in compartments]):
            features.append(col)

    if metadata:
        features = population_df.columns[
            population_df.columns.str.startswith("Metadata_")
        ].tolist()

    assert (
        len(features) > 0
    ), "No CP features found. Are you sure this dataframe is from CellProfiler?"

    return features


def count_na_features(population_df, features):
    """Given a population dataframe and features, count how many nas per feature.

    Parameters
    ----------
    population_df : pandas.core.frame.DataFrame
        DataFrame of profiles.
    features : list of str
        Features present in the population dataframe.

    Returns
    -------
    Dataframe of NA counts per feature
    """

    return pd.DataFrame(population_df.loc[:, features].isna().sum(), columns=["num_na"])


def drop_outlier_features(
    population_df, features="infer", samples="all", outlier_cutoff=500
):
    """Exclude a feature if its min or max absolute value is greater than the threshold.

    Parameters
    ----------
    population_df : pandas.core.frame.DataFrame
        DataFrame that includes metadata and observation features.
    features : list of str or str, default "infer"
        Features present in the population dataframe. If "infer", then assume Cell Painting features are those that start with "Cells_", "Nuclei_", or "Cytoplasm_"
    samples : list of str or str, default "all"
        Samples to perform the operation on
    outlier_cutoff : int or float, default 500
    see https://github.com/cytomining/pycytominer/issues/237 for details.
        Threshold to remove features if absolute values is greater

    Returns
    -------
    outlier_features: list of str
        Features greater than the threshold.
    """

    # Subset dataframe
    if samples != "all":
        population_df = population_df.loc[samples, :]

    if features == "infer":
        features = infer_cp_features(population_df)
        population_df = population_df.loc[:, features]
    else:
        population_df = population_df.loc[:, features]

    max_feature_values = population_df.max().abs()
    min_feature_values = population_df.min().abs()

    outlier_features = max_feature_values[
        (max_feature_values > outlier_cutoff) | (min_feature_values > outlier_cutoff)
    ].index.tolist()

    return outlier_features


def convert_compartment_format_to_list(compartments):
    """Converts compartment to a list.

    Parameters
    ----------
    compartments : list of str or str
        Cell Painting compartment(s).

    Returns
    -------
    compartments : list of str
        List of Cell Painting compartments.
    """

    if isinstance(compartments, list):
        compartments = [x.lower() for x in compartments]
    elif isinstance(compartments, str):
        compartments = [compartments.lower()]

    return compartments
TW_EOF
mkdir -p pycytominer
cat > pycytominer/feature_select.py <<'TW_EOF'
"""
Select features to use in downstream analysis based on specified selection method
"""

import os
import pandas as pd

from pycytominer.operations import (
    correlation_threshold,
    variance_threshold,
    get_na_columns,
    noise_removal,
)
from pycytominer.cyto_utils import (
    load_profiles,
    output,
    get_blocklist_features,
    infer_cp_features,
    drop_outlier_features,
)


def feature_select(
    profiles,
    features="infer",
    image_features=False,
    samples="all",
    operation="variance_threshold",
    output_file="none",
    na_cutoff=0.05,
    corr_threshold=0.9,
    corr_method="pearson",
    freq_cut=0.05,
    unique_cut=0.1,
    compression_options=None,
    float_format=None,
    blocklist_file=None,
    outlier_cutoff=500,
    noise_removal_perturb_groups=None,
    noise_removal_stdev_cutoff=None,
):
    """Performs feature selection based on the given operation.

    Parameters
    ----------
    profiles : pandas.core.frame.DataFrame or file
        DataFrame or file of profiles.
    features : list
        A list of strings corresponding to feature measurement column names in the
        `profiles` DataFrame. All features listed must be found in `profiles`.
        Defaults to "infer". If "infer", then assume cell painting features are those
        prefixed with "Cells", "Nuclei", or "Cytoplasm".
    image_features: bool, default False
        Whether the profiles contain image features.
    samples : list or str, default "all"
        Samples to provide operation on.
    operation: list of str or str, default "variance_threshold
        Operations to perform on the input profiles.
    output_file : str, optional
        If provided, will write annotated profiles to file. If not specified, will
        return the normalized profiles as output. We recommend that this output file be
        suffixed with "_normalized_variable_selected.csv".
    na_cutoff : float, default 0.05
        Proportion of missing values in a column to tolerate before removing.
    corr_threshold : float, default 0.1
        Value between (0, 1) to exclude features above if any two features are correlated above this threshold.
    corr_method : str, default "pearson"
        Correlation type to compute. Allowed methods are "spearman", "kendall" and "pearson".
    freq_cut : float, default 0.05
        Ratio (2nd most common feature val / most common). Must range between 0 and 1.
        Remove features lower than freq_cut. A low freq_cut will remove features
        that have large difference between the most common feature and second most
        common feature. (e.g. this will remove a feature: [1, 1, 1, 1, 0.01, 0.01, ...])
    unique_cut: float, default 0.01
        Ratio (num unique features / num samples). Must range between 0 and 1.
        Remove features less than unique cut. A low unique_cut will remove features
        that have very few different measurements compared to the number of samples.
    compression_options : str or dict, optional
        Contains compression options as input to
        pd.DataFrame.to_csv(compression=compression_options). pandas version >= 1.2.
    float_format : str, optional
        Decimal precision to use in writing output file as input to
        pd.DataFrame.to_csv(float_format=float_format). For example, use "%.3g" for 3
        decimal precision.
    blocklist_file : str, optional
        File location of datafrmame with with features to exclude. Note that if "blocklist" in operation then will remove standard blocklist
    outlier_cutoff : float, default 500
        The threshold at which the maximum or minimum value of a feature across a full experiment is excluded. Note that this procedure is typically applied after normalization.
    noise_removal_perturb_groups: str or list of str, optional
        Perturbation groups corresponding to rows in profiles or the the name of the metadata column containing this information.
    noise_removal_stdev_cutoff: float,optional
        Maximum mean feature standard deviation to be kept for noise removal, grouped by the identity of the perturbation from perturb_list. The data must already be normalized so that this cutoff can apply to all columns.

    Returns
    -------
    selected_df : pandas.core.frame.DataFrame, optional
        The feature selected profile DataFrame. If output_file="none", then return the
        DataFrame. If you specify output_file, then write to file and do not return
        data.

    """

    all_ops = [
        "variance_threshold",
        "correlation_threshold",
        "drop_na_columns",
        "blocklist",
        "drop_outliers",
        "noise_removal",
    ]

    # Make sure the user provides a supported operation
    if isinstance(operation, list):
        assert all(
            [x in all_ops for x in operation]
        ), "Some operation(s) {} not supported. Choose {}".format(operation, all_ops)
    elif isinstance(operation, str):
        assert operation in all_ops, "{} not supported. Choose {}".format(
            operation, all_ops
        )
        operation = operation.split()
    else:
        return ValueError("Operation must be a list or string")

    # Load Data
    profiles = load_profiles(profiles)

    if features == "infer":
        features = infer_cp_features(profiles, image_features=image_features)

    excluded_features = []
    for op in operation:
        if op == "variance_threshold":
            exclude = variance_threshold(
                population_df=profiles,
                features=features,
                samples=samples,
                freq_cut=freq_cut,
                unique_cut=unique_cut,
            )
        elif op == "drop_na_columns":
            exclude = get_na_columns(
                population_df=profiles,
                features=features,
                samples=samples,
                cutoff=na_cutoff,
            )
        elif op == "correlation_threshold":
            exclude = correlation_threshold(
                population_df=profiles,
                features=features,
                samples=samples,
                threshold=corr_threshold,
                method=corr_method,
            )
        elif op == "blocklist":
            if blocklist_file:
                exclude = get_blocklist_features(
                    population_df=profiles, blocklist_file=blocklist_file
                )
            else:
                exclude = get_blocklist_features(population_df=profiles)
        elif op == "drop_outliers":
            exclude = drop_outlier_features(
                population_df=profiles,
                features=features,
                samples=samples,
                outlier_cutoff=outlier_cutoff,
            )
        elif op == "noise_removal":
            exclude = noise_removal(
                population_df=profiles,
                features=features,
                samples=samples,
                noise_removal_perturb_groups=noise_removal_perturb_groups,
                noise_removal_stdev_cutoff=noise_removal_stdev_cutoff,
            )
        excluded_features += exclude

    excluded_features = list(set(excluded_features))

    selected_df = profiles.drop(excluded_features, axis="columns")

    if output_file != "none":
        output(
            df=selected_df,
            output_filename=output_file,
            compression_options=compression_options,
            float_format=float_format,
        )
    else:
        return selected_df
TW_EOF
