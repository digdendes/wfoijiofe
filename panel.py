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
        
       
class VIEW3D_PT_ODCTeeth(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type="TOOLS"
    bl_category = "Dental"
    bl_label = "Tooth Restorations"
    bl_context = ""

    def draw(self, context):
        if not context.scene.odc_props.show_teeth:
            return
        sce = bpy.context.scene
        layout = self.layout
        
        #split = layout.split()

        row = layout.row()
        #row.operator("wm.url_open", text = "", icon="QUESTION").url = "https://sites.google.com/site/blenderdental/contributors"
        row.operator("opendental.start_crown_help", text = "", icon = 'QUESTION')
        row.operator("opendental.stop_help", text = "", icon = 'CANCEL')
        row = layout.row()
        row.template_list("SCENE_UL_odc_teeth","",sce, "odc_teeth", sce, "odc_tooth_index")
        
        col = row.column(align=True)
        #col.operator("opendental.tooth_lib_refresh", text = "Update Tooth Lib")
        col.operator("opendental.add_tooth_restoration", text = "Add a Tooth")
        col.operator("opendental.remove_tooth_restoration", text = "Remove a Tooth")
        col.operator("opendental.plan_restorations", text = "Plan Multiple")

        #row = layout.row()
        #row.operator("opendental.implant_inner_cylinder", text = "Implant Inner Cylinders")
        
        row = layout.row()
        row.operator("opendental.crown_report", text = "Project Report")
        
        row = layout.row()
        row.operator("opendental.center_objects", text = "Center Objects")

        row = layout.row()
        row.operator("opendental.set_master", text = "Set Master")
        
        row = layout.row()
        row.operator("opendental.set_as_prep", text = "Set Prep")
        
        row = layout.row()
        row.operator("opendental.set_opposing", text = "Set Opposing")
        
        row = layout.row()
        row.operator("opendental.set_mesial", text = "Set Mesial")
        
        row = layout.row()
        row.operator("opendental.set_distal", text = "Set Distal")
        
        row = layout.row()
        row.operator("opendental.insertion_axis", text = "Insertion Axis")
        
        row = layout.row()
        row.operator("opendental.mark_crown_margin", text = "Mark Margin")
        
        row = layout.row()
        row.operator("opendental.refine_margin", text = "Refine Margin")
        
        row = layout.row()
        row.operator("opendental.accept_margin", text = "Accept Margin")
        
        row = layout.row()
        row.operator("opendental.get_crown_form", text = "Get Crown From")
        
        if context.object and 'LAPLACIANDEFORM' in [mod.type for mod in context.object.modifiers]:
            row = layout.row()
            row.operator("opendental.flexitooth_keep", text = "FlexiTooth Keep")
        else:
            row = layout.row()
            row.operator("opendental.flexitooth", text = "FlexiTooth")
        
        if context.object and 'LATTICE' in [mod.type for mod in context.object.modifiers]:
            row = layout.row()
            row.operator("opendental.keep_shape", text = "Lattice Deform Keep")
        else:
            row = layout.row()
            row.operator("opendental.lattice_deform", text = "Lattice Deform Crown")
        
        row = layout.row()
        row.operator("opendental.seat_to_margin", text = "Seat To Margin")
        
        row = layout.row()
        row.operator("opendental.cervical_convergence", text = "Angle Cervical Convergence")
        
        row = layout.row()
        row.operator("opendental.grind_occlusion", text = "Grind Occlusion")
        
        row = layout.row()
        row.operator("opendental.grind_contacts", text = "Grind Contacts")
        
        row = layout.row()
        row.operator("opendental.calculate_inside", text = "Calculate Intaglio")
        
        row = layout.row()
        row.operator("opendental.prep_from_crown", text = "Artificial Intaglio")
        
        row = layout.row()
        row.operator("opendental.make_solid_restoration", text = "Solid Restoration")
        
        
        #row = layout.row()
        #row.operator("opendetnal.lattice_deform", text = "Place/Replace Implant")
        
class VIEW3D_PT_ODCImplants(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type="TOOLS"
    bl_category = "Dental"
    bl_label = "Implant Restorations"
    bl_context = ""
    
    def draw(self, context):
        if not context.scene.odc_props.show_implant:
            return
        sce = bpy.context.scene
        layout = self.layout
        
        
        #split = layout.split()


        #row.label(text="By Patrick Moore and others...")
        #row.operator("wm.url_open", text = "", icon="QUESTION").url = "https://sites.google.com/site/blenderdental/contributors"
        row = layout.row()
        row.operator("opendental.start_implant_help", text = "", icon = 'QUESTION')
        row.operator("opendental.stop_help", text = "", icon = 'CANCEL')
        
        row = layout.row()
        row.label(text = "Edentulous Spaces to Fill")
        row = layout.row()
        row.template_list("SCENE_UL_odc_implants","", sce, "odc_implants", sce, "odc_implant_index")
        
        col = row.column(align=True)
        col.operator("opendental.add_implant_restoration", text = "Add a Space")
        col.operator("opendental.remove_implant_restoration", text = "Remove a Space")
        col.operator("opendental.plan_restorations", text = "Plan Multiple")
        
        #if odc.odc_restricted_registration:
        row = layout.row()
        row.operator("opendental.place_implant", text = "Place/Replace Implant")
        
        row = layout.row()
        row.operator("opendental.implant_from_crown", text = "Place Implants From Crown")
        
        
        #else:
            #row = layout.row()
            #row.label(text = "Implant library not loaded :-(")
        
        row = layout.row()
        row.operator("opendental.place_guide_sleeve", text = "Place Sleeve")
        
        row = layout.row()
        row.operator("opendental.implant_guide_cylinder", text = "Place Guide Cylinder")
        
        row = layout.row()
        row.operator("opendental.implant_inner_cylinder", text = "Implant Inner Cylinders")
            
class VIEW3D_PT_ODCBridges(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type="TOOLS"
    bl_category = "Dental"
    bl_label = "Bridge Restorations"
    bl_context = ""
    
    def draw(self, context):
        if not context.scene.odc_props.show_bridge:
            return
        sce = bpy.context.scene
        layout = self.layout
        
        
        #split = layout.split()

        #row = layout.row()
        #row.label(text="By Patrick Moore and others...")
        #row.operator("wm.url_open", text = "", icon="QUESTION").url = "https://sites.google.com/site/blenderdental/contributors"
        
        row = layout.row()
        row.label(text = "Bridges")
        row = layout.row()
        row.operator("opendental.start_bridge_help", text = "", icon = 'QUESTION')
        row.operator("opendental.stop_help", text = "", icon = 'CANCEL')
        
        row = layout.row()
        row.template_list("SCENE_UL_odc_bridges","", sce, "odc_bridges", sce, "odc_bridge_index")
        
        col = row.column(align=True)
        #col.operator("opendental.add_implant_restoration", text = "Add a Space")
        col.operator("opendental.remove_bridge_restoration", text = "Remove a Bridge")
        #col.operator("opendental.plan_restorations", text = "Plan Multiple")


        row = layout.row()
        row.operator("opendental.draw_arch_curve", text = "Draw Arch Curve")
        
        row = layout.row()
        row.operator("opendental.teeth_to_arch", text = "Set Teeth on Curve")
        
        row = layout.row()
        row.operator("opendental.occlusal_scheme", text = "Occlusal Setup to Curve")
        
        row = layout.row()
        row.operator("opendental.arch_plan_keep", text = "Keep Arch Plan")
        
        row = layout.row()
        row.operator("opendental.define_bridge", text = "Plan Selected Units as Bridge")
        
        #row = layout.row()
        #row.operator("opendental.make_prebridge", text = "Make Pre Bridge")
        
        #row = layout.row()
        #row.operator("opendental.bridge_individual", text = "Bridge Individual")
        
        row = layout.row()
        row.operator("opendental.bridge_boolean", text = "Make Bridge Shell")
        
        row = layout.row()
        row.operator("opendental.solid_bridge", text = "Join Intaglios to Shell")
        
class VIEW3D_PT_ODCSplints(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type="TOOLS"
    bl_category = "Dental"
    bl_label = "Splints"
    bl_context = ""
    
    def draw(self, context):
        if not context.scene.odc_props.show_splint:
            return
        sce = bpy.context.scene
        layout = self.layout

        #split = layout.split()

        #row = layout.row()
        #row.label(text="By Patrick Moore and others...")
        #row.operator("wm.url_open", text = "", icon="QUESTION").url = "https://sites.google.com/site/blenderdental/contributors"
        
        row = layout.row()
        row.label(text = "Splints")
        row = layout.row()
        row.operator("wm.url_open", text = "", icon="INFO").url = "https://github.com/patmo141/odc_public/wiki/Splint-Basics"
        row.operator("opendental.start_guide_help", text = "", icon = 'QUESTION')
        row.operator("opendental.stop_help", text = "", icon = 'CANCEL')
        row = layout.row()
        row.template_list("SCENE_UL_odc_splints","", sce, "odc_splints", sce, "odc_splint_index")
        
        col = row.column(align=True)
        
        col.operator("opendental.add_splint", text = "Start a Splint")
        col.operator("opendental.remove_splint", text = "Remove Splint")
        
        row = layout.row()
        row.operator("import_mesh.stl", text = 'Import STL Models')
                
        row = layout.row()
        row.operator("opendental.model_set", text = "Set Model")
        
        row = layout.row()
        row.operator("opendental.splint_opposing_set", text = "Set Opposing")
        
        row = layout.row()
        row.operator("opendental.splint_mark_landmarks", text = "Set Landmarks")
        
        row = layout.row()
        row.operator("opendental.draw_occlusal_curve_max", text = "Mark Occlusal Curve Max")

        row = layout.row()
        row.operator("opendental.draw_occlusal_curve", text = "Mark Occlusal Curve Mand")
        
        
        
        row = layout.row()
        row.operator("opendental.view_silhouette_survey", text = "Survey Model (View)")
        
        row = layout.row()
        row.operator("opendental.arrow_silhouette_survey", text = "Survey Model (Arrow)")
        
        row = layout.row()
        row.label('Draw Line Method')
        row = layout.row()
        row.operator("opendental.draw_buccal_curve", text = "Mark Splint Outline")
        
        row = layout.row()
        row.operator("opendental.splint_trim_from_curve", text = "Trim Upper")
        
        #row = layout.row()
        #row.label('Paint Method')
        #row = layout.row()
        #row.operator("opendental.splint_paint_margin", text = "Paint Splint Outline")
        
        #if context.mode == 'SCULPT':
            
        #    paint_settings = sce.tool_settings.unified_paint_settings
            
        #    row = layout.row()
        #    row.prop(paint_settings, "unprojected_radius")
            
        #    brush = bpy.data.brushes['Mask']
        #    row = layout.row()
        #    row.prop(brush, "stroke_method")
            
        
        #    row = layout.row()
        #    row.operator("opendental.splint_trim_from_paint", text = "Trim Upper (Paint)")
        

        row = layout.row()
        row.label('Shell Construction')
        
        row = layout.row()
        col = row.column()
        
        col.operator("opendental.splint_offset_shell", text = "Splint Shell")
        col.operator("opendental.splint_passive_spacer", text = "Passivity Offset")
        col.operator("opendental.splint_rim_from_dual_curves", text = "Splint Flat Plane")
        col.operator("opendental.splint_join_rim", text = "Join rim to Shell")
        
        row = layout.row()
        row.label('Articulation/Mounting')
        row = layout.row()
        col = row.column()
        col.operator("opendental.generate_articulator", text = "Generate Articulator")
        #col.operator("opendental.splint_mount_articulator", text = "Mount on Articulator")
        
        row = layout.row()
        col = row.column()
        col.operator("opendental.splint_animate_articulator", text = "Generate Functional Surface")
        col.operator("opendental.splint_stop_articulator", text = "Stop Functional Surface")
        
        row = layout.row()
        col.operator("opendental.splint_subtract_surface", text = "Subtract Functional Surface")
        
        
        row = layout.row()
        row.label('Sulpt and Refinement')
        
        if context.mode == 'OBJECT':
            row = layout.row()
            row.operator("opendental.splint_start_sculpt", text = "Go to Sculpt")
        
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
        col.operator("opendental.splint_finish_booleans", text = "Finalize The Splint")
        
        
          
class VIEW3D_PT_ODCModels(bpy.types.Panel):
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
            txt = context.object.name
            row.label(text = "Please Select a Model")
            
        row = layout.row()    
        col = row.column(align=True)
            
        col.operator("opendental.enter_sculpt_paint_mask", text = "Paint Model")
        col.operator("opendental.delete_sculpt_mask", text = "Delete Painted")
        col.operator("opendental.delete_sculpt_mask_inverse", text = "Keep Only Painted")
        col.operator("opendental.delete_islands", text = "Delete Small Parts")
        
        if context.mode == 'SCULPT':
            col.operator("object.mode_set", text = 'Finish Sculpt')
                
        #col.operator("opendental.simple_offset_surface", text = "Simple Offset")
        col.operator("opendental.simple_base", text = "Simple Base")            
      

def register():
    bpy.utils.register_class(SCENE_UL_odc_teeth)
    bpy.utils.register_class(SCENE_UL_odc_implants)
    bpy.utils.register_class(SCENE_UL_odc_bridges)
    bpy.utils.register_class(SCENE_UL_odc_splints)
    bpy.utils.register_class(VIEW3D_PT_ODCSettings)
    
    bpy.utils.register_class(VIEW3D_PT_ODCSplints)
    
    #bpy.utils.register_class(VIEW3D_PT_ODCDentures)
    bpy.utils.register_class(VIEW3D_PT_ODCModels)
    
    #bpy.utils.register_module(__name__)
    
def unregister():
    bpy.utils.unregister_class(SCENE_UL_odc_teeth)
    bpy.utils.unregister_class(SCENE_UL_odc_implants)
    bpy.utils.unregister_class(SCENE_UL_odc_bridges)
    bpy.utils.unregister_class(SCENE_UL_odc_splints)
    
    bpy.utils.unregister_class(VIEW3D_PT_ODCSettings)
    
    bpy.utils.unregister_class(VIEW3D_PT_ODCSplints)
    
    #bpy.utils.unregister_class(VIEW3D_PT_ODCDentures)
    bpy.utils.unregister_class(VIEW3D_PT_ODCModels)
    
if __name__ == "__main__":
    register()