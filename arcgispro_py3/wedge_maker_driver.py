import os
import arcpy
import sys
sys.dont_write_bytecode = True
from wedge_maker import createWedges


NUMERIC_ARCGIS_TYPES = [
    "single", "double", # float
    "long", "short" # int
]

EXPECTED_INPUT_FIELDS = {
    # field name: allowed types
    "a1": NUMERIC_ARCGIS_TYPES,
    "a2": NUMERIC_ARCGIS_TYPES,
    "r1": NUMERIC_ARCGIS_TYPES,
    "r2": NUMERIC_ARCGIS_TYPES
}

OPTIONAL_INPUT_FIELD = "r2"


def validate_input_shp(input_shp: str):
    """
    Validate input shapefile and its fields

    Args:
        input_shp (str): file path

    Raises:
        AssertionError: if input is invalid or fields are missing or mistyped

    Returns:
        list[str]: included fields, in expected wedge_buffer param order
    """

    # assert input is a shapefile
    assert input_shp.lower().endswith(".shp"), input_shp

    # assert shapefile exists
    assert arcpy.Exists(input_shp), input_shp

    # assert point features
    desc = arcpy.Describe(input_shp)
    shape_type = desc.shapeType
    assert shape_type == 'Point', shape_type

    # define input fields and types
    input_fields = {
        f.name.lower(): str(f.type.lower())
        for f in arcpy.ListFields(input_shp)
    }

    # prep check required input fields are correct types
    mismatched = {
        k: {"current_type": v, "allowed_types": EXPECTED_INPUT_FIELDS[k]}
        for k, v in input_fields.items()
        if k in EXPECTED_INPUT_FIELDS and v not in EXPECTED_INPUT_FIELDS[k]
    }

    # prep check no required fields are missing
    missing = {
        k: v
        for k, v in EXPECTED_INPUT_FIELDS.items()
        if k not in input_fields and k != OPTIONAL_INPUT_FIELD
    }

    # prep return list of included fields
    included = [
        f for f in EXPECTED_INPUT_FIELDS
        if f in input_fields
    ]

    # execute field checks
    assert (
        not mismatched and not missing
    ), f"\nmismatched fields:\n{mismatched}\n\nmissing_fields:\n{missing}\n"

    return included


def validate_sref(input_shp: str):
    """
    Validate spatial reference of input is acceptable.
    Accepted CRS's include any UTM (Meter) or State Plane (Foot_US)

    Args:
        input_shp (str): file path

    Raises:
        ValueError: if input spatial reference isn't acceptable

    Returns:
        arcpy.SpatialReference
    """

    # get spatial reference from input
    sref = arcpy.Describe(input_shp).spatialReference

    # special message for unknown sref
    if sref.Name == "Unknown":
        raise ValueError("Input shp does not have projection information.")

    # standard message for all other unaccepted types
    if (
        sref.Name == "GCS_WGS_1984" or
        sref.linearUnitName not in ["Meter", "Foot_US"]
    ):
        raise ValueError(
            "Please reproject to a non-WGS84 CRS intended for analysis,"
            "\ne.g., local UTM (Meter) or local State Plane (Foot_US)."
            f"\nCurrent CRS is: {sref.Name} ({sref.linearUnitName})"
        )

    return sref


def validate_output_shp(input_shp: str, output_shp: str = None):
    """
    Validate output_shp path, or create from input if none provided

    Args:
        input_shp (str): file path
        output_shp (str): file path, default f"{input_root}_buff.shp"

    Raises:
        AssertionError: if output is invalid, or exists and wouldn't overwrite

    Returns:
        str: output shapefile path
    """

    # define output_shp if not provided
    if not output_shp:
        root, ext = os.path.splitext(input_shp)
        output_shp = f"{root}_buff{ext}"

    # assert output will be a shapefile
    assert output_shp.lower().endswith(".shp"), output_shp

    # assert that output does not exist already, or overwrite mode is on
    assert (
        not arcpy.Exists(output_shp) or arcpy.env.overwriteOutput
    ), f"Set arcpy.env.overwriteOutput=True or remove: `{output_shp}`"

    return output_shp


def wedge_buffer_driver(
    input_shp: str,
    output_shp: str = None,
):
    """
    All you really need to run wedge buffers is a single input shapefile having:
     - all point features
     - CRS in local UTM or state plane
     - fields:
        a1 (float): angle 1, in degrees
        a2 (float): angle 2, in degrees
        r1 (float): radius 1, in meters
        r2 (float): radius 2, in meters [OPTIONAL]

    Args:
        input_shp (str): file path
        output_shp (str): file path, default f"{input_root}_buff.shp"

    Returns:
        str: buffered output shapefile path
    """

    # announce start
    print("\nSTARTING WEDGE BUFFER SCRIPT\n")

    # validate inputs
    input_fields = validate_input_shp(input_shp)
    sref = validate_sref(input_shp)
    output_shp = validate_output_shp(input_shp, output_shp)

    # create a list of lists (attributes) from input_shp
    attributes = [
        row for row in arcpy.da.SearchCursor(
            in_table = input_shp,
            field_names = ["oid@", "shape@x", "shape@y"] + input_fields,
        )
    ]

    # call createWedges
    createWedges(
        attributesList = attributes,
        outputFC = output_shp,
        projOut = sref
    )

    # announce completion
    print(f"\nCOMPLETE: `{output_shp}`\n")

    return output_shp


if __name__ == "__main__":

    # overwrite outputs on repeat runs
    arcpy.env.overwriteOutput = True

    # illustrate usage with one of the example_data shps
    input_shp = os.path.join(
        os.path.dirname(__file__),
        "example_data",
        "points_utm.shp"
    )

    # call our function on the example shp, or supply your own!
    output_shp = wedge_buffer_driver(input_shp)
