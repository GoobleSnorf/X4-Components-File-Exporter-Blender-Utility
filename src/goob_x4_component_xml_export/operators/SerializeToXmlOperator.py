import bpy

import os
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import objectify, etree
from mathutils import Vector
import numpy as np

def get_adjusted_position(object) -> dict:
    location_vector = object.location.xyz

    position = {
        "x":str(location_vector[0]),
        #   y and z are flipped
        "y":str(location_vector[2]),
        "z":str(location_vector[1])
    }

    return position

def get_adjusted_rotation(object) -> dict:
    #   Egosoft did some weird things with rotation,
    #   I found this mapping to work by trial & error.
    quaternion = {
        "qw":str(object.rotation_quaternion.w),
        "qx":str(-object.rotation_quaternion.x),
        #   y and z are flipped
        "qy":str(-object.rotation_quaternion.z),
        "qz":str(-object.rotation_quaternion.y)
    }

    return quaternion

def get_offset_xml(object) -> etree.Element:
    offset_xml = etree.Element("offset")

    position = get_adjusted_position(object)

    quaternion = get_adjusted_rotation(object)

    position_xml = etree.Element(
        "position",
        **position
    )

    quaternion_xml = etree.Element(
        "quaternion",
        **quaternion
    )

    location_vector = object.location.xyz

    #   Check to see if position is negligible
    should_include_position = (
            abs(location_vector[0])
        +   abs(location_vector[1])
        +   abs(location_vector[2])
    ) > 0.001

    if should_include_position:
        offset_xml.insert(0, position_xml)

    #   Check to see if rotation is negligible
    should_include_quaternion = (
            # abs(object.rotation_quaternion.w)
            abs(object.rotation_quaternion.x)
        +   abs(object.rotation_quaternion.y)
        +   abs(object.rotation_quaternion.z)
    ) > 0.001

    if should_include_quaternion:
        offset_xml.insert(0, quaternion_xml)

    return offset_xml

def get_true_dimensions(object) -> dict:
    """
        Get dimensions of mesh object ignoring all
        modifiers scaling/rotation.

        https://blender.stackexchange.com/questions/212926/how-to-get-the-base-dimensions-of-an-object-ignoring-all-of-its-modifiers
    """

    coords = np.empty(3 * len(object.data.vertices))
    object.data.vertices.foreach_get("co", coords)
    x, y, z = coords.reshape((-1, 3)).T

    mesh_dim = {
            "x": str(x.max() - x.min()),
            "y": str(y.max() - y.min()),
            "z": str(z.max() - z.min())
    }

    return mesh_dim

def get_parts_xml(object) -> etree.Element:
    #   TODO: Seems <lods> is no longer used? May need to add here in the future.

    max = get_true_dimensions(object)
    # max = {
    #     "x": str(object.dimensions.xyz.x),
    #     "y": str(object.dimensions.xyz.y),
    #     "z": str(object.dimensions.xyz.z)
    # }

    #   https://blender.stackexchange.com/questions/62040/get-center-of-geometry-of-an-object
    local_bound_box_center = 0.125 * sum((Vector(b) for b in object.bound_box), Vector())

    center = {
        "x": str(local_bound_box_center[0]),
        "y": str(local_bound_box_center[1]),
        "z": str(local_bound_box_center[2])
    }

    max_xml = etree.Element("max", **max)
    center_xml = etree.Element("center", **center)

    size_xml = etree.Element("size")

    size_xml.append(max_xml)
    size_xml.append(center_xml)

    part_xml = etree.Element("part", name=object.name)

    part_xml.insert(0, size_xml)

    parts_xml = etree.Element("parts")

    parts_xml.insert(0, part_xml)

    return parts_xml

def get_if_animations_needed(object, filtered_tags) -> bool:
    if "animation" in filtered_tags:
        return True

    return False

def get_animation_xml(nla_track, strip):
    animation_attributes = {
        "name": nla_track.name + "_" + strip.name,
        "start": str(round(strip.action_frame_start)),
        "end": str(round(strip.action_frame_end))
    }

    animation_xml = etree.Element(
        "animation",
        **animation_attributes
    )

    return animation_xml

def get_animations_xml(object):
    animations_xml = etree.Element("animations")

    for nla_track in object.animation_data.nla_tracks:
        for strip in nla_track.strips:
            animations_xml.append(get_animation_xml(nla_track, strip))
    
    return animations_xml

def get_connection_xml(object) -> etree.Element:
    #   Tags is effectively a dict where we include the key if the value is 1
    #   Maybe this is used for one-hot encoding internally in the game engine?
    geometry_tags = []
    connection_tags = []

    if hasattr(object, "GeometryTags"):
        geometry_tags = [key for key, value in object.GeometryTags.items() if value == 1]

    if hasattr(object, "ConnectionTags"):
        connection_tags = [key for key, value in object.ConnectionTags.items() if value == 1]
    
    filtered_tags = geometry_tags + connection_tags

    tags = " ".join(filtered_tags)

    #   "part" objects are meshes, and have some different handling
    is_part = (
            object.type == "MESH"
        #   Ignore additional LODs
        and not object.name.endswith("lod1")
        and not object.name.endswith("lod2")
        and not object.name.endswith("lod3")
        and not "_hull_" in object.name
    )

    #   Following Egosoft's convention for prefixing part connection names
    if is_part:
        connection_name = "ConnectionFor" + object.name
    else:
        connection_name = object.name

    connection_attributes = {
        "name": connection_name
    }

    if len(tags) > 0:
        #   Apparently this " " at the end is load-bearing
        connection_attributes["tags"] = tags + " "

    #   Only include value if it's non-zero
    if object.value != 0:
        connection_attributes["value"] = str(object.value)
    
    #   Groups are pre-aggregated into a string, only include if not empty
    if object.groups:
        #   Apparently this " " at the end is load-bearing
        connection_attributes["group"] = object.groups.strip() + " "
    
    connection_xml = etree.Element(
        "connection",
        **connection_attributes
    )

    #   Offset
    connection_xml.append(get_offset_xml(object))

    #   Animations
    if get_if_animations_needed(object, filtered_tags):
        connection_xml.append(get_animations_xml(object))

    #   Parts
    if is_part:
        connection_xml.append(get_parts_xml(object))

    return connection_xml

def get_components_xml(context):
    #   For now, I don't know of a way to get the class, think this is stored in the Egosoft panel?
    class_name = context.scene.classAttr
    geometry_source_directory = context.scene.x4_component_exporter.geometrySourceDirectory

    #   Component name is the file name without extension
    component_name = Path(bpy.context.blend_data.filepath).stem

    component_attributes = {
        "class": class_name,
        "name": component_name
    }

    components_xml = etree.Element(
        "components"
    )

    component_xml = etree.Element(
        "component",
        component_attributes
    )

    #   Adding source geometry, hard-coded for now
    component_xml.insert(
        0,
        etree.Element(
            "source",
            # geometry=r"extensions\cubix\assets\units\size_l\goob_ship_jb1_data"
            geometry=geometry_source_directory
        )
    )

    components_xml.insert(
        0,
        component_xml
    )

    return components_xml

def get_if_connection_needed(object):
    #   Waypoints have no connection XML
    if get_if_waypoint_needed(object):
        return False
    
    #   "part" objects are meshes, and have some different handling
    is_part = (
            object.type == "MESH"
        #   Ignore additional LODs
        and not object.name.lower().endswith("lod1")
        and not object.name.lower().endswith("lod2")
        and not object.name.lower().endswith("lod3")
        and not "_hull_" in object.name.lower()
    )

    geometry_tags = []
    connection_tags = []

    if hasattr(object, "GeometryTags"):
        geometry_tags = [key for key, value in object.GeometryTags.items() if value == 1]

    if hasattr(object, "ConnectionTags"):
        connection_tags = [key for key, value in object.ConnectionTags.items() if value == 1]
    
    active_connection_tags = geometry_tags + connection_tags

    has_active_tags = len(active_connection_tags) > 0

    is_skip_export = "skipexport" in active_connection_tags

    #   We are only processing objects that:
    #   -     are meshes
    #   - OR  have active tags
    #   - AND aren't explicitly marked "skipexport"
    # if (is_part or has_active_tags) and not is_skip_export:
    if (has_active_tags or is_part) and not is_skip_export:

        return True
        # self.report({'INFO'}, object.name + " " + " ".join(active_connection_tags))

    return False

def get_if_waypoint_needed(object) -> bool:
    #   "Waypoint" objects should have 3 custom properties:
    #       - list
    #       - waypoint
    #       - waypoint_properties

    if "waypoint" in object:
        return True

    return False

def get_waypoint_xml(object):
    position = get_adjusted_position(object)
    rotation = get_adjusted_rotation(object)

    waypoint_tags = []

    if hasattr(object, "Waypoints"):
        waypoint_tags = [key for key, value in object.Waypoints.items() if value == 1]

    waypoint_tags_dict = {
        "tags": " ".join(waypoint_tags) + " "
    }

    waypoint_name_dict = {
        "name": object.name
    }

    waypoint_attributes = waypoint_name_dict | waypoint_tags_dict | position | rotation

    waypoint_xml = etree.Element(
        "waypoint",
        **waypoint_attributes
    )

    link_target_list = []

    for constraint in object.constraints:
        link_target_list.append(constraint.target.name)

    if len(link_target_list) > 0:
        links_xml = etree.Element("links")

        for link_target in link_target_list:
            links_xml.insert(
                0,
                etree.Element(
                    "link",
                    ref=link_target
                )
            )

        waypoint_xml.insert(
            0,
            links_xml
        )
    
    return waypoint_xml

def get_connections_xml():
    connections_xml = etree.Element("connections")
    
    #   Adding hard-coded connections for ship_l
    connections_xml.insert(
        0,
        etree.Element(
            "connection",
            name="container",
            tags="contents",
            value="0"
        )
    )

    connections_xml.insert(
        0,
        etree.Element(
            "connection",
            name="position",
            tags="position",
            value="1"
        )
    )

    connections_xml.insert(
        0,
        etree.Element(
            "connection",
            name="space",
            tags="ship ship_l"
        )
    )

    #   Gather up all the connections
    for object in bpy.data.objects:
        if get_if_connection_needed(object):
            connection_xml = get_connection_xml(object)
            connections_xml.insert(0, connection_xml)
        
    return connections_xml

def get_waypoints_xml():
    waypoints_xml = etree.Element("waypoints")

    for object in bpy.data.objects:
        if get_if_waypoint_needed(object):
            waypoint_xml = get_waypoint_xml(object)
            waypoints_xml.append(waypoint_xml)
    
    return waypoints_xml

def get_layers_xml():
    #   TODO: Find out if it is possible to have multiple layers
    layers_xml = etree.Element("layers")

    layer_xml = etree.Element("layer")

    waypoints_xml = get_waypoints_xml()

    layer_xml.append(waypoints_xml)

    layers_xml.insert(
        0,
        layer_xml
    )

    return layers_xml

def main(self, context):
    target_xml_file_path = os.path.splitext(bpy.context.blend_data.filepath)[0] + ".xml"

    components_xml = get_components_xml(context)

    layers_xml = get_layers_xml()

    connections_xml = get_connections_xml()


    #   Should only have 1
    for component in components_xml:
        component.insert(0,connections_xml)
        component.insert(0,layers_xml)

    #   Convert element and children to an element tree
    #   for exporting to a file
    element_tree = etree.ElementTree(components_xml)
    
    #   TODO: Decide how we want to handle an existing file
    element_tree.write(
        target_xml_file_path,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    )

class SerializeToXmlOperator(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "object.serialize_to_xml_operator"
    bl_label = "Serialize to Component XML Operator"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        main(self, context)
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(SerializeToXmlOperator.bl_idname, text=SerializeToXmlOperator.bl_label)

# Register and add to the "object" menu (required to also use F3 search "Simple Object Operator" for quick access).
def register():
    bpy.utils.register_class(SerializeToXmlOperator)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(SerializeToXmlOperator)
    bpy.types.VIEW3D_MT_object.remove(menu_func)

if __name__ == "__main__":
    register()