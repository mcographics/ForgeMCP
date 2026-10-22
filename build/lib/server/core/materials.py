# SPDX-License-Identifier: MIT
"""Bounded material graph recipes; native validation remains authoritative."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

MaterialPath = Annotated[
    str,
    Field(
        pattern=r"^/(?:Game|JasperPrism)/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*$",
        max_length=240,
    ),
]
NodeId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_]{1,64}$")]
ExpressionType = Literal[
    "SceneTexture",
    "Subtract",
    "Multiply",
    "Add",
    "Constant",
    "Constant3Vector",
    "ScalarParameter",
    "VectorParameter",
]
Number = Annotated[FiniteFloat, Field(ge=-1000000, le=1000000)]
TextureObjectPath = Annotated[
    str,
    Field(
        pattern=r"^/(?:Game|JasperPrism)/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$",
        max_length=280,
    ),
]
JASPER_MATERIAL = "/JasperPrism/Materials/M_JasperPrism_PP"
JASPER_PERMISSION = "I authorize completing the existing JasperPrism contrast graph"
FORGE_TEST_MATERIAL = "/JasperPrism/Materials/M_ForgeMCP_Test"
FORGE_TEST_MATERIAL_PERMISSION = "I authorize creating the ForgeMCP test material at the exact target path"


class MaterialModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class MaterialInstanceParameter(MaterialModel):
    type: Literal["scalar", "vector", "texture"]
    name: Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")]
    value: Number | list[Number] | TextureObjectPath | None

    @model_validator(mode="after")
    def validate_typed_value(self):
        if self.type == "scalar":
            if type(self.value) not in {int, float} or abs(self.value) > 1_000_000:
                raise ValueError("Scalar parameter values must be finite numbers within +/-1,000,000")
        elif self.type == "vector":
            if (not isinstance(self.value, list) or len(self.value) != 4
                    or any(type(component) not in {int, float} or abs(component) > 1_000_000
                           for component in self.value)):
                raise ValueError("Vector parameter values must be four finite RGBA numbers")
        elif self.value is not None and not isinstance(self.value, str):
            raise ValueError("Texture parameter values must be an exact asset object path or null")
        return self


class MaterialInstanceRequest(MaterialModel):
    action: Literal["create", "update"]
    asset_path: MaterialPath
    parent_path: MaterialPath | None = None
    parameters: Annotated[list[MaterialInstanceParameter], Field(max_length=64)] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_parent_and_unique_parameters(self):
        if (self.action == "create") != (self.parent_path is not None):
            raise ValueError("Create requires a parent_path; update must omit it")
        if len({(parameter.type, parameter.name) for parameter in self.parameters}) != len(self.parameters):
            raise ValueError("Each material instance parameter can be changed only once")
        return self


class MaterialNode(MaterialModel):
    id: NodeId
    type: ExpressionType
    x: Annotated[int, Field(ge=-16000, le=16000)] = 0
    y: Annotated[int, Field(ge=-16000, le=16000)] = 0
    parameters: dict[str, Number | str | list[Number] | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_parameters(self):
        validate_parameters(self.type, self.parameters)
        return self


def validate_parameters(kind, values):
    allowed = {
        "SceneTexture": {"scene_texture_id", "filtered"},
        "Subtract": {"const_a", "const_b"},
        "Multiply": {"const_a", "const_b"},
        "Add": {"const_a", "const_b"},
        "Constant": {"value"},
        "Constant3Vector": {"value"},
        "ScalarParameter": {"parameter_name", "default_value"},
        "VectorParameter": {"parameter_name", "default_value"},
    }[kind]
    if values.keys() - allowed:
        raise ValueError("Unsupported expression parameter")
    for key, value in values.items():
        if key == "scene_texture_id":
            if value != "PostProcessInput0":
                raise ValueError("Only PostProcessInput0 is supported")
        elif key == "filtered":
            if type(value) is not bool:
                raise ValueError("filtered must be boolean")
        elif key == "parameter_name":
            import re

            if not isinstance(value, str) or not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]{0,63}", value
            ):
                raise ValueError("Invalid parameter name")
        elif kind in {"Constant3Vector", "VectorParameter"}:
            size = 3 if kind == "Constant3Vector" else 4
            if not isinstance(value, list) or len(value) != size:
                raise ValueError(f"Expected {size} finite vector components")
        elif type(value) not in {int, float}:
            raise ValueError("Expected a finite numeric constant")


class MaterialConnection(MaterialModel):
    from_node: NodeId
    # Empty explicitly selects native output zero; SceneTexture 'Color' also maps to zero.
    from_output: Literal["", "Color", "R", "G", "B", "A", "Size", "InvSize", "RGB"] = ""
    to_node: NodeId
    to_input: Annotated[str, Field(min_length=1, max_length=64)]


class MaterialPropertyConnection(MaterialModel):
    from_node: NodeId
    from_output: Literal["", "Color", "R", "G", "B", "A", "Size", "InvSize", "RGB"] = ""
    property: Literal["EmissiveColor"] = "EmissiveColor"


class MaterialUpdate(MaterialModel):
    node_id: NodeId
    type: ExpressionType
    parameters: dict[str, Number | str | list[Number] | bool]

    @model_validator(mode="after")
    def validate_parameters(self):
        if not self.parameters:
            raise ValueError("An update must change a supported parameter")
        validate_parameters(self.type, self.parameters)
        return self


class JasperDevelopmentAuthorization(MaterialModel):
    asset_path: Literal["/JasperPrism/Materials/M_JasperPrism_PP"]
    permission: Literal["I authorize completing the existing JasperPrism contrast graph"]
    expected_state_id: Annotated[str, Field(pattern=r"^[A-F0-9]{32}$")]


class ForgeTestMaterialCreationAuthorization(MaterialModel):
    asset_path: Literal["/JasperPrism/Materials/M_ForgeMCP_Test"]
    permission: Literal[
        "I authorize creating the ForgeMCP test material at the exact target path"
    ]
    expected_state: Literal["absent"]


class MaterialRecipe(MaterialModel):
    asset_path: MaterialPath
    domain: Literal["PostProcess"] = "PostProcess"
    blendable_location: Literal["SceneColorAfterTonemapping"] = "SceneColorAfterTonemapping"
    nodes: Annotated[list[MaterialNode], Field(max_length=32)] = Field(default_factory=list)
    connections: Annotated[list[MaterialConnection], Field(max_length=64)] = Field(
        default_factory=list
    )
    properties: Annotated[list[MaterialPropertyConnection], Field(max_length=1)] = Field(
        default_factory=list
    )
    updates: Annotated[list[MaterialUpdate], Field(max_length=32)] = Field(default_factory=list)
    action: Literal["edit", "compile", "save"] = "edit"
    development_authorization: JasperDevelopmentAuthorization | None = None
    creation_authorization: ForgeTestMaterialCreationAuthorization | None = None

    @model_validator(mode="after")
    def validate_graph(self):
        protected = self.asset_path.casefold() == JASPER_MATERIAL.casefold()
        auth = self.development_authorization
        creation_auth = self.creation_authorization
        if auth is not None and creation_auth is not None:
            raise ValueError("Existing-material and new-material authorizations cannot be combined")
        if protected and auth is None:
            raise ValueError("The original JasperPrism material is protected")
        if auth:
            if self.asset_path != JASPER_MATERIAL or auth.asset_path != self.asset_path:
                raise ValueError(
                    "Development authorization requires the exact JasperPrism asset path"
                )
            if self.action == "save":
                raise ValueError(
                    "Development authorization does not permit existing-material saving"
                )
            if self.action == "edit":
                import re

                if (
                    self.updates
                    or len(self.nodes) != 1
                    or len(self.connections) != 1
                    or len(self.properties) != 1
                ):
                    raise ValueError(
                        "Authorization permits only the missing contrast Add and connections"
                    )
                node, link, prop = self.nodes[0], self.connections[0], self.properties[0]
                if (
                    node.id != "contrast_add"
                    or node.type != "Add"
                    or node.parameters != {"const_b": 0.5}
                    or not re.fullmatch(r"[A-F0-9]{32}", link.from_node)
                    or link.from_output != ""
                    or link.to_node != node.id
                    or link.to_input != "A"
                    or prop.from_node != node.id
                    or prop.from_output != ""
                    or prop.property != "EmissiveColor"
                ):
                    raise ValueError(
                        "Authorization permits only the exact contrast completion recipe"
                    )
        test_target = self.asset_path.casefold() == FORGE_TEST_MATERIAL.casefold()
        if test_target and self.asset_path != FORGE_TEST_MATERIAL:
            raise ValueError("Use the exact canonical ForgeMCP test-material path")
        if creation_auth is not None:
            if self.asset_path != FORGE_TEST_MATERIAL or creation_auth.asset_path != self.asset_path:
                raise ValueError("Creation authorization permits only the exact ForgeMCP test-material path")
            if self.action != "edit" or self.updates:
                raise ValueError("Creation authorization permits only a new-material graph recipe")
        if self.action != "edit" and (
            self.nodes or self.connections or self.properties or self.updates
        ):
            raise ValueError("Compile/save previews cannot contain graph edits")
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("Node aliases must be unique")
        targets = [(c.to_node, c.to_input) for c in self.connections]
        if len(targets) != len(set(targets)):
            raise ValueError("Duplicate destination input")
        if len({u.node_id for u in self.updates}) != len(self.updates):
            raise ValueError("Use a single update per expression")
        edges = {}
        for c in self.connections:
            edges.setdefault(c.from_node, []).append(c.to_node)
        active, done = set(), set()

        def visit(node):
            if node in active:
                raise ValueError("Material graph cycles are unsupported")
            if node in done:
                return
            active.add(node)
            for target in edges.get(node, []):
                visit(target)
            active.remove(node)
            done.add(node)

        for node in edges:
            visit(node)
        return self
