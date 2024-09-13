import os
import bpy
from math import radians
import pprint as pp

def generate_preview():
    '''This function generates blender file preview image in DAM'''

    blend_filepath = str(bpy.data.filepath)     # active blend file
    blend_dirpath, blend_filename = os.path.split(os.path.abspath(blend_filepath))
    print("current directory ", blend_dirpath)
    print("active blend file ", blend_filename)
    
    curr_dir = os.getcwd()
    os.chdir(blend_dirpath)
    print("active directory", os.getcwd())

    # set preview image path in the active blend file directory
    preview_filepath = os.path.join(blend_dirpath, "preview.jpg")

    if os.path.exists(preview_filepath):
        os.remove(preview_filepath)

    # check whether camera is present or not
    cam_obj = bpy.context.scene.camera

    if cam_obj is None:
        print("no scene camera")
        add_camera()
        bg_shader()
    elif cam_obj.type == 'CAMERA':
        print("regular scene cam")
    else:
        print("%s object as camera" % cam_obj.type)

    # generate rendered image
    render_preview(preview_filepath, sample_count=4)
    
    print("rendering completed")

def add_camera():
    '''To create new camera and add to scene'''

    camera_data = bpy.data.cameras.new(name='Camera')
    camera_object = bpy.data.objects.new('Camera', camera_data)
    bpy.context.scene.camera = camera_object

    # bpy.context.scene.collection.objects.link(camera_object)

    # Select objects that will be rendered
    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    for obj in bpy.context.visible_objects:
        if not (obj.hide_get() or obj.hide_render):
            obj.select_set(True)

    camera_object.rotation_euler = (radians(75), radians(0), radians(-30))

    bpy.ops.view3d.camera_to_view_selected()

    print(camera_object.location)
    print(camera_object.rotation_euler)

def bg_shader():
    '''To add backgroungd shader to previews'''

    # select world node tree
    wd = bpy.context.scene.world
    wd.use_nodes = True
    nt = bpy.data.worlds[wd.name].node_tree

    #find location of World Output
    world = nt.nodes['World Output']
    worldIn = world.inputs['Surface']

    mixShader = nt.nodes.new(type="ShaderNodeMixShader")
    mixShaderOut = mixShader.outputs['Shader']
    mixShaderIn1 = mixShader.inputs[1]
    mixShaderIn2 = mixShader.inputs[2]
    mixShaderFac = mixShader.inputs['Fac']
    nt.links.new(mixShaderOut, worldIn)

    back1 = nt.nodes.new(type="ShaderNodeBackground")
    back1.color = (0, 1, 0)
    pp.pprint(back1.color)

    back1Out = back1.outputs['Background']
    nt.links.new(back1Out, mixShaderIn1)

    back2 = nt.nodes.new(type="ShaderNodeBackground")
    back2.color = (1, 0, 0)
    back2Out = back2.outputs['Background']
    nt.links.new(back2Out, mixShaderIn2)

    lightPath = nt.nodes.new(type="ShaderNodeLightPath")
    lightPathOut = lightPath.outputs['Is Camera Ray']
    nt.links.new(lightPathOut, mixShaderFac)


def render_preview(preview_filepath, sample_count=1):
    '''To generate previews by rendering'''

    params_dict = {"render.image_settings.file_format": "JPEG",
                   "render.image_settings.quality": 50,
                   "render.resolution_x": 1440,
                   "render.resolution_y": 960,
                   "render.engine": "CYCLES",
                   "cycles.samples": sample_count,
                   "render.use_simplify": True,
                   "render.filepath": preview_filepath
                   }

    # get old parameters
    old_params = get_params(params_dict)

    # set preview image parameters
    set_params(params_dict)
    bpy.ops.render.render(write_still=True, use_viewport=True)

    # set old parameters
    set_params(old_params)

def get_params(inpDict):
    res = {}
    for k,v in inpDict.items():
        res[k] = rec_getattr(bpy.context.scene, k)
    return res
        
def set_params(inpDict):
    res = {}
    for k, v in inpDict.items():
        rec_setattr(bpy.context.scene, k, v)

def rec_getattr(obj, attr):
    if '.' not in attr:
        return getattr(obj, attr)
    else:
        L = attr.split('.')
        return rec_getattr(getattr(obj, L[0]), '.'.join(L[1:]))

def rec_setattr(obj, attr, value):
    if '.' not in attr:
        setattr(obj, attr, value)
    else:
        L = attr.split('.')
        rec_setattr(getattr(obj, L[0]), '.'.join(L[1:]), value)

if __name__=="__main__":
    generate_preview()




