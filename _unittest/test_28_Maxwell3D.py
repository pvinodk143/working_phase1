# Setup paths for module imports
import os
import tempfile

from _unittest.conftest import BasisTest
from _unittest.conftest import desktop_version
from _unittest.conftest import local_path
from pyaedt import Maxwell3d
from pyaedt.generic.constants import SOLUTIONS
from pyaedt.generic.general_methods import generate_unique_name

try:
    import pytest
except ImportError:
    import _unittest_ironpython.conf_unittest as pytest

test_project_name = "eddy"


class TestClass(BasisTest, object):
    def setup_class(self):
        BasisTest.my_setup(self)
        self.aedtapp = BasisTest.add_app(self, application=Maxwell3d, solution_type="EddyCurrent")
        core_loss_file = "PlanarTransformer.aedt"
        example_project = os.path.join(local_path, "example_models", core_loss_file)
        self.file_path = self.local_scratch.copyfile(example_project)

    def teardown_class(self):
        BasisTest.my_teardown(self)

    def test_01_create_primitive(self):
        self.aedtapp.modeler.model_units = "mm"

        plate_pos = self.aedtapp.modeler.Position(0, 0, 0)
        hole_pos = self.aedtapp.modeler.Position(18, 18, 0)
        # Create plate with hole
        plate = self.aedtapp.modeler.create_box(plate_pos, [294, 294, 19], name="Plate")  # All positions in model units
        hole = self.aedtapp.modeler.create_box(hole_pos, [108, 108, 19], name="Hole")  # All positions in model units
        self.aedtapp.modeler.subtract([plate], [hole])
        plate.material_name = "aluminum"
        assert plate.solve_inside
        assert plate.material_name == "aluminum"

    def test_02_create_coil(self):
        center_hole = self.aedtapp.modeler.Position(119, 25, 49)
        center_coil = self.aedtapp.modeler.Position(94, 0, 49)
        coil_hole = self.aedtapp.modeler.create_box(
            center_hole, [150, 150, 100], name="Coil_Hole"
        )  # All positions in model units
        coil = self.aedtapp.modeler.create_box(
            center_coil, [200, 200, 100], name="Coil"
        )  # All positions in model units
        self.aedtapp.modeler.subtract([coil], [coil_hole])
        coil.material_name = "Copper"
        coil.solve_inside = True
        p_coil = self.aedtapp.post.volumetric_loss("Coil")
        assert type(p_coil) is str

    def test_03_coordinate_system(self):
        assert self.aedtapp.modeler.create_coordinate_system([200, 100, 0], mode="view", view="XY", name="Coil_CS")

    def test_04_coil_terminal(self):
        self.aedtapp.modeler.section(["Coil"], self.aedtapp.PLANE.ZX)
        self.aedtapp.modeler.separate_bodies(["Coil_Section1"])
        self.aedtapp.modeler.delete("Coil_Section1_Separate1")
        assert self.aedtapp.assign_current(["Coil_Section1"], amplitude=2472)
        self.aedtapp.solution_type = "Magnetostatic"
        volt = self.aedtapp.assign_voltage(self.aedtapp.modeler["Coil_Section1"].faces[0].id, amplitude=1)
        cur2 = self.aedtapp.assign_current(["Coil_Section1"], amplitude=212)
        assert cur2
        assert cur2.delete()
        assert volt
        assert volt.delete()
        self.aedtapp.solution_type = "EddyCurrent"

    def test_05_winding(self):
        face_id = self.aedtapp.modeler["Coil_Section1"].faces[0].id
        assert self.aedtapp.assign_winding(face_id)
        bounds = self.aedtapp.assign_winding(current_value=20e-3, coil_terminals=face_id)
        assert bounds
        bounds = self.aedtapp.assign_winding(current_value="20e-3A", coil_terminals=face_id)
        assert bounds
        bounds = self.aedtapp.assign_winding(res="1ohm", coil_terminals=face_id)
        assert bounds
        bounds = self.aedtapp.assign_winding(ind="1H", coil_terminals=face_id)
        assert bounds
        bounds = self.aedtapp.assign_winding(voltage="10V", coil_terminals=face_id)
        assert bounds
        bounds_name = generate_unique_name("Winding")
        bounds = self.aedtapp.assign_winding(coil_terminals=face_id, name=bounds_name)
        assert bounds_name == bounds.name

    def test_05a_assign_coil(self):
        face_id = self.aedtapp.modeler["Coil_Section1"].faces[0].id
        bound = self.aedtapp.assign_coil(input_object=face_id)
        assert bound
        polarity = "Positive"
        bound = self.aedtapp.assign_coil(input_object=face_id, polarity=polarity)
        assert not bound.props["Point out of terminal"]
        polarity = "Negative"
        bound = self.aedtapp.assign_coil(input_object=face_id, polarity=polarity)
        assert bound.props["Point out of terminal"]
        bound_name = generate_unique_name("Coil")
        bound = self.aedtapp.assign_coil(input_object=face_id, name=bound_name)
        assert bound_name == bound.name

    def test_05_draw_region(self):
        assert self.aedtapp.modeler.create_air_region(*[300] * 6)

    def test_06_eddycurrent(self):
        assert self.aedtapp.eddy_effects_on(["Plate"], activate_eddy_effects=True)
        oModule = self.aedtapp.odesign.GetModule("BoundarySetup")
        assert oModule.GetEddyEffect("Plate")
        assert oModule.GetDisplacementCurrent("Plate")
        self.aedtapp.eddy_effects_on(["Plate"], activate_eddy_effects=False)
        assert not oModule.GetEddyEffect("Plate")
        assert not oModule.GetDisplacementCurrent("Plate")

    def test_07a_setup(self):
        adaptive_frequency = "200Hz"
        Setup = self.aedtapp.create_setup()
        Setup.props["MaximumPasses"] = 12
        Setup.props["MinimumPasses"] = 2
        Setup.props["MinimumConvergedPasses"] = 1
        Setup.props["PercentRefinement"] = 30
        Setup.props["Frequency"] = adaptive_frequency
        dc_freq = 0.1
        stop_freq = 10
        count = 1
        assert Setup.add_eddy_current_sweep("LinearStep", dc_freq, stop_freq, count, clear=True)
        assert isinstance(Setup.props["SweepRanges"]["Subrange"], dict)
        assert Setup.add_eddy_current_sweep("LinearCount", dc_freq, stop_freq, count, clear=False)
        assert isinstance(Setup.props["SweepRanges"]["Subrange"], list)

        assert Setup.update()
        assert Setup.enable_expression_cache(["CoreLoss"], "Fields", "Phase='0deg' ", True)
        assert Setup.disable()
        assert Setup.enable()
        assert self.aedtapp.setup_ctrlprog(Setup.name)

    def test_07b_create_parametrics(self):
        self.aedtapp["w1"] = "10mm"
        self.aedtapp["w2"] = "2mm"
        setup1 = self.aedtapp.parametrics.add("w1", 0.1, 20, 0.2, "LinearStep")
        assert setup1
        expression = "re(FluxLinkage(" + self.aedtapp.excitations[2] + "))"
        assert setup1.add_calculation(
            calculation=expression,
            ranges={"Freq": "200Hz"},
            report_type="EddyCurrent",
            solution=self.aedtapp.existing_analysis_sweeps[0],
        )

    def test_08_setup_ctrlprog_with_file(self):
        transient_setup = self.aedtapp.create_setup()
        transient_setup.props["MaximumPasses"] = 12
        transient_setup.props["MinimumPasses"] = 2
        transient_setup.props["MinimumConvergedPasses"] = 1
        transient_setup.props["PercentRefinement"] = 30
        transient_setup.props["Frequency"] = "200Hz"
        transient_setup.update()
        transient_setup.enable_expression_cache(["CoreLoss"], "Fields", "Phase='0deg' ", True)

        # Test the creation of the control program file
        with tempfile.TemporaryFile("w+") as fp:
            assert self.aedtapp.setup_ctrlprog(transient_setup.name, file_str=fp.name)

    def test_22_create_length_mesh(self):
        assert self.aedtapp.mesh.assign_length_mesh(["Plate"])

    def test_23_create_skin_depth(self):
        assert self.aedtapp.mesh.assign_skin_depth(["Plate"], "1mm")

    def test_24_create_curvilinear(self):
        assert self.aedtapp.mesh.assign_curvilinear_elements(["Coil"], "1mm")

    def test_24_create_edge_cut(self):
        assert self.aedtapp.mesh.assign_edge_cut(["Coil"])

    def test_24_density_control(self):
        assert self.aedtapp.mesh.assign_density_control(["Coil"], maxelementlength="2mm", layerNum="3")

    def test_24_density_control(self):
        assert self.aedtapp.mesh.assign_rotational_layer(["Coil"])

    def test_25_assign_initial_mesh(self):
        assert self.aedtapp.mesh.assign_initial_mesh_from_slider(4)

    def test_26_create_udp(self):
        my_udpPairs = []
        mypair = ["DiaGap", "102mm"]
        my_udpPairs.append(mypair)
        mypair = ["Length", "100mm"]
        my_udpPairs.append(mypair)
        mypair = ["Poles", "8"]
        my_udpPairs.append(mypair)
        mypair = ["EmbraceTip", "0.29999999999999999"]
        my_udpPairs.append(mypair)
        mypair = ["EmbraceRoot", "1.2"]
        my_udpPairs.append(mypair)
        mypair = ["ThickTip", "5mm"]
        my_udpPairs.append(mypair)
        mypair = ["ThickRoot", "10mm"]
        my_udpPairs.append(mypair)
        mypair = ["ThickShoe", "8mm"]
        my_udpPairs.append(mypair)
        mypair = ["DepthSlot", "12mm"]
        my_udpPairs.append(mypair)
        mypair = ["ThickYoke", "10mm"]
        my_udpPairs.append(mypair)
        mypair = ["LengthPole", "90mm"]
        my_udpPairs.append(mypair)
        mypair = ["LengthMag", "0mm"]
        my_udpPairs.append(mypair)
        mypair = ["SegAngle", "5deg"]
        my_udpPairs.append(mypair)
        mypair = ["LenRegion", "200mm"]
        my_udpPairs.append(mypair)
        mypair = ["InfoCore", "0"]
        my_udpPairs.append(mypair)

        # Test udp with a custom name.
        my_udpName = "MyClawPoleCore"
        udp = self.aedtapp.modeler.create_udp(
            udp_dll_name="RMxprt/ClawPoleCore",
            udp_parameters_list=my_udpPairs,
            upd_library="syslib",
            name=my_udpName,
            udp_type="Solid",
        )

        assert udp
        assert udp.name == "MyClawPoleCore"
        assert "MyClawPoleCore" in udp._primitives.object_names
        assert int(udp.bounding_dimension[2]) == 100

        # Modify one of the 'MyClawPoleCore' udp properties.
        assert self.aedtapp.modeler.update_udp(
            object_name="MyClawPoleCore",
            operation_name="CreateUserDefinedPart",
            udp_parameters_list=[["Length", "110mm"]],
        )

        assert int(udp.bounding_dimension[0]) == 102
        assert int(udp.bounding_dimension[1]) == 102
        assert int(udp.bounding_dimension[2]) == 110

        # Test udp with default name -None-.
        second_udp = self.aedtapp.modeler.create_udp(
            udp_dll_name="RMxprt/ClawPoleCore",
            udp_parameters_list=my_udpPairs,
            upd_library="syslib",
            udp_type="Solid",
        )

        assert second_udp
        assert second_udp.name == "ClawPoleCore"
        assert "ClawPoleCore" in udp._primitives.object_names

        # Modify two of the 'MyClawPoleCore' udp properties.
        assert self.aedtapp.modeler.update_udp(
            object_name="ClawPoleCore",
            operation_name="CreateUserDefinedPart",
            udp_parameters_list=[["Length", "110mm"], ["DiaGap", "125mm"]],
        )

        assert int(second_udp.bounding_dimension[0]) == 125
        assert int(second_udp.bounding_dimension[1]) == 125
        assert int(second_udp.bounding_dimension[2]) == 110

    @pytest.mark.skipif(os.name == "posix", reason="Feature not supported in Linux")
    def test_27_create_udm(self):
        my_udmPairs = []
        mypair = ["ILD Thickness (ILD)", "0.006mm"]
        my_udmPairs.append(mypair)
        mypair = ["Line Spacing (LS)", "0.004mm"]
        my_udmPairs.append(mypair)
        mypair = ["Line Thickness (LT)", "0.005mm"]
        my_udmPairs.append(mypair)
        mypair = ["Line Width (LW)", "0.004mm"]
        my_udmPairs.append(mypair)
        mypair = ["No. of Turns (N)", 2]
        my_udmPairs.append(mypair)
        mypair = ["Outer Diameter (OD)", "0.15mm"]
        my_udmPairs.append(mypair)
        mypair = ["Substrate Thickness", "0.2mm"]
        my_udmPairs.append(mypair)
        mypair = [
            "Inductor Type",
            '"Square,Square,Octagonal,Circular,Square-Differential,Octagonal-Differential,Circular-Differential"',
        ]
        my_udmPairs.append(mypair)
        mypair = ["Underpass Thickness (UT)", "0.001mm"]
        my_udmPairs.append(mypair)
        mypair = ["Via Thickness (VT)", "0.001mm"]
        my_udmPairs.append(mypair)

        assert self.aedtapp.modeler.create_udm(
            udmfullname="Maxwell3D/OnDieSpiralInductor.py", udm_params_list=my_udmPairs, udm_library="syslib"
        )

    def test_28_assign_torque(self):
        assert self.aedtapp.assign_torque("Coil")

    def test_29_assign_force(self):
        assert self.aedtapp.assign_force("Coil")

    def test_30_assign_movement(self):
        self.aedtapp.insert_design("Motion")
        self.aedtapp.solution_type = SOLUTIONS.Maxwell3d.Transient
        self.aedtapp.modeler.create_box([0, 0, 0], [10, 10, 10], name="Inner_Box")
        self.aedtapp.modeler.create_box([0, 0, 0], [30, 20, 20], name="Outer_Box")
        bound = self.aedtapp.assign_translate_motion("Outer_Box", mechanical_transient=True, velocity=1)
        assert bound
        assert bound.props["Velocity"] == "1m_per_sec"

    def test_31_core_losses(self):

        m3d1 = Maxwell3d(self.file_path, specified_version=desktop_version)
        assert m3d1.set_core_losses(["PQ_Core_Bottom", "PQ_Core_Top"])
        assert m3d1.set_core_losses(["PQ_Core_Bottom"], False)
        self.aedtapp.close_project(m3d1.project_name, False)

    def test_32_matrix(self):
        m3d = Maxwell3d(self.file_path, specified_version=desktop_version)
        m3d.solution_type = SOLUTIONS.Maxwell3d.ElectroStatic
        m3d.modeler.primitives.create_box([0, 1.5, 0], [1, 2.5, 5], name="Coil_1", matname="aluminum")
        m3d.modeler.primitives.create_box([8.5, 1.5, 0], [1, 2.5, 5], name="Coil_2", matname="aluminum")
        m3d.modeler.primitives.create_box([16, 1.5, 0], [1, 2.5, 5], name="Coil_3", matname="aluminum")
        m3d.modeler.primitives.create_box([32, 1.5, 0], [1, 2.5, 5], name="Coil_4", matname="aluminum")

        rectangle1 = m3d.modeler.primitives.create_rectangle(0, [0.5, 1.5, 0], [2.5, 5], name="Sheet1")
        rectangle2 = m3d.modeler.primitives.create_rectangle(0, [9, 1.5, 0], [2.5, 5], name="Sheet2")
        rectangle3 = m3d.modeler.primitives.create_rectangle(0, [16.5, 1.5, 0], [2.5, 5], name="Sheet3")
        rectangle4 = m3d.modeler.primitives.create_rectangle(0, [32.5, 1.5, 0], [2.5, 5], name="Sheet4")

        m3d.assign_voltage(rectangle1.faces[0], amplitude=1, name="Voltage1")
        m3d.assign_voltage(rectangle2.faces[0], amplitude=1, name="Voltage2")
        m3d.assign_voltage(rectangle3.faces[0], amplitude=1, name="Voltage3")
        m3d.assign_voltage(rectangle4.faces[0], amplitude=1, name="Voltage4")

        L = m3d.assign_matrix(sources="Voltage1")
        assert L.props["MatrixEntry"]["MatrixEntry"][0]["Source"] == "Voltage1"
        assert L.delete()
        group_sources = "Voltage2"
        L = m3d.assign_matrix(sources=["Voltage1", "Voltage3"], matrix_name="Test1", group_sources=group_sources)
        assert L.props["MatrixEntry"]["MatrixEntry"][1]["Source"] == "Voltage3"
        m3d.solution_type = SOLUTIONS.Maxwell3d.Transient
        winding1 = m3d.assign_winding("Sheet1", name="Current1")
        winding2 = m3d.assign_winding("Sheet2", name="Current2")
        winding3 = m3d.assign_winding("Sheet3", name="Current3")
        winding4 = m3d.assign_winding("Sheet4", name="Current4")
        L = m3d.assign_matrix(sources="Current1")
        assert not L
        self.aedtapp.close_project(m3d.project_name, False)

    def test_33_mesh_settings(self):
        assert self.aedtapp.mesh.initial_mesh_settings
        assert self.aedtapp.mesh.initial_mesh_settings.props

    def test_34_assign_voltage_drop(self):
        circle = self.aedtapp.modeler.create_circle(position=[10, 10, 0], radius=5, cs_plane="XY")
        self.aedtapp.solution_type = "Magnetostatic"
        assert self.aedtapp.assign_voltage_drop([circle.faces[0]])
