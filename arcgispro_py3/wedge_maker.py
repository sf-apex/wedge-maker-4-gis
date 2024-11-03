import os
import math
import arcpy


def erase(
    input_fc: str,
    erase_fc: str,
    output_fc: str,
):
    """
    Performs the same as arcpy.Erase_analysis, without the advanced license.

    Args:
        input_fc (str): path of input feature class
        erase_fc (str): path of features to erase from input
        output_fc (str): path of output feature class
    """

    # define erase feature layer
    erase_fl = "erase_fl"

    # define input fc and erase fc names
    input_fc_name = os.path.basename(input_fc)
    erase_fc_name = os.path.basename(erase_fc)

    # list fields in erase fc
    fields = arcpy.ListFields(erase_fc)

    # create a fieldinfo object
    fieldinfo = arcpy.FieldInfo()

    # set all fields to hidden
    for field in fields:
        fieldinfo.addField(field.name, field.name, "HIDDEN", "NONE")

    # create erase feature layer with all fields hidden
    arcpy.MakeFeatureLayer_management(
        in_features = erase_fc,
        out_layer = erase_fl,
        field_info = fieldinfo
    )

    # union input to erase features
    arcpy.Union_analysis(
        in_features = [input_fc, erase_fl],
        out_feature_class = output_fc
    )

    # delete features where FID_{input_layer} < 0 or FID_{erase_layer} > 0
    with arcpy.da.UpdateCursor(
        in_table = output_fc,
        field_names = ["oid@"],
        where_clause = f"FID_{input_fc_name} < 0 OR FID_{erase_fc_name} > 0",
    ) as uCur:
        for _ in uCur:
            uCur.deleteRow()

    # and finally delete the extra fields
    for f in [f"FID_{input_fc_name}", f"FID_{erase_fc_name}"]:
        arcpy.DeleteField_management(output_fc, f)


def innerWedgeErase(centerX, centerY, r2, wedge):
    """
    Cut out the inner part of the wedge based upon the original point feature
    class's radius2 field.  Returns a string with the location of the output
    wedge.

    Args:
        centerX (float): X coord of wedge center
        centerY (float): Y coord of wedge center
        r2 (float): Inner radius of the wedge, in meters
        wedge (str): Path of wedge feature class from which to erase
    """

    # skip if r2 = 0 or empty
    if not r2:
        return wedge

    # create arcpy.PointGeometry to buffer
    pointGeometry = arcpy.PointGeometry(
        inputs = arcpy.Point(centerX, centerY),
        spatial_reference = arcpy.Describe(wedge).spatialReference
    )

    # buffer by inner radius distance
    circle = "memory\\circle"
    arcpy.Buffer_analysis([pointGeometry], circle, f"{r2} METERS")

    # erase buffer from input wedge
    oWedge2 = "memory\\oWedge2"
    erase(wedge, circle, oWedge2)

    return oWedge2


def createOneWedge(
    centerX, centerY, angleA, angleB, r, outWedgeName, projOut
):
    """
    Creates a single wedge feature class.

    Performs trigonometric calculations to determine the
    vertices of the Clip/Erase triangle, creates the circle and triangle
    geometry, and performs the necessary Clip/Erase to generate the wedge/
    Pac-Man shape.  Returns a string with the location of the output wedge.

    Args:
        -- The X coordinate of the center of the wedge (int or float)
        -- The Y coordinate of the center of the wedge (int or float)
        -- The start line of bearing of the wedge (int or float)
        -- The end line of bearing of the wedge (int or float)
        -- The outer radius of the wedge (int or float)
        -- The path and name of the wedge to be created (string)
        -- Desired projection of the wedge (arcpy.SpatialReference)

    angleA and angleB must fall in the range [0, 360).  r must be
    greater than 0 and must be in meters.
    """

    # define theta as the angle between the two lines of bearing
    theta = angleB - angleA

    # define erase_bool before converting theta to radians
    erase_bool = (theta % 360 > 180)

    # switch to radians to work with Python's trig functions
    angleA = math.radians(angleA)
    angleB = math.radians(angleB)
    theta = math.radians(theta)

    # calculate hypotenuse, convert from feet if CRS is SPCS
    adjustment = 3.2808399 if projOut.linearUnitName == "Foot_US" else 1
    hyp = math.fabs(r * adjustment / math.cos(theta/2))

    # get X and Y coords of the endpoints of this hypotenuse
    ptAX = centerX + math.fabs(hyp) * math.sin(angleA)
    ptAY = centerY + math.fabs(hyp) * math.cos(angleA)
    ptBX = centerX + math.fabs(hyp) * math.sin(angleB)
    ptBY = centerY + math.fabs(hyp) * math.cos(angleB)

    # define the center point geometry
    center_point = arcpy.Point(centerX, centerY)
    pointGeometry = arcpy.PointGeometry(
        inputs = center_point,
        spatial_reference = projOut
    )

    # define the triangle as an array, from center and two end points   
    array = arcpy.Array(
        items = [
            center_point,
            arcpy.Point(ptAX, ptAY),
            arcpy.Point(ptBX, ptBY),
            center_point
        ]
    )
    triangle_poly = arcpy.Polygon(array, projOut)

    # export triangle as a feature class
    triangle = "memory\\triangle"
    arcpy.CopyFeatures_management([triangle_poly], triangle)

    # buffer the center point
    circle = "memory\\circle"
    arcpy.Buffer_analysis([pointGeometry], circle, f'{r} METERS')

    # define this wedge feature class
    outWedge = f"memory\\{outWedgeName}"
    
    #In the special case where theta is a multiple of 360 (and greater than
    #0) don't do any erasing or clipping. Just copy the circle feature over
    #to the final output feature class.
    if theta == 0:
        arcpy.CopyFeatures_management(circle, outWedge)
        return outWedge

    # If theta is greater than 180 degrees, erase the triangle from the
    #circle to get a Pac-Man shape. If not, clip the circle with the
    #triangle and get the wedge shape.
    if erase_bool:
        erase(circle, triangle, outWedge)
    else:
        arcpy.Clip_analysis(circle, triangle, outWedge)

    return outWedge


def createWedges(attributesList, outputFC, projOut):
    """
    Create a feature class of wedge/arcband shapes based upon the attribute
    information in attributesList.

    attributesList contains a list item for each wedge to be created, read from
    the geometry and attributes of the input shapefile.  The order of the items
    in the list is centerX, centerY, the first angle (angleA), the second angle
    (angleB), the outer (or only) radius, the inner radius (optional), and a
    number that counts the wedges as they are made.

    The procedure passes the necessary information for each wedge onto the
    createOneWedge procedure unless the wedge is between 135 and 225 degrees,
    in which case it calls createOneWedge twice to make two adjacent wedges
    because a wedge between those two degree measures may cause the resulting
    clip/erase triangle to be too large for the input projection.  As an
    extreme case, a 180-degree wedge would result in the creation of an invalid
    clip/erase triangle, while a 179.999 degree wedge, for example, could
    result in the creation of an extremely wide clip/erase triangle, one that
    ArcGIS may not be able to work with.  After creating the two adjacent
    wedges, the tool then merges and dissolves them to make the full wedge.
    Once the wedge is made, it checks whether the optional inner radius
    parameter is present in the wedge list.  If it is, it creates a circle of
    that inner radius and uses it to erase from the wedge, resulting in the
    final "arcband."

    Keyword arguments:
    attributesList -- A list of lists.  Each list contains 5 or 6 entries:
        -- Wedge ID, e.g., ObjectID (int)
        -- The X coordinate of the center of the wedge (int or float)
        -- The Y coordinate of the center of the wedge (int or float)
        -- The start line of bearing of the wedge (int or float)
        -- The end line of bearing of the wedge (int or float)
        -- The outer radius of the wedge (int or float)
        -- The inner radius of the wedge (optional) (int or float)
    outputFC -- The path to the tool's output point feature class (string)
    projOut -- CRS to use (arcpy.SpatialReference)
    """

    #Keep track of how many wedges have been processed
    count = 1

    # collect individual feature classes in a list to merge at the end
    mergeList = []

    #Process each wedge in turn
    for wedge in attributesList:

        #Extract the mandatory information about the wedge from its list
        wedgeNumber = wedge[0]
        centerX = wedge[1]
        centerY = wedge[2]
        angleA = wedge[3]
        angleB = wedge[4]
        r1 = wedge[5]

        #If the user enters two lines of bearing that are identical, skip
        #that wedge entirely, but let the user know we've skipped a wedge.
        #Otherwise, if the user enters two lines of bearing differing by a
        #multiple of 360 degrees, this will just create a circular buffer
        if angleA == angleB:
            print(f"Skipping wedge {count} (0-degree wedge)...")
            count += 1
            continue

        #Reduce the angles to a range >= 0 and < 360
        angleA = angleA % 360
        angleB = angleB % 360

        #Calculate the difference between the two angles
        theta = (angleB - angleA) % 360

        # Announce we're gonna cook up a wedge...
        print(f"Creating wedge {count} of {len(attributesList)}...")

        #If theta is too close to 180 degrees, the triangle math may fail
        #because the coordinates of the Clip/Erase triangle will become
        #extremely large in magnitude. In those cases, make two smaller
        #wedges and dissolve them together.
        if 135 < theta < 225:

            #Create the first wedge
            angleB = (angleA + theta/2) % 360
            wedge1 = createOneWedge(
                centerX, centerY, angleA, angleB, r1, "WedgeA", projOut
            )

            #Create the second wedge
            angleA = angleB
            angleB = (angleB + theta/2) % 360
            wedge2 = createOneWedge(
                centerX, centerY, angleA, angleB, r1, "WedgeB", projOut
            )

            #Now merge the two wedges, dissolve, and clean up
            arcpy.Merge_management([wedge1, wedge2],
                                    "memory\\WedgeC")

            oWedge = "memory\\oWedge"
            arcpy.Dissolve_management("memory\\WedgeC", oWedge)

        #If theta isn't close to 180, proceed normally
        else:
            oWedge = createOneWedge(
                centerX, centerY, angleA, angleB, r1, "oWedge", projOut
            )

        #If an inner radius is provided, use it to erase the donut hole
        if len(wedge) == 7:
            r2 = wedge[6]
            oWedge = innerWedgeErase(
                centerX, centerY, r2, oWedge
            )

        #Create a wedge id field and populate with the given wedge id
        arcpy.AddField_management(oWedge, "WID", 'LONG')
        with arcpy.da.UpdateCursor(oWedge, "WID") as uCur:
            for row in uCur:
                row[0] = wedgeNumber
                uCur.updateRow(row)
        count += 1

        #Give this wedge a unique name in the memory workspace and
        #add it to the list of feature classes to be merged at the end
        nextWedge = "memory\\nextWedge" + str(count)
        arcpy.CopyFeatures_management(oWedge, nextWedge)
        mergeList.append(nextWedge)

    # Merge the individual wedge feature classes into an outputFC
    print('Merging wedges...')
    arcpy.Merge_management(mergeList, outputFC)

    # And clean up the output by removing extra fields
    for field in ["BUFF_DIST", "ORIG_FID"]:
        arcpy.DeleteField_management(outputFC, field)
