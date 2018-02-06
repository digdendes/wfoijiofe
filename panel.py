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
            
class VIEW3D_PT_D3SplintAssitant(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type="TOOLS"
    bl_category = "Dental"
    bl_label = "D3Tool Assistant Panel"
    bl_context = ""

    def draw(self, context):
        sce = bpy.context.scene
        layout = self.layout
        
        #split = layout.split()
        row = layout.row()

        row.operator("wm.url_open", text = "Wiki", icon="INFO").url = "https://d3tool.com/d3splint-membership-videos/"
        row.operator("wm.url_open", text = "Errors", icon="ERROR").url = "https://github.com/patmo141/"
        row.operator("wm.url_open", text = "Forum", icon="QUESTION").url = "https://www.facebook.com/groups/939777786197766"
        

        row = layout.row()
        row.label(text = "Save/Checkpoints")
        row = layout.row()
        col = row.column()
        col.operator("wm.save_as_mainfile", text = "Save").copy = False
        col.operator("wm.splint_saveincremental", text = "Save Checkpoint")
        
        
   
class VIEW3D_PT_D3Splints(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type="TOOLS"
    bl_category = "Dental"
    bl_label = "Splints"
    bl_context = ""
    
    def draw(self, context):

        sce = bpy.context.scene
        layout = self.layout
        prefs = get_settings()
        
        if len(sce.odc_splints):
            n = sce.odc_splint_index
            splint = sce.odc_splints[n]
        else:
            splint = None
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
        #row = layout.row()
        #row.template_list("SCENE_UL_odc_splints","", sce, "odc_splints", sce, "odc_splint_index")
        
        
        box = layout.box()
        box.label('Splint Properties')
        
        if not hasattr(context.scene , "odc_splints"):
            col = box.column()
            col.label('ERROR with addon installation', icon = 'ERROR')
            return
        elif len(context.scene.odc_splints) == 0:
            row = box.row()
            col = row.column()
            col.label('Jaw Type')
            #col = row.column()
            col.prop(prefs, 'default_jaw_type', text = '')
            col.prop(prefs, 'default_workflow_type', text = '')
        else:
            n = context.scene.odc_splint_index
            splint =context.scene.odc_splints[n]
            
            row = box.row()
            col = row.column()
            col.label('Jaw Type')
            #col = row.column()
            col.prop(splint, 'jaw_type', text = '')
            col.prop(splint, 'workflow_type', text = '')
            
        row = layout.row()
        row.operator("import_mesh.stl", text = 'Import STL Models')
                
        
        if splint and splint.model_set: 
            ico = 'CHECKBOX_HLT'
        else:
            ico = 'CHECKBOX_DEHLT'
        row = layout.row()
        row.operator("d3splint.pick_model", text = "Set Splint Model", icon = ico)
        
        if not splint: return
        if splint and splint.opposing_set: 
            ico = 'CHECKBOX_HLT'
        else:
            ico = 'CHECKBOX_DEHLT'
        row = layout.row()
        row.operator("d3splint.pick_opposing", text = "Set Opposing",icon = ico)
        
        if splint and splint.landmarks_set: 
            ico = 'CHECKBOX_HLT'
        else:
            ico = 'CHECKBOX_DEHLT'
        row = layout.row()
        row.operator("d3splint.splint_mark_landmarks", text = "Set Landmarks", icon = ico)
        
        
        row = layout.row()
        row.label('Initial Mounting and Articulation')
        row = layout.row()
        col = row.column()
        col.operator("d3splint.generate_articulator", text = "Set Initial Values")
        #col.operator("d3splint.splint_mount_articulator", text = "Mount on Articulator")
    
        row = layout.row()
        col = row.column()
    
        col.operator("d3splint.open_pin_on_articulator", text = "Change Pin Setting" )
        col.operator("d3splint.recover_mounting_relationship", text = "Recover Mounting" )
        
        row = layout.row()
        row.label('Survey and HoC')
        
        if splint and splint.curve_max: 
            ico = 'CHECKBOX_HLT'
        else:
            ico = 'CHECKBOX_DEHLT'
        row = layout.row()
        row.operator("d3splint.draw_occlusal_curve_max", text = "Mark Max Curve", icon = ico)

        if splint and splint.curve_mand: 
            ico = 'CHECKBOX_HLT'
        else:
            ico = 'CHECKBOX_DEHLT'
        row = layout.row()
        row.operator("d3splint.draw_occlusal_curve_mand", text = "Mark Mand Curve", icon = ico)
        
         
        row = layout.row()
        col = row.column()
        
        if splint and splint.insertion_path: 
            ico = 'CHECKBOX_HLT'
        else:
            ico = 'CHECKBOX_DEHLT'
            
        col.operator("d3splint.view_silhouette_survey", text = "Survey Model (View)", icon = ico)
        col.operator("d3splint.arrow_silhouette_survey", text = "Survey Model (Arrow)")
        
        row = layout.row()
        row.label('Splint Boundaries')
        
        if splint and splint.splint_outline: 
            ico = 'CHECKBOX_HLT'
        else:
            ico = 'CHECKBOX_DEHLT'
        row = layout.row()
        row.operator("d3splint.draw_splint_margin", text = "Mark Splint Margin", icon = ico)
        
        if splint and splint.trim_upper: 
            ico = 'CHECKBOX_HLT'
        else:
            ico = 'CHECKBOX_DEHLT'
        row = layout.row()
        row.operator("d3splint.splint_model_trim", text = "Trim Model", icon = ico)
        
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
        
        if splint and splint.splint_shell: 
            ico = 'CHECKBOX_HLT'
        else:
            ico = 'CHECKBOX_DEHLT'
        col.operator("d3splint.splint_offset_shell", text = "Splint Shell", icon = ico)
        
        
        if splint.workflow_type == 'FREEFORM':
            row = layout.row()
            row.label('Virtual Wax Tools')
            
            row = layout.row()
            col = row.column()
            if splint and "MakeRim" in splint.ops_string: 
                ico = 'FILE_TICK'
            else:
                ico = 'NONE'
            col.operator("d3splint.splint_rim_from_dual_curves", text = "Splint Wax Rim", icon = ico)
            
            if splint and "JoinRim" in splint.ops_string: 
                ico = 'FILE_TICK'
            else:
                ico = 'NONE'
            col.operator("d3splint.splint_join_rim", text = "Fuse Rim to Shell", icon = ico)
            
            row = layout.row()
            col = row.column()
            col.operator("d3splint.draw_meta_scaffold_curve", text = 'Draw Wax Curve')
            col.operator("d3splint.virtual_wax_on_curve", text = 'Add Virtual Wax')
            col.operator("d3splint.splint_join_meta_shell", text = 'Fuse Virtual Wax')
            
            row = layout.row()
            col = row.column()
            col.operator("d3splint.anterior_deprogrammer_element", text = 'Anterior Deprogrammer Ramp')
            col.operator("d3splint.splint_join_deprogrammer", text = 'Fuse Deprogrammer')
        
        if splint.workflow_type == 'DEPROGRAMMER':
            row = layout.row()
            col = row.column()
            col.operator("d3splint.anterior_deprogrammer_element", text = 'Anterior Deprogrammer Ramp')
            col.operator("d3splint.splint_join_deprogrammer", text = 'Fuse Deprogrammer')
            
            
        if splint.workflow_type in {'FLAT_PLANE', 'MICHIGAN'}:
            
            row = layout.row()
            col = row.column()
            if splint and "MakeRim" in splint.ops_string: 
                ico = 'FILE_TICK'
            else:
                ico = 'NONE'
            
            if splint.workflow_type == 'FLAT_PLANE':
                col.operator("d3splint.splint_rim_from_dual_curves", text = "Splint Wax Rim", icon = ico).ap_segment = 'POSTERIOR_ONLY'
            
            elif splint.workflow_type == 'MICHIGAN':
                col.operator("d3splint.splint_rim_from_dual_curves", text = "Splint Wax Rim", icon = ico).ap_segment = 'FULL_RIM'
            
            if splint and "JoinRim" in splint.ops_string: 
                ico = 'FILE_TICK'
            else:
                ico = 'NONE'
            col.operator("d3splint.splint_join_rim", text = "Fuse Rim to Shell", icon = ico)
            
            row = layout.row()
            row.label('Auto Refinement Tools')
            row = layout.row()
            col = row.column()
            col.operator("d3splint.meta_blockout_shell", text = 'Blockout Large Concavities')
            col.operator("d3splint.auto_sculpt_concavities", text = 'Auto Sculpt Concavities')
        
            row = layout.row()
            row.label('Manual Flat Plane')
            row = layout.row()
            col = row.column()
            col.operator("d3splint.splint_manual_flat_plane", text = "Mark Opposing Contacts")
            col.operator("d3splint.subtract_posterior_surface", text = 'Subtract Posterior Plane')
        
            row = layout.row()
            row.label('Create Low Value Surface')
            
            row = layout.row()
            col = row.column()
            col.operator("d3splint.splint_animate_articulator", text = "Generate Surface").force_full = True
            col.operator("d3splint.splint_subtract_surface", text = "Subtract Surface")
        
        if splint.workflow_type == 'MICHIGAN':
            
            row = layout.row()
            row.label('Ramp and Guidance')
            
            row = layout.row()
            col = row.column()
            
            col.operator("d3splint.generate_articulator", text = "Set Steeper Articulator Values")
            
            col.operator("d3splint.splint_rim_from_dual_curves", text = "Add Anterior Ramp").ap_segment = 'ANTERIOR_ONLY'
            
            
            col.operator("d3splint.splint_join_rim", text = "Fuse Anterior Rim")
            col.operator("d3splint.splint_animate_articulator", text = "Generate New Surface").force_full = True
            col.operator("d3splint.splint_subtract_surface", text = "Subtract Surface")
            
            
        #row = layout.row()
        #row.prop(prefs, "show_occlusal_mod")
        #if get_settings().show_occlusal_mod:
        #    row = layout.row()
        #    row.label('Occlusal Modification [BETA!]')
        
        #    row = layout.row()
        #    col = row.column()
        #    col.operator("d3splint.convexify_lower", text = "Make Convex (FAST)")
        #    col.operator("d3splint.convexify_lower", text = "Make Convex (SLOW)").method1 = 'CARVE'
        #    col.operator("d3splint.join_convex_lower", text = "Join Convex Elements")
        
        if splint.workflow_type == 'FREEFORM':    
            row = layout.row()
            row.label('Articulation/Mounting/Occlusion')
            
            row = layout.row()
            row.operator("d3splint.subtract_opposing_model", text = 'Grind MIP')
            row = layout.row()
            if splint and "GenArticulator" in splint.ops_string: 
                ico = 'FILE_TICK'
            else:
                ico = 'NONE'
            col = row.column()
            col.operator("d3splint.generate_articulator", text = "Generate Articulator", icon = ico)
            #col.operator("d3splint.splint_mount_articulator", text = "Mount on Articulator")
            
            row = layout.row()
            col = row.column()
            
            col.operator("d3splint.open_pin_on_articulator", text = "Change Pin Setting" )
            col.operator("d3splint.recover_mounting_relationship", text = "Recover Mounting" )
            col.operator("d3splint.articulator_mode_set", text = "Choose Articulator Motion")
            
            if splint and "AnimateArticulator" in splint.ops_string: 
                ico = 'FILE_TICK'
            else:
                ico = 'NONE'
                
            col.operator("d3splint.splint_animate_articulator", text = "Generate Functional Surface", icon = ico)
            col.operator("d3splint.stop_surface_calculation", text = "Stop Surface Calculation")
            col.operator("d3splint.start_surface_calculation", text = "Re-Start Surface Calculation")
            col.operator("d3splint.reset_functional_surface", text = "Re-set Functional Surface")
            if splint and "SubtractSurface" in splint.ops_string: 
                ico = 'FILE_TICK'
            else:
                ico = 'NONE'
            
            col.operator("d3splint.splint_subtract_surface", text = "Subtract Functional Surface", icon = ico)
        
        
        row = layout.row()
        row.label('Sculpt and Refinement')
        
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
            row.operator("object.mode_set", text = 'Finish Paint/Sculpt')
            
        #    row = layout.row()
        #    row.prop(paint_settings, "unprojected_radius")
            
        #    brush = bpy.data.brushes['Mask']
        #    row = layout.row()
        #    row.prop(brush, "stroke_method")
        
        
        row = layout.row()
        row.label('Fit and Finalization')
        
        if splint and splint.passive_offset: 
            ico = 'CHECKBOX_HLT'
        else:
            ico = 'CHECKBOX_DEHLT'
        col.operator("d3splint.splint_passive_spacer", text = "Passivity Offset", icon = ico)
        
        if splint and splint.remove_undercuts: 
            ico = 'CHECKBOX_HLT'
        else:
            ico = 'CHECKBOX_DEHLT'
        col.operator("d3splint.meta_blockout_trimmed_model2", text = "Undercut Blockout", icon = ico)
        
        row = layout.row()
        if splint and splint.finalize_splint: 
            ico = 'CHECKBOX_HLT'
        else:
            ico = 'CHECKBOX_DEHLT'
        col = row.column()
        col.operator("d3splint.splint_finish_booleans2", text = "Finalize The Splint", icon = ico)
        #col.operator("d3guard.splint_cork_boolean", text = "Finalize Splint (CORK EGINE)")
        col.operator("d3splint.export_splint_stl", text = "Export Splint STL")
        
        row = layout.row()
        row.label('Start Again on Opposing?')
        
        row = layout.row()
        col = row.column()
        col.operator("d3splint.plan_splint_on_opposing", text = "Plan Opposing Splint")
        
          
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
        row.label('Sculpt/Paint Mode Tools')
        row = layout.row()
        col = row.column()    
        col.operator("d3splint.enter_sculpt_paint_mask", text = "Paint Model")
        col.operator("paint.mask_flood_fill", text = "Clear Paint").mode = 'VALUE'
        col.operator("d3splint.delete_sculpt_mask", text = "Delete Painted") #defaults to .value = 0
        col.operator("d3splint.close_paint_hole", text = 'Close Paint Hole')
        col.operator("d3splint.delete_sculpt_mask_inverse", text = "Keep Only Painted")
        col.operator("d3splint.delete_islands", text = "Delete Small Parts")
        
        
        if context.mode == 'SCULPT':
            col.operator("object.mode_set", text = 'Finish Sculpt/Paint')
        
        row = layout.row()
        row.label('Object Mode Operators')
        row = layout.row()
        col = row.column()      
        #col.operator("d3splint.simple_offset_surface", text = "Simple Offset")
        col.operator("d3splint.ragged_edges", text = "Remove Ragged Edges")
        col.operator("d3splint.simple_base", text = "Simple Base")            
        col.operator("d3splint.model_wall_thicken", text = 'Hollow Model')
        col.operator("d3splint.model_wall_thicken2", text = 'Hollow Model2')
        col.operator("d3tool.model_vertical_base", text = 'Vertical Base')
        
        
class VIEW3D_PT_D3SplintModelText(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type="TOOLS"
    bl_category = "Dental"
    bl_label = "Model Text Embossing"
    bl_context = ""
    
    def draw(self, context):
        sce = bpy.context.scene
        layout = self.layout
        
        row = layout.row()
        row.label(text = "Model Labelling")
        #row.operator("wm.url_open", text = "", icon="INFO").url = "https://github.com/patmo141/odc_public/wiki"
          
        if context.object != None:
            row = layout.row()
            txt = context.object.name
            row.label(text = "Selected Model: " + txt)
        
        else:
            row = layout.row()
            row.label(text = "Please Select a Model")
            
            row = layout.row()
            row.label(text = 'SVG Image Workflow')
            
        row = layout.row()
        row.operator("d3splint.place_text_on_model", text = 'Place Text at Cursor')
        row = layout.row()
        row.operator("d3tool.remesh_and_emboss_text", text = 'Emboss Text onto Object')
        
        
def register():
    bpy.utils.register_class(SCENE_UL_odc_teeth)
    bpy.utils.register_class(SCENE_UL_odc_implants)
    bpy.utils.register_class(SCENE_UL_odc_bridges)
    bpy.utils.register_class(SCENE_UL_odc_splints)
    
    bpy.utils.register_class(VIEW3D_PT_D3SplintAssitant)
    bpy.utils.register_class(VIEW3D_PT_D3Splints)
    bpy.utils.register_class(VIEW3D_PT_D3SplintModels)
    bpy.utils.register_class(VIEW3D_PT_D3SplintModelText)
    
    #bpy.utils.register_module(__name__)
    
def unregister():
    bpy.utils.unregister_class(SCENE_UL_odc_teeth)
    bpy.utils.unregister_class(SCENE_UL_odc_implants)
    bpy.utils.unregister_class(SCENE_UL_odc_bridges)
    bpy.utils.unregister_class(SCENE_UL_odc_splints)
    
    
    bpy.utils.unregister_class(VIEW3D_PT_D3Splints)
    
    #bpy.utils.unregister_class(VIEW3D_PT_ODCDentures)
    bpy.utils.unregister_class(VIEW3D_PT_D3SplintModels)
    bpy.utils.unregister_class(VIEW3D_PT_D3SplintModelText)
if __name__ == "__main__":
    register()