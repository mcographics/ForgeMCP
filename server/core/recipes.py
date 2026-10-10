"""Typed, bounded native recipes. No script text or unrestricted evaluation."""

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")]
Vector = Annotated[list[FiniteFloat], Field(min_length=3, max_length=3)]


class RecipeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class BlueprintNode(RecipeModel):
    id: Identifier
    kind: Literal["event", "custom_event", "variable_get", "variable_set", "call_function",
                  "branch", "sequence", "self", "reroute", "function_entry",
                  "function_result"]
    name: Identifier
    owner_class: str = "/Script/Engine.Actor"
    graph: Identifier = "EventGraph"
    x: Annotated[int, Field(ge=-100000, le=100000)] = 0
    y: Annotated[int, Field(ge=-100000, le=100000)] = 0
    execution_outputs: Annotated[int, Field(ge=2, le=16)] = 2
    defaults: dict[Identifier, Annotated[str, Field(max_length=512)]] = Field(default_factory=dict)


class BlueprintConnection(RecipeModel):
    graph: Identifier = "EventGraph"
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


class BlueprintEdit(RecipeModel):
    op: Literal["move", "default", "connect", "disconnect"]
    graph: Identifier
    node_id: GraphNodeRef
    pin: Annotated[str, Field(max_length=128)] = ""
    value: Annotated[str, Field(max_length=512)] = ""
    x: Annotated[int, Field(ge=-100000, le=100000)] = 0
    y: Annotated[int, Field(ge=-100000, le=100000)] = 0
    to_node: GraphNodeRef = ""
    to_pin: Annotated[str, Field(max_length=128)] = ""


class BlueprintEditRecipe(RecipeModel):
    asset_path: Annotated[str, Field(pattern=r"^/Game/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*$", max_length=240)]
    operations: Annotated[list[BlueprintEdit], Field(max_length=32)] = Field(default_factory=list)
    variables: Annotated[list[BlueprintVariable], Field(max_length=32)] = Field(default_factory=list)
    components: Annotated[list[BlueprintComponent], Field(max_length=32)] = Field(default_factory=list)
    nodes: Annotated[list[BlueprintNode], Field(max_length=32)] = Field(default_factory=list)
    connections: Annotated[list[BlueprintConnection], Field(max_length=64)] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_bounded_changes(self):
        change_count = (len(self.operations) + len(self.variables) + len(self.components)
                        + len(self.nodes) + len(self.connections))
        if not 1 <= change_count <= 128:
            raise ValueError("Blueprint edit needs 1 to 128 total changes")
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("New Blueprint node IDs must be unique")
        if any(node.kind in {"function_entry", "function_result"} for node in self.nodes):
            raise ValueError("Function entry/return references are supported only in new Blueprint recipes")
        variable_names = [variable.name for variable in self.variables]
        component_names = [component.name for component in self.components]
        if len(variable_names) != len(set(variable_names)) or len(component_names) != len(set(component_names)):
            raise ValueError("New Blueprint variables and components must have unique names")
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
    location: Vector | None = None
    rotation: Vector | None = None
    scale: Vector | None = None
    hidden: bool | None = None


class ActorRecipe(RecipeModel):
    operations: Annotated[list[ActorOperation], Field(min_length=1, max_length=32)]


class ShaderLink(RecipeModel):
    from_node: Identifier
    from_socket: Annotated[str, Field(min_length=1, max_length=64)]
    to_node: Identifier
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


class SceneOperation(RecipeModel):
    op: Literal[
        "create_mesh",
        "set_vertices",
        "set_transform",
        "create_material",
        "assign_material",
        "create_collection",
        "keyframe",
        "scene_settings",
        "duplicate_object",
        "set_material_input",
        "create_armature",
        "bone_keyframe",
    ]
    name: Annotated[str, Field(min_length=1, max_length=64)] = ""
    vertices: Annotated[list[Vector], Field(max_length=128)] = Field(default_factory=list)
    faces: Annotated[
        list[Annotated[list[int], Field(min_length=3, max_length=32)]], Field(max_length=128)
    ] = Field(default_factory=list)
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
    frame: Annotated[int, Field(ge=-100000, le=100000)] = 1
    fps: Annotated[int, Field(ge=1, le=240)] = 30
    frame_start: Annotated[int, Field(ge=-100000, le=100000)] = 1
    frame_end: Annotated[int, Field(ge=-100000, le=100000)] = 250
    shader_nodes: Annotated[list[ShaderNode], Field(max_length=32)] = Field(default_factory=list)
    shader_links: Annotated[list[ShaderLink], Field(max_length=64)] = Field(default_factory=list)
    bones: Annotated[list[RigBoneSpec], Field(max_length=64)] = Field(default_factory=list)

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
