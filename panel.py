import bpy
import os
from odcutils import get_settings

class SCENE_UL_odc_teeth(bpy.types.UIList):
    # The draw_item function is called for each item of the collection that is visible in the list.
    #   data is the RNA object containing the collection,
    #   item is the current drawn item of the collection,
    #   icon is the "computed" icon for the item (as an integer, because some objects like materials or textures
    #   have custom icons ID, which are not available as enum items).
    #   active_data is the RNA object containing the active property for the collection (i.e. integer pointing to the
    #   active item of the collection).
    #   active_propname is the name of the active property (use 'getattr(active_data, active_propname)').
    #   index is index of the current item in the collection.
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        sce = data
        tooth = item
        # draw_item must handle the three layout types... Usually 'DEFAULT' and 'COMPACT' can share the same code.
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # You should always start your row layout by a label (icon + text), this will also make the row easily
            # selectable in the list!
            # We use icon_value of label, as our given icon is an integer value, not an enum ID.
            layout.label(tooth.name)
            # And now we can add other UI stuff...
            # Here, we add nodes info if this material uses (old!) shading nodes.

        # 'GRID' layout type should be as compact as possible (typically a single icon!).
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label("", icon_value="NODE")
            
class SCENE_UL_odc_implants(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        sce = data
        implant = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            
            layout.label(implant.name)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label("", icon_value="NODE")
            
class SCENE_UL_odc_bridges(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        sce = data
        bridge = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            
            layout.label(bridge.name)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label("", icon_value="NODE")

class SCENE_UL_odc_splints(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        sce = data
        splint = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            
            layout.label(splint.name)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label("", icon_value="NODE")
            
class VIEW3D_PT_ODCSettings(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type="TOOLS"
    bl_category = "Dental"
    bl_label = "D3Tool Control Panel"
    bl_context = ""

    def draw(self, context):
        sce = bpy.context.scene
        layout = self.layout
        
        #split = layout.split()
        row = layout.row()

        row.operator("wm.url_open", text = "Wiki", icon="INFO").url = "https://github.com/patmo141/"
        row.operator("wm.url_open", text = "Errors", icon="ERROR").url = "https://github.com/patmo141/"
        row.operator("wm.url_open", text = "Forum", icon="QUESTION").url = "https://www.facebook.com/"
        
      
class VIEW3D_PT_D3Splints(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type="TOOLS"
    bl_category = "Dental"
    bl_label = "Splints"
    bl_context = ""
    
    def draw(self, context):

        sce = bpy.context.scene
        layout = self.layout

        #split = layout.split()

        #row = layout.row()
        #row.label(text="By Patrick Moore and others...")
        #row.operator("wm.url_open", text = "", icon="QUESTION").url = "https://sites.google.com/site/blenderdental/contributors"
        
        row = layout.row()
        row.label(text = "Splints")
        row = layout.row()
        row.operator("wm.url_open", text = "", icon="INFO").url = "www.d3tool.com"
        #row.operator("d3splint.start_guide_help", text = "", icon = 'QUESTION')
        #row.operator("d3splint.stop_help", text = "", icon = 'CANCEL')
        row = layout.row()
        row.template_list("SCENE_UL_odc_splints","", sce, "odc_splints", sce, "odc_splint_index")
        
        row = layout.row()
        row.operator("import_mesh.stl", text = 'Import STL Models')
                
        row = layout.row()
        row.operator("d3splint.pick_model", text = "Set Splint Model")
        
        row = layout.row()
        row.operator("d3splint.pick_opposing", text = "Set Opposing")
        
        row = layout.row()
        row.operator("d3splint.splint_mark_landmarks", text = "Set Landmarks")
        
        row = layout.row()
        row.operator("d3splint.draw_occlusal_curve_max", text = "Mark Occlusal Curve Max")

        row = layout.row()
        row.operator("d3splint.draw_occlusal_curve", text = "Mark Occlusal Curve Mand")
        
        
        
        row = layout.row()
        row.operator("d3splint.view_silhouette_survey", text = "Survey Model (View)")
        
        row = layout.row()
        row.operator("d3splint.arrow_silhouette_survey", text = "Survey Model (Arrow)")
        
        row = layout.row()
        row.label('Draw Line Method')
        row = layout.row()
        row.operator("d3splint.draw_buccal_curve", text = "Mark Splint Outline")
        
        row = layout.row()
        row.operator("d3splint.splint_trim_from_curve", text = "Trim Upper")
        
        #row = layout.row()
        #row.label('Paint Method')
        #row = layout.row()
        #row.operator("d3splint.splint_paint_margin", text = "Paint Splint Outline")
        
        #if context.mode == 'SCULPT':
            
        #    paint_settings = sce.tool_settings.unified_paint_settings
            
        #    row = layout.row()
        #    row.prop(paint_settings, "unprojected_radius")
            
        #    brush = bpy.data.brushes['Mask']
        #    row = layout.row()
        #    row.prop(brush, "stroke_method")
            
        
        #    row = layout.row()
        #    row.operator("d3splint.splint_trim_from_paint", text = "Trim Upper (Paint)")
        

        row = layout.row()
        row.label('Shell Construction')
        
        row = layout.row()
        col = row.column()
        
        col.operator("d3splint.splint_offset_shell", text = "Splint Shell")
        col.operator("d3splint.splint_passive_spacer", text = "Passivity Offset")
        col.operator("d3splint.splint_rim_from_dual_curves", text = "Splint Flat Plane")
        col.operator("d3splint.splint_join_rim", text = "Join rim to Shell")
        
        row = layout.row()
        row.label('Articulation/Mounting')
        row = layout.row()
        col = row.column()
        col.operator("d3splint.generate_articulator", text = "Generate Articulator")
        #col.operator("d3splint.splint_mount_articulator", text = "Mount on Articulator")
        
        row = layout.row()
        col = row.column()
        col.operator("d3splint.splint_animate_articulator", text = "Generate Functional Surface")
        col.operator("d3splint.splint_stop_articulator", text = "Stop Functional Surface")
        
        row = layout.row()
        col.operator("d3splint.splint_subtract_surface", text = "Subtract Functional Surface")
        
        
        row = layout.row()
        row.label('Sulpt and Refinement')
        
        if context.mode == 'OBJECT':
            row = layout.row()
            row.operator("d3splint.splint_start_sculpt", text = "Go to Sculpt")
        
        if context.mode == 'SCULPT': #TODO other checks for sculpt object and stuff
            
            paint_settings = sce.tool_settings.unified_paint_settings
            sculpt_settings = context.tool_settings.sculpt
            row= layout.row()
            col = row.column()
            col.template_ID_preview(sculpt_settings, "brush", new="brush.add", rows=3, cols=8)
            
            
            brush = sculpt_settings.brush
            row = layout.row()
            row.prop(brush, "stroke_method")
        
            
            row = layout.row()
            row.operator("object.mode_set", text = 'Finish Sculpt')
            
        #    row = layout.row()
        #    row.prop(paint_settings, "unprojected_radius")
            
        #    brush = bpy.data.brushes['Mask']
        #    row = layout.row()
        #    row.prop(brush, "stroke_method")
        
        
        row = layout.row()
        row.label('Finalize Steps')
        
        row = layout.row()
        col = row.column()
        col.operator("d3splint.splint_finish_booleans", text = "Finalize The Splint")
        
        
          
class VIEW3D_PT_D3SplintModels(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type="TOOLS"
    bl_category = "Dental"
    bl_label = "Model Operations"
    bl_context = ""
    
    def draw(self, context):
        sce = bpy.context.scene
        layout = self.layout
        
        row = layout.row()
        row.label(text = "Model Operators")
        row.operator("wm.url_open", text = "", icon="INFO").url = "https://github.com/patmo141/odc_public/wiki"
          
        if context.object != None:
            row = layout.row()
            txt = context.object.name
            row.label(text = "Selected Model: " + txt)
        
        else:
            row = layout.row()
            row.label(text = "Please Select a Model")
            
        row = layout.row()    
        col = row.column(align=True)
            
        col.operator("d3splint.enter_sculpt_paint_mask", text = "Paint Model")
        col.operator("d3splint.delete_sculpt_mask", text = "Delete Painted")
        col.operator("d3splint.delete_sculpt_mask_inverse", text = "Keep Only Painted")
        col.operator("d3splint.delete_islands", text = "Delete Small Parts")
        
        if context.mode == 'SCULPT':
            col.operator("object.mode_set", text = 'Finish Sculpt')
                
        #col.operator("d3splint.simple_offset_surface", text = "Simple Offset")
        col.operator("d3splint.simple_base", text = "Simple Base")            
      

def register():
    bpy.utils.register_class(SCENE_UL_odc_teeth)
    bpy.utils.register_class(SCENE_UL_odc_implants)
    bpy.utils.register_class(SCENE_UL_odc_bridges)
    bpy.utils.register_class(SCENE_UL_odc_splints)
    bpy.utils.register_class(VIEW3D_PT_ODCSettings)
    
    bpy.utils.register_class(VIEW3D_PT_D3Splints)
    bpy.utils.register_class(VIEW3D_PT_D3SplintModels)
    
    #bpy.utils.register_module(__name__)
    
def unregister():
    bpy.utils.unregister_class(SCENE_UL_odc_teeth)
    bpy.utils.unregister_class(SCENE_UL_odc_implants)
    bpy.utils.unregister_class(SCENE_UL_odc_bridges)
    bpy.utils.unregister_class(SCENE_UL_odc_splints)
    
    bpy.utils.unregister_class(VIEW3D_PT_ODCSettings)
    
    bpy.utils.unregister_class(VIEW3D_PT_D3Splints)
    
    #bpy.utils.unregister_class(VIEW3D_PT_ODCDentures)
    bpy.utils.unregister_class(VIEW3D_PT_D3SplintModels)
    
if __name__ == "__main__":
    register()