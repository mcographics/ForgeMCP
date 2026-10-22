# SPDX-License-Identifier: MIT
"""Typed, bounded native recipes. No script text or unrestricted evaluation."""

import math
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")]
Vector = Annotated[list[FiniteFloat], Field(min_length=3, max_length=3)]


class RecipeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CsvImportPreviewRequest(RecipeModel):
    """A bounded local CSV import plan for a new User Defined Struct and DataTable."""

    csv_path: Annotated[str, Field(min_length=1, max_length=1024)]
    struct_path: Annotated[str, Field(pattern=r"^/Game/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+$", max_length=240)]
    data_table_path: Annotated[str, Field(pattern=r"^/Game/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+$", max_length=240)]
    row_key_column: Annotated[str, Field(min_length=1, max_length=128)]
    # Pin information inferred from CSV values is advisory. Explicit overrides win.
    type_overrides: dict[str, Literal["string", "name", "bool", "int", "int64", "double"]] = Field(
        default_factory=dict, max_length=256
    )


class StructTooltipsPreviewRequest(RecipeModel):
    """Reviewed tooltip updates for exact User Defined Struct member names."""

    struct_path: Annotated[str, Field(pattern=r"^/Game/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+$", max_length=240)]
    tooltips: dict[Identifier, Annotated[str, Field(min_length=1, max_length=1024)]] = Field(
        min_length=1, max_length=256
    )


BlueprintValueType = Literal["bool", "int", "float", "string", "name", "vector", "rotator"]
GAS_BOOTSTRAP_COMPONENT = "/Script/MajesticForgeRuntime.ForgeGameplayAbilitySetupComponent"
GASClassPath = Annotated[
    str,
    Field(
        pattern=(
            r"^(?:/Script/[A-Za-z0-9_]+\.[A-Za-z0-9_]+|"
            r"/Game/(?:[A-Za-z_][A-Za-z0-9_]*/)*"
            r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*_C)$"
        ),
        max_length=240,
    ),
]


class BlueprintVariable(RecipeModel):
    name: Identifier
    type: BlueprintValueType
    default: Annotated[str, Field(max_length=512)] = ""


class BlueprintFunctionPin(RecipeModel):
    name: Identifier
    type: BlueprintValueType


class BlueprintFunctionSpec(RecipeModel):
    name: Identifier
    inputs: Annotated[list[BlueprintFunctionPin], Field(max_length=16)] = Field(
        default_factory=list
    )
    outputs: Annotated[list[BlueprintFunctionPin], Field(max_length=16)] = Field(
        default_factory=list
    )
    pure: bool = False

    @model_validator(mode="after")
    def unique_parameter_names(self):
        names = [pin.name.casefold() for pin in self.inputs + self.outputs]
        if len(names) != len(set(names)):
            raise ValueError("Function input/output parameter names must be unique")
        if self.pure and not self.outputs:
            raise ValueError("Pure functions must declare at least one output")
        return self


class GASAbilityGrant(RecipeModel):
    class_path: GASClassPath
    level: Annotated[int, Field(ge=1, le=100)] = 1
    input_id: Annotated[int, Field(ge=-1, le=255)] = -1


class GASStartupEffect(RecipeModel):
    class_path: GASClassPath
    level: Annotated[FiniteFloat, Field(gt=0, le=100)] = 1.0


class GASSetup(RecipeModel):
    ability_system_component: Identifier = "AbilitySystemComponent"
    replication_mode: Literal["minimal", "mixed", "full"] | None = None
    initialize_owner_as_avatar: bool = True
    attribute_sets: Annotated[list[GASClassPath], Field(max_length=16)] = Field(
        default_factory=list
    )
    startup_abilities: Annotated[list[GASAbilityGrant], Field(max_length=32)] = Field(
        default_factory=list
    )
    startup_effects: Annotated[list[GASStartupEffect], Field(max_length=32)] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_unique_gas_classes(self):
        for label, classes in (
            ("AttributeSet", self.attribute_sets),
            ("ability", [grant.class_path for grant in self.startup_abilities]),
            ("GameplayEffect", [effect.class_path for effect in self.startup_effects]),
        ):
            if len(classes) != len({class_path.casefold() for class_path in classes}):
                raise ValueError(f"GAS {label} class paths must be unique")
        return self


class BlueprintComponent(RecipeModel):
    name: Identifier
    class_path: Annotated[str, Field(pattern=r"^/Script/[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")]
    replication_mode: Literal["minimal", "mixed", "full"] | None = None
    gas_setup: GASSetup | None = None

    @model_validator(mode="after")
    def validate_gas_component_mode(self):
        ability_system = self.class_path == "/Script/GameplayAbilities.AbilitySystemComponent"
        gas_setup_component = self.class_path == GAS_BOOTSTRAP_COMPONENT
        if ability_system and self.replication_mode is None:
            raise ValueError("AbilitySystemComponent requires an explicit replication_mode")
        if self.replication_mode is not None and not ability_system:
            raise ValueError("replication_mode is supported only on AbilitySystemComponent")
        if gas_setup_component != (self.gas_setup is not None):
            raise ValueError("GAS startup settings require the ForgeGameplayAbilitySetupComponent")
        return self


GraphNodeRef = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
BlueprintGraphName = Annotated[
    str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_ /-]{0,63}$")
]


class BlueprintNode(RecipeModel):
    id: Identifier
    kind: Literal["event", "custom_event", "variable_get", "variable_set", "call_function",
                  "branch", "sequence", "self", "reroute", "function_entry",
                  "function_result"]
    name: Annotated[str, Field(min_length=1, max_length=64)]
    owner_class: str = "/Script/Engine.Actor"
    graph: BlueprintGraphName = "EventGraph"
    x: Annotated[int, Field(ge=-100000, le=100000)] = 0
    y: Annotated[int, Field(ge=-100000, le=100000)] = 0
    execution_outputs: Annotated[int, Field(ge=2, le=16)] = 2
    defaults: dict[Identifier, Annotated[str, Field(max_length=512)]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_member_reference(self):
        # Existing Blueprint members can have spaces. Native preview resolves the
        # exact member before creating a node; new members remain identifiers.
        pattern = (r"[A-Za-z_][A-Za-z0-9_ ]{0,63}" if self.kind in
                   {"variable_get", "variable_set"} else r"[A-Za-z_][A-Za-z0-9_]{0,63}")
        if not re.fullmatch(pattern, self.name) or self.name != self.name.strip():
            raise ValueError("Node name must be a bounded identifier or exact existing member name")
        return self


class BlueprintConnection(RecipeModel):
    graph: BlueprintGraphName = "EventGraph"
    from_node: GraphNodeRef
    from_pin: Annotated[str, Field(min_length=1, max_length=128)]
    to_node: GraphNodeRef
    to_pin: Annotated[str, Field(min_length=1, max_length=128)]


class BlueprintRecipe(RecipeModel):
    asset_path: Annotated[
        str,
        Field(
            pattern=r"^/Game/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*$", max_length=240
        ),
    ]
    parent_class: str = "/Script/Engine.Actor"
    variables: Annotated[list[BlueprintVariable], Field(max_length=32)] = Field(
        default_factory=list
    )
    components: Annotated[list[BlueprintComponent], Field(max_length=32)] = Field(
        default_factory=list
    )
    functions: Annotated[list[Identifier | BlueprintFunctionSpec], Field(max_length=16)] = Field(
        default_factory=list
    )
    nodes: Annotated[list[BlueprintNode], Field(max_length=64)] = Field(default_factory=list)
    connections: Annotated[list[BlueprintConnection], Field(max_length=128)] = Field(
        default_factory=list
    )
    place: bool = False
    location: Vector = Field(default_factory=lambda: [0, 0, 0])
    save: bool = False

    @model_validator(mode="after")
    def validate_function_graphs(self):
        function_names = [
            function if isinstance(function, str) else function.name for function in self.functions
        ]
        folded_names = [name.casefold() for name in function_names]
        if len(folded_names) != len(set(folded_names)):
            raise ValueError("Function names must be unique")
        if any(name.casefold() == "eventgraph" for name in function_names):
            raise ValueError("Function names cannot conflict with EventGraph")
        member_names = [variable.name.casefold() for variable in self.variables]
        member_names.extend(component.name.casefold() for component in self.components)
        if len(member_names) != len(set(member_names)):
            raise ValueError("Variable and component names must be unique")
        if set(member_names).intersection(folded_names):
            raise ValueError("Function names cannot conflict with variables or components")

        setup_owners: set[str] = set()
        for component in self.components:
            if component.gas_setup is None:
                continue
            matching_ability_systems = [
                candidate
                for candidate in self.components
                if candidate.class_path
                == "/Script/GameplayAbilities.AbilitySystemComponent"
                and candidate.name.casefold()
                == component.gas_setup.ability_system_component.casefold()
            ]
            if len(matching_ability_systems) != 1:
                raise ValueError(
                    "GAS startup settings must name one AbilitySystemComponent in the Blueprint"
                )
            ability_system = matching_ability_systems[0]
            component_key = ability_system.name.casefold()
            if component_key in setup_owners:
                raise ValueError("Only one GAS setup component may configure each AbilitySystemComponent")
            setup_owners.add(component_key)
            configured_mode = component.gas_setup.replication_mode
            requested_mode = ability_system.replication_mode
            if configured_mode is not None and configured_mode != requested_mode:
                raise ValueError("GAS setup replication_mode must match its AbilitySystemComponent")
            component.gas_setup.replication_mode = requested_mode

        for ability_system in self.components:
            if (ability_system.class_path == "/Script/GameplayAbilities.AbilitySystemComponent"
                    and ability_system.replication_mode in {"minimal", "mixed"}
                    and ability_system.name.casefold() not in setup_owners):
                raise ValueError(
                    "minimal/mixed replication_mode requires a matching ForgeGameplayAbilitySetupComponent"
                )

        function_name_set = set(function_names)
        function_nodes: set[tuple[str, str]] = set()
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Blueprint node IDs must be unique")
        for node in self.nodes:
            if node.kind in {"function_entry", "function_result"}:
                expected_name = "Entry" if node.kind == "function_entry" else "Return"
                if node.graph == "EventGraph" or node.graph not in function_name_set:
                    raise ValueError("Function entry/return nodes must reference a declared function graph")
                if node.name != expected_name:
                    raise ValueError(f"Use name '{expected_name}' for a {node.kind} graph reference")
                key = (node.kind, node.graph.casefold())
                if key in function_nodes:
                    raise ValueError(f"Only one {node.kind} reference is allowed per function graph")
                function_nodes.add(key)
            elif node.graph != "EventGraph" and node.graph not in function_name_set:
                raise ValueError("Graph nodes must reference EventGraph or a declared function")
        return self


class ShaderNode(RecipeModel):
    id: Identifier
    type: Literal[
        "ShaderNodeOutputMaterial", "ShaderNodeBsdfPrincipled", "ShaderNodeRGB",
        "ShaderNodeValue", "ShaderNodeMath", "ShaderNodeMixRGB", "ShaderNodeTexNoise",
        "ShaderNodeTexCoord", "ShaderNodeMapping", "ShaderNodeBump", "ShaderNodeVectorMath",
        "ShaderNodeSeparateXYZ", "ShaderNodeCombineXYZ",
    ]
    inputs: dict[Annotated[str, Field(min_length=1, max_length=64)],
                 FiniteFloat | Annotated[list[FiniteFloat], Field(min_length=3, max_length=4)]] = (
        Field(default_factory=dict, max_length=16)
    )
    outputs: dict[Annotated[str, Field(min_length=1, max_length=64)],
                  FiniteFloat | Annotated[list[FiniteFloat], Field(min_length=3, max_length=4)]] = (
        Field(default_factory=dict, max_length=16)
    )
    operation: Annotated[str, Field(max_length=32)] = ""
    x: Annotated[int, Field(ge=-100000, le=100000)] = 0
    y: Annotated[int, Field(ge=-100000, le=100000)] = 0


class ShaderNodeEdit(RecipeModel):
    id: Annotated[str, Field(min_length=1, max_length=64, strict=True)]
    x: Annotated[int, Field(strict=True, ge=-100000, le=100000)] | None = None
    y: Annotated[int, Field(strict=True, ge=-100000, le=100000)] | None = None
    operation: Annotated[str, Field(max_length=32)] = ""
    blend_type: Literal["MIX", "ADD", "MULTIPLY", "SUBTRACT", "SCREEN", "OVERLAY"] | None = None
    inputs: dict[Annotated[str, Field(min_length=1, max_length=64)],
                 FiniteFloat | Annotated[list[FiniteFloat], Field(min_length=3, max_length=4)]] = (
        Field(default_factory=dict, max_length=16)
    )

    @model_validator(mode="after")
    def requires_edit(self):
        if any(ord(character) < 32 for character in self.id):
            raise ValueError("Node IDs cannot contain control characters")
        if self.x is None and self.y is None and not self.operation and self.blend_type is None and not self.inputs:
            raise ValueError("A shader node edit must change a position, operation, blend type, or input default")
        return self


class BlueprintEdit(RecipeModel):
    op: Literal["move", "default", "connect", "disconnect", "remove"]
    graph: BlueprintGraphName
    node_id: GraphNodeRef
    pin: Annotated[str, Field(max_length=128)] = ""
    value: Annotated[str, Field(max_length=512)] = ""
    x: Annotated[int, Field(ge=-100000, le=100000)] = 0
    y: Annotated[int, Field(ge=-100000, le=100000)] = 0
    to_node: GraphNodeRef = ""
    to_pin: Annotated[str, Field(max_length=128)] = ""


class BlueprintWidgetEdit(RecipeModel):
    name: Identifier
    action: Literal["hide_text"]


class BlueprintMaterialSlot(RecipeModel):
    index: Annotated[int, Field(strict=True, ge=0, le=31)]
    material_path: Annotated[str, Field(pattern=r"^/Game/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$", max_length=280)]


class BlueprintComponentSetting(RecipeModel):
    component_name: Identifier
    mobility: Literal["Static", "Stationary", "Movable"] | None = None
    material_slots: Annotated[list[BlueprintMaterialSlot], Field(max_length=16)] = Field(default_factory=list)

    @model_validator(mode="after")
    def requires_a_setting(self):
        if self.mobility is None and not self.material_slots:
            raise ValueError("A component setting must change mobility or at least one material slot")
        indices = [slot.index for slot in self.material_slots]
        if len(indices) != len(set(indices)):
            raise ValueError("Each component material slot may be changed only once")
        return self


class BlueprintEditRecipe(RecipeModel):
    asset_path: Annotated[str, Field(pattern=r"^/Game/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*$", max_length=240)]
    operations: Annotated[list[BlueprintEdit], Field(max_length=32)] = Field(default_factory=list)
    variables: Annotated[list[BlueprintVariable], Field(max_length=32)] = Field(default_factory=list)
    components: Annotated[list[BlueprintComponent], Field(max_length=32)] = Field(default_factory=list)
    functions: Annotated[list[BlueprintFunctionSpec], Field(max_length=16)] = Field(default_factory=list)
    nodes: Annotated[list[BlueprintNode], Field(max_length=32)] = Field(default_factory=list)
    connections: Annotated[list[BlueprintConnection], Field(max_length=64)] = Field(default_factory=list)
    widgets: Annotated[list[BlueprintWidgetEdit], Field(max_length=32)] = Field(default_factory=list)
    component_settings: Annotated[list[BlueprintComponentSetting], Field(max_length=32)] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_bounded_changes(self):
        function_names = [function.name.casefold() for function in self.functions]
        if len(function_names) != len(set(function_names)):
            raise ValueError("Function names must be unique")
        member_names = {variable.name.casefold() for variable in self.variables}
        member_names.update(component.name.casefold() for component in self.components)
        if set(function_names) & member_names:
            raise ValueError("Function names cannot conflict with new variables or components")
        function_node_refs: set[tuple[str, str]] = set()
        function_name_set = set(function_names)
        for node in self.nodes:
            if node.kind in {"function_entry", "function_result"}:
                expected_name = "Entry" if node.kind == "function_entry" else "Return"
                if node.graph.casefold() not in function_name_set or node.name != expected_name:
                    raise ValueError("Function entry/return nodes must reference a function added in this edit")
                key = (node.kind, node.graph.casefold())
                if key in function_node_refs:
                    raise ValueError(f"Only one {node.kind} reference is allowed per function graph")
                function_node_refs.add(key)
            # Existing function/collapsed graphs are resolved by native preview.
            # Entry/result nodes above still require a newly declared function.
        widget_names = [widget.name.casefold() for widget in self.widgets]
        if len(widget_names) != len(set(widget_names)):
            raise ValueError("Widget edits must name unique exact widgets")
        change_count = (len(self.widgets) + len(self.operations) + len(self.variables) + len(self.components)
                        + len(self.component_settings) + len(self.functions)
                        + len(self.nodes) + len(self.connections))
        if not 1 <= change_count <= 128:
            raise ValueError("Blueprint edit needs 1 to 128 total changes")
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("New Blueprint node IDs must be unique")
        variable_names = [variable.name for variable in self.variables]
        component_names = [component.name for component in self.components]
        if len(variable_names) != len(set(variable_names)) or len(component_names) != len(set(component_names)):
            raise ValueError("New Blueprint variables and components must have unique names")
        setting_names = [setting.component_name.casefold() for setting in self.component_settings]
        if len(setting_names) != len(set(setting_names)):
            raise ValueError("Blueprint component settings must name unique components")
        return self

    @model_validator(mode="after")
    def configure_added_gas_components(self):
        new_ability_systems = {
            component.name.casefold(): component
            for component in self.components
            if component.class_path == "/Script/GameplayAbilities.AbilitySystemComponent"
        }
        setup_owners: set[str] = set()
        for component in self.components:
            setup = component.gas_setup
            if setup is None:
                continue
            owner = setup.ability_system_component.casefold()
            if owner in setup_owners:
                raise ValueError("Only one GAS setup component may configure each AbilitySystemComponent")
            setup_owners.add(owner)
            ability_system = new_ability_systems.get(owner)
            if ability_system is None:
                continue
            if setup.replication_mode is not None and setup.replication_mode != ability_system.replication_mode:
                raise ValueError("GAS setup replication_mode must match its AbilitySystemComponent")
            setup.replication_mode = ability_system.replication_mode

        for name, ability_system in new_ability_systems.items():
            if (ability_system.replication_mode in {"minimal", "mixed"}
                    and name not in setup_owners):
                raise ValueError(
                    "minimal/mixed replication_mode requires a matching ForgeGameplayAbilitySetupComponent"
                )
        return self


class ActorOperation(RecipeModel):
    op: Literal["spawn", "transform", "visibility"]
    actor_path: Annotated[str, Field(max_length=512)] = ""
    class_path: Annotated[str, Field(max_length=240)] = ""
    label: Annotated[str, Field(max_length=64)] = ""
    tags: Annotated[list[Annotated[str, Field(min_length=1, max_length=128)]], Field(max_length=16)] | None = None
    mesh_path: Annotated[str, Field(max_length=240)] = ""
    location: Vector | None = None
    rotation: Vector | None = None
    scale: Vector | None = None
    hidden: bool | None = None

    @model_validator(mode="after")
    def validate_mesh_placement(self):
        if self.tags is not None:
            if self.op != "spawn":
                raise ValueError("tags can be assigned only when spawning a new actor")
            if any(tag != tag.strip() for tag in self.tags):
                raise ValueError("actor tags cannot start or end with whitespace")
            if len({tag.casefold() for tag in self.tags}) != len(self.tags):
                raise ValueError("actor tags must be unique")
        if self.mesh_path:
            if self.op != "spawn" or self.class_path != "/Script/Engine.StaticMeshActor":
                raise ValueError("mesh_path requires native StaticMeshActor spawning")
            if not re.fullmatch(r"/Game/(?:[A-Za-z_][A-Za-z0-9_]*/)*([A-Za-z_][A-Za-z0-9_]*)\.\1", self.mesh_path):
                raise ValueError("mesh_path must be an exact /Game/ static-mesh object path")
        return self


class ActorRecipe(RecipeModel):
    operations: Annotated[list[ActorOperation], Field(min_length=1, max_length=32)]


class DataAssetInitialProperty(RecipeModel):
    name: Identifier
    value: Annotated[str, Field(strict=True, max_length=512)]


class DataAssetCreateRequest(RecipeModel):
    asset_path: Annotated[
        str,
        Field(pattern=r"^/(?:Game|JasperPrism)/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*$", max_length=240),
    ]
    class_path: Annotated[
        str,
        Field(
            pattern=(
                r"^(?:/Script/[A-Za-z0-9_]+\.[A-Za-z0-9_]+|"
                r"/Game/(?:[A-Za-z_][A-Za-z0-9_]*/)*"
                r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*_C)$"
            ),
            max_length=512,
        ),
    ]
    properties: Annotated[list[DataAssetInitialProperty], Field(max_length=32)] = Field(default_factory=list)
    save: Annotated[bool, Field(strict=True)] = False

    @model_validator(mode="after")
    def unique_property_names(self):
        names = [item.name.casefold() for item in self.properties]
        if len(names) != len(set(names)):
            raise ValueError("DataAsset initial property names must be unique")
        return self


class DataAssetPropertyEditRequest(RecipeModel):
    asset_path: Annotated[
        str,
        Field(
            pattern=r"^/(?:Game|JasperPrism)/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$",
            max_length=512,
        ),
    ]
    properties: Annotated[list[DataAssetInitialProperty], Field(min_length=1, max_length=32)]
    save: Annotated[bool, Field(strict=True)] = False

    @model_validator(mode="after")
    def unique_property_names(self):
        names = [item.name.casefold() for item in self.properties]
        if len(names) != len(set(names)):
            raise ValueError("DataAsset property edits must use unique names")
        package_path = self.asset_path.split(".", 1)[0]
        if "." in self.asset_path and self.asset_path.split(".", 1)[1] != package_path.rsplit("/", 1)[-1]:
            raise ValueError("DataAsset object path must name the asset matching its package")
        return self


class ShaderLink(RecipeModel):
    from_node: Annotated[str, Field(min_length=1, max_length=64)]
    from_socket: Annotated[str, Field(min_length=1, max_length=64)]
    to_node: Annotated[str, Field(min_length=1, max_length=64)]
    to_socket: Annotated[str, Field(min_length=1, max_length=64)]


class RigBoneSpec(RecipeModel):
    name: Identifier
    head: Vector
    tail: Vector
    parent: Identifier | None = None
    connected: bool = False
    deform: bool = True

    @model_validator(mode="after")
    def validate_bone_extent(self):
        if any(abs(value) > 100000 for value in self.head + self.tail):
            raise ValueError("Rig bone coordinates must stay within 100000 Blender units")
        if math.dist(self.head, self.tail) <= 1e-6:
            raise ValueError("Rig bones need distinct head and tail positions")
        if self.connected and self.parent is None:
            raise ValueError("Connected rig bones require a parent")
        return self


class SkinWeight(RecipeModel):
    vertex: Annotated[int, Field(strict=True, ge=0, le=9999)]
    bone: Identifier
    weight: Annotated[FiniteFloat, Field(strict=True, gt=0, le=1)]


class MeshEdgeSeam(RecipeModel):
    index: Annotated[int, Field(strict=True, ge=0, le=200000)]
    seam: Annotated[bool, Field(strict=True)]


class IKConstraintSpec(RecipeModel):
    bone: Identifier
    constraint: Identifier
    target: Identifier
    chain_count: Annotated[int, Field(strict=True, ge=1, le=16)]
    iterations: Annotated[int, Field(strict=True, ge=1, le=256)] = 64
    pole_target: Identifier | None = None
    pole_angle: Annotated[FiniteFloat, Field(strict=True, ge=-math.pi, le=math.pi)] = 0.0

    @model_validator(mode="after")
    def validate_pole(self):
        if self.pole_target is not None:
            if self.pole_target == self.target or self.chain_count < 2:
                raise ValueError("Pole IK needs a distinct target and at least two bones")
        elif self.pole_angle != 0:
            raise ValueError("Pole angle requires a pole target")
        return self


class SceneOperation(RecipeModel):
    op: Literal[
        "create_mesh",
        "set_vertices",
        "set_mesh_geometry",
        "set_uv_coordinates",
        "create_uv_layer",
        "smart_uv_project",
        "unwrap_uv",
        "pack_uv_islands",
        "set_mesh_edge_seams",
        "set_transform",
        "create_material",
        "assign_material",
        "create_collection",
        "keyframe",
        "set_keyframe",
        "scene_settings",
        "duplicate_object",
        "set_material_input",
        "edit_material_graph",
        "create_armature",
        "bone_keyframe",
        "bind_mesh",
        "reweight_mesh",
        "auto_bind_mesh",
        "patch_skin_weights",
        "create_ik_constraint",
        "create_empty",
        "set_frame",
        "add_modifier",
        "set_modifier_settings",
    ]
    name: Annotated[str, Field(min_length=1, max_length=64)] = ""
    vertices: Annotated[list[Vector], Field(max_length=512)] = Field(default_factory=list)
    faces: Annotated[
        list[Annotated[list[int], Field(min_length=3, max_length=32)]], Field(max_length=512)
    ] = Field(default_factory=list)
    edge_seams: Annotated[list[MeshEdgeSeam], Field(max_length=512)] = Field(default_factory=list)
    uv_layer: Annotated[str, Field(max_length=64)] = ""
    uv_start: Annotated[int, Field(strict=True, ge=0, le=1000000)] = 0
    uv_values: Annotated[list[Annotated[list[FiniteFloat], Field(min_length=2, max_length=2)]], Field(max_length=512)] = Field(default_factory=list)
    uv_angle_limit: Annotated[FiniteFloat, Field(ge=0, le=1.5707963267948966)] = 1.1519173063162575
    uv_island_margin: Annotated[FiniteFloat, Field(ge=0, le=0.5)] = 0.02
    uv_unwrap_method: Literal["ANGLE_BASED", "CONFORMAL"] = "ANGLE_BASED"
    uv_margin: Annotated[FiniteFloat, Field(ge=0, le=0.5)] = 0.001
    location: Vector | None = None
    rotation: Vector | None = None
    scale: Vector | None = None
    color: Annotated[list[FiniteFloat], Field(min_length=4, max_length=4)] | None = None
    material: str = ""
    collection: str = ""
    source: Annotated[str, Field(max_length=64)] = ""
    bone: Annotated[str, Field(max_length=64)] = ""
    node: Annotated[str, Field(max_length=64)] = ""
    socket: Annotated[str, Field(max_length=64)] = ""
    value: FiniteFloat | Annotated[list[FiniteFloat], Field(min_length=3, max_length=4)] | None = None
    data_path: Literal["location", "rotation_euler", "rotation_quaternion", "scale"] = "location"
    frame: Annotated[int, Field(strict=True, ge=-100000, le=100000)] = 1
    curve_index: Annotated[int, Field(strict=True, ge=0, le=9999)] | None = None
    keyframe_index: Annotated[int, Field(strict=True, ge=0, le=100000)] | None = None
    key_frame: Annotated[FiniteFloat, Field(ge=-100000, le=100000)] | None = None
    key_value: Annotated[FiniteFloat, Field(ge=-100000000, le=100000000)] | None = None
    fps: Annotated[int, Field(ge=1, le=240)] = 30
    frame_start: Annotated[int, Field(ge=-100000, le=100000)] = 1
    frame_end: Annotated[int, Field(ge=-100000, le=100000)] = 250
    shader_nodes: Annotated[list[ShaderNode], Field(max_length=32)] = Field(default_factory=list)
    shader_links: Annotated[list[ShaderLink], Field(max_length=64)] = Field(default_factory=list)
    shader_links_remove: Annotated[list[ShaderLink], Field(max_length=64)] = Field(default_factory=list)
    shader_node_edits: Annotated[list[ShaderNodeEdit], Field(max_length=32)] = Field(default_factory=list)
    bones: Annotated[list[RigBoneSpec], Field(max_length=64)] = Field(default_factory=list)
    armature: Annotated[str, Field(max_length=64)] = ""
    weights: Annotated[list[SkinWeight], Field(max_length=512)] = Field(default_factory=list)
    weight_method: Literal["", "blender_heat_top4"] = ""
    ik: IKConstraintSpec | None = None
    modifier_type: Literal["SUBSURF", "BEVEL", "SOLIDIFY", "WEIGHTED_NORMAL"] | None = None
    modifier_name: Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")] = ""
    modifier_settings: Annotated[dict[str, bool | int | float | str], Field(max_length=8)] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_action_key_edit(self):
        fields = {"curve_index", "keyframe_index", "key_frame", "key_value"}
        if self.op == "set_keyframe":
            if not self.name or any(getattr(self, field) is None for field in fields):
                raise ValueError("Editing an Action key requires an object, curve/key indices, frame and value")
            if any(field in self.model_fields_set for field in ("value", "data_path", "frame")):
                raise ValueError("Action key edits use key_frame and key_value, not transform keyframe fields")
        elif any(field in self.model_fields_set for field in fields):
            raise ValueError("Action key edit fields belong only to set_keyframe")
        return self

    @model_validator(mode="after")
    def validate_material_graph_edit(self):
        graph_fields = self.shader_nodes or self.shader_links or self.shader_links_remove or self.shader_node_edits
        if self.op == "edit_material_graph":
            if not self.name or not graph_fields:
                raise ValueError("Material graph edits require an exact material name and graph additions, link removals or node edits")
            if any(node.type == "ShaderNodeOutputMaterial" for node in self.shader_nodes):
                raise ValueError("Existing material graph edits cannot replace the material output node")
            node_ids = [node.id for node in self.shader_nodes]
            if len(node_ids) != len(set(node_ids)):
                raise ValueError("Added material node IDs must be unique")
            edit_ids = [edit.id for edit in self.shader_node_edits]
            if len(edit_ids) != len(set(edit_ids)) or set(edit_ids) & set(node_ids):
                raise ValueError("Existing node edits must be unique and cannot target nodes added in the same recipe")
            link_targets = [(link.to_node, link.to_socket) for link in self.shader_links]
            if len(link_targets) != len(set(link_targets)):
                raise ValueError("Each material graph input can receive only one added link")
            removed_links = [
                (link.from_node, link.from_socket, link.to_node, link.to_socket)
                for link in self.shader_links_remove
            ]
            if len(removed_links) != len(set(removed_links)):
                raise ValueError("Material graph link removals must be unique")
        elif self.op == "create_material":
            if self.shader_node_edits or self.shader_links_remove:
                raise ValueError("Existing graph edits belong only to edit_material_graph")
        elif graph_fields:
            raise ValueError("Shader graph fields belong only to create_material or edit_material_graph")
        return self

    @model_validator(mode="after")
    def validate_ik_setup(self):
        if (self.op == "create_ik_constraint") != (self.ik is not None):
            raise ValueError("IK setup requires an explicit spec only on create_ik_constraint")
        return self

    @model_validator(mode="after")
    def validate_modifier_setup(self):
        if self.op == "add_modifier":
            if self.modifier_type is None or not self.modifier_name:
                raise ValueError("Modifier creation requires a supported type and name")
        elif self.op == "set_modifier_settings":
            if self.modifier_type is not None or not self.modifier_name or not self.modifier_settings:
                raise ValueError("Modifier edits require a target name and at least one setting")
        elif self.modifier_type is not None or self.modifier_name or self.modifier_settings:
            raise ValueError("Modifier fields belong only to add_modifier")
        return self

    @model_validator(mode="after")
    def validate_mesh_geometry(self):
        if self.op in {"create_mesh", "set_vertices", "set_mesh_geometry"}:
            maximum = 512 if self.op == "set_mesh_geometry" else 128
            if not self.name or not 1 <= len(self.vertices) <= maximum:
                raise ValueError(f"Mesh geometry requires a name and 1 to {maximum} vertices")
            if self.op == "set_mesh_geometry":
                if len(self.faces) > 512:
                    raise ValueError("Topology replacement supports at most 512 faces")
                for face in self.faces:
                    if len(set(face)) != len(face) or any(type(index) is not int or index < 0 or index >= len(self.vertices) for index in face):
                        raise ValueError("Mesh face indices must be unique and reference supplied vertices")
            else:
                if len(self.vertices) > 128 or len(self.faces) > 128:
                    raise ValueError("Mesh creation and vertex edits support at most 128 vertices and faces")
                if self.op == "set_vertices" and self.faces:
                    raise ValueError("Vertex position edits cannot include topology")
        elif self.vertices or self.faces:
            raise ValueError("Vertex and face fields belong only to mesh geometry operations")
        return self

    @model_validator(mode="after")
    def validate_uv_edit(self):
        if self.op in {"set_uv_coordinates", "create_uv_layer", "smart_uv_project", "unwrap_uv", "pack_uv_islands"}:
            if self.op == "smart_uv_project":
                if not self.name or not self.uv_layer:
                    raise ValueError("Smart UV projection requires a mesh and layer name")
                if any(field in self.model_fields_set for field in (
                    "uv_start", "uv_values", "uv_unwrap_method", "uv_margin"
                )):
                    raise ValueError("Smart UV projection does not accept loop coordinates or seam unwrap settings")
                return self
            if self.op == "unwrap_uv":
                if not self.name or not self.uv_layer:
                    raise ValueError("Seam-based UV unwrap requires a mesh and layer name")
                if any(field in self.model_fields_set for field in (
                    "uv_start", "uv_values", "uv_angle_limit", "uv_island_margin"
                )):
                    raise ValueError("Seam-based unwrap does not accept coordinate or smart-project settings")
                return self
            if self.op == "pack_uv_islands":
                if not self.name or not self.uv_layer:
                    raise ValueError("UV island packing requires a mesh and layer name")
                if any(field in self.model_fields_set for field in (
                    "uv_start", "uv_values", "uv_angle_limit", "uv_island_margin", "uv_unwrap_method"
                )):
                    raise ValueError("UV island packing accepts only its target layer and packing margin")
                return self
            if any(field in self.model_fields_set for field in ("uv_angle_limit", "uv_island_margin")):
                raise ValueError("UV projection settings belong only to smart_uv_project")
            if any(field in self.model_fields_set for field in ("uv_unwrap_method", "uv_margin")):
                raise ValueError("Seam unwrap settings belong only to unwrap_uv")
            if self.op == "create_uv_layer" and self.uv_start != 0:
                raise ValueError("UV layer creation starts at loop zero")
            if not self.name or not self.uv_layer or not 1 <= len(self.uv_values) <= 512:
                if self.op == "create_uv_layer" and self.name and self.uv_layer and not self.uv_values:
                    return self
                raise ValueError("UV operations require a mesh, layer, and bounded loop coordinates")
            if any(any(abs(component) > 1000000 for component in uv) for uv in self.uv_values):
                raise ValueError("UV coordinates exceed the supported numeric range")
        elif any(field in self.model_fields_set for field in (
            "uv_layer", "uv_start", "uv_values", "uv_angle_limit", "uv_island_margin",
            "uv_unwrap_method", "uv_margin"
        )):
            raise ValueError("UV fields belong only to UV operations")
        return self

    @model_validator(mode="after")
    def validate_edge_seams(self):
        if self.op == "set_mesh_edge_seams":
            if not self.name or not 1 <= len(self.edge_seams) <= 512:
                raise ValueError("Mesh seam edits require a mesh and 1 to 512 edge changes")
            indices = [edge.index for edge in self.edge_seams]
            if len(indices) != len(set(indices)):
                raise ValueError("Mesh seam edge indices must be unique")
        elif self.edge_seams:
            raise ValueError("Edge seam changes belong only to set_mesh_edge_seams")
        return self

    @model_validator(mode="after")
    def validate_timeline_target(self):
        if self.op == "set_frame" and self.name:
            raise ValueError("set_frame targets the scene timeline; omit object name")
        return self

    @model_validator(mode="after")
    def validate_skin_binding(self):
        if self.op == "auto_bind_mesh":
            if not self.source or not self.armature or self.weights or self.weight_method != "blender_heat_top4":
                raise ValueError("Automatic binding requires mesh, armature and explicit blender_heat_top4 method")
            return self
        if self.weight_method:
            raise ValueError("Automatic weight method belongs only to auto_bind_mesh")
        if self.op in {"bind_mesh", "reweight_mesh", "patch_skin_weights"}:
            if not self.source or not self.armature or not self.weights:
                raise ValueError("Binding requires a source mesh, target armature and explicit weights")
            assignments = set()
            totals = {}
            influences = {}
            for item in self.weights:
                if self.op != "patch_skin_weights" and item.vertex >= 128:
                    raise ValueError("Full explicit skin recipes support vertex indices below 128")
                key = (item.vertex, item.bone)
                if key in assignments:
                    raise ValueError("Skin assignments must be unique")
                assignments.add(key)
                totals[item.vertex] = totals.get(item.vertex, 0) + item.weight
                influences[item.vertex] = influences.get(item.vertex, 0) + 1
            if any(abs(total - 1) > 1e-5 for total in totals.values()) or any(count > 4 for count in influences.values()):
                raise ValueError("Each vertex needs normalized weights and at most four influences")
            if self.op == "patch_skin_weights" and len(totals) > 128:
                raise ValueError("A weight patch supports at most 128 selected vertices")
        elif self.armature or self.weights:
            raise ValueError("Armature binding fields belong only to skin binding/weight operations")
        return self

    @model_validator(mode="after")
    def validate_bone_keyframe(self):
        if self.op == "bone_keyframe":
            if not self.bone or any(ord(char) < 32 for char in self.bone):
                raise ValueError("Bone keyframes require a bounded bone name")
            expected_size = 4 if self.data_path == "rotation_quaternion" else 3
            if self.data_path not in {"location", "rotation_euler", "rotation_quaternion", "scale"}:
                raise ValueError("Unsupported pose-bone keyframe property")
            if not isinstance(self.value, list) or len(self.value) != expected_size:
                raise ValueError(f"Bone {self.data_path} keyframes require {expected_size} values")
            if self.data_path == "rotation_quaternion":
                norm = math.sqrt(sum(value * value for value in self.value))
                if abs(norm - 1.0) > 1e-3:
                    raise ValueError("Pose-bone rotation_quaternion values must be normalized")
            if self.data_path == "scale" and any(abs(value) < 1e-8 for value in self.value):
                raise ValueError("Pose-bone scale keyframes cannot use zero scale")
        elif self.bone:
            raise ValueError("Bone names are supported only for bone_keyframe operations")
        elif self.op == "keyframe" and self.data_path == "rotation_quaternion":
            raise ValueError("Object transform keyframes do not support rotation_quaternion")
        if self.op == "keyframe" and self.value is not None:
            if not isinstance(self.value,list) or len(self.value) != 3:
                raise ValueError("Object keyframe values require three components")
            if self.data_path == "scale" and any(abs(value)<1e-8 for value in self.value):
                raise ValueError("Object scale keyframes cannot use zero scale")
        return self


class SceneRecipe(RecipeModel):
    operations: Annotated[list[SceneOperation], Field(min_length=1, max_length=32)]

    @model_validator(mode="after")
    def validate_armature_hierarchies(self):
        armature_names = set()
        for operation in self.operations:
            if operation.op != "create_armature":
                if operation.bones:
                    raise ValueError("Bone definitions are supported only for create_armature")
                continue
            if not 1 <= len(operation.bones) <= 64:
                raise ValueError("Armatures require 1 to 64 bounded bones")
            object_key = operation.name.casefold()
            if object_key in armature_names:
                raise ValueError("Armature object names must be unique in a recipe")
            armature_names.add(object_key)
            bones = {bone.name.casefold(): bone for bone in operation.bones}
            if len(bones) != len(operation.bones):
                raise ValueError("Rig bone names must be unique")
            for bone in operation.bones:
                if bone.parent is not None and bone.parent.casefold() not in bones:
                    raise ValueError("Rig bone parents must reference a bone in the same armature")
                if bone.connected:
                    parent = bones[bone.parent.casefold()]
                    if math.dist(parent.tail, bone.head) > 1e-4:
                        raise ValueError("Connected bone heads must match their parent tails")
            for bone_name in bones:
                visited = set()
                current = bone_name
                while bones[current].parent is not None:
                    current = bones[current].parent.casefold()
                    if current in visited or current == bone_name:
                        raise ValueError("Rig bone hierarchy cannot contain parent cycles")
                    visited.add(current)
        return self
