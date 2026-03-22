"""Tests for Universal Node Engine type system."""

import pytest
from pydantic import ValidationError

from mascarade.node_engine.types import (
    ArrayType,
    DomainType,
    MapType,
    NodePortDefinition,
    OptionalType,
    PrimitiveType,
    PortType,
    StreamType,
    UnionType,
)


class TestPrimitiveTypes:
    """Test suite for primitive types."""

    def test_primitive_type_values(self):
        """Primitive types should have correct string values."""
        assert PrimitiveType.STRING == "string"
        assert PrimitiveType.NUMBER == "number"
        assert PrimitiveType.INTEGER == "integer"
        assert PrimitiveType.BOOLEAN == "boolean"
        assert PrimitiveType.BINARY == "binary"
        assert PrimitiveType.JSON == "json"
        assert PrimitiveType.VOID == "void"

    def test_primitive_type_enum(self):
        """Primitive types should be string enums."""
        assert isinstance(PrimitiveType.STRING, str)
        assert PrimitiveType.STRING.value == "string"


class TestArrayType:
    """Test suite for array types."""

    def test_array_of_primitives(self):
        """Array type should wrap primitive types."""
        arr = ArrayType(element=PrimitiveType.STRING)
        assert arr.kind == "array"
        assert arr.element == PrimitiveType.STRING

    def test_array_of_arrays(self):
        """Array type should support nested arrays."""
        inner = ArrayType(element=PrimitiveType.INTEGER)
        outer = ArrayType(element=inner)
        assert outer.kind == "array"
        assert outer.element.kind == "array"
        assert outer.element.element == PrimitiveType.INTEGER

    def test_array_type_serialization(self):
        """Array type should serialize to dict."""
        arr = ArrayType(element=PrimitiveType.NUMBER)
        data = arr.model_dump()
        assert data["kind"] == "array"
        assert data["element"] == "number"


class TestMapType:
    """Test suite for map types."""

    def test_map_primitive_key_primitive_value(self):
        """Map type with primitive key and value."""
        m = MapType(key=PrimitiveType.STRING, value=PrimitiveType.INTEGER)
        assert m.kind == "map"
        assert m.key == PrimitiveType.STRING
        assert m.value == PrimitiveType.INTEGER

    def test_map_with_complex_value(self):
        """Map type should support complex values."""
        arr = ArrayType(element=PrimitiveType.STRING)
        m = MapType(key=PrimitiveType.STRING, value=arr)
        assert m.kind == "map"
        assert m.value.kind == "array"

    def test_map_type_serialization(self):
        """Map type should serialize correctly."""
        m = MapType(key=PrimitiveType.STRING, value=PrimitiveType.NUMBER)
        data = m.model_dump()
        assert data["kind"] == "map"
        assert data["key"] == "string"
        assert data["value"] == "number"


class TestOptionalType:
    """Test suite for optional types."""

    def test_optional_primitive(self):
        """Optional type should wrap primitive."""
        opt = OptionalType(inner=PrimitiveType.STRING)
        assert opt.kind == "optional"
        assert opt.inner == PrimitiveType.STRING

    def test_optional_complex(self):
        """Optional type should wrap complex types."""
        arr = ArrayType(element=PrimitiveType.INTEGER)
        opt = OptionalType(inner=arr)
        assert opt.kind == "optional"
        assert opt.inner.kind == "array"

    def test_optional_type_serialization(self):
        """Optional type should serialize correctly."""
        opt = OptionalType(inner=PrimitiveType.BOOLEAN)
        data = opt.model_dump()
        assert data["kind"] == "optional"
        assert data["inner"] == "boolean"


class TestUnionType:
    """Test suite for union types."""

    def test_union_of_primitives(self):
        """Union type should support multiple primitive variants."""
        union = UnionType(variants=[PrimitiveType.STRING, PrimitiveType.INTEGER])
        assert union.kind == "union"
        assert len(union.variants) == 2
        assert PrimitiveType.STRING in union.variants
        assert PrimitiveType.INTEGER in union.variants

    def test_union_of_complex_types(self):
        """Union type should support complex type variants."""
        arr = ArrayType(element=PrimitiveType.STRING)
        m = MapType(key=PrimitiveType.STRING, value=PrimitiveType.NUMBER)
        union = UnionType(variants=[arr, m])
        assert union.kind == "union"
        assert len(union.variants) == 2

    def test_union_type_serialization(self):
        """Union type should serialize correctly."""
        union = UnionType(variants=[PrimitiveType.STRING, PrimitiveType.NUMBER])
        data = union.model_dump()
        assert data["kind"] == "union"
        assert len(data["variants"]) == 2


class TestStreamType:
    """Test suite for stream types."""

    def test_stream_of_primitives(self):
        """Stream type should wrap primitive element type."""
        stream = StreamType(element=PrimitiveType.STRING)
        assert stream.kind == "stream"
        assert stream.element == PrimitiveType.STRING

    def test_stream_of_complex(self):
        """Stream type should support complex element types."""
        arr = ArrayType(element=PrimitiveType.INTEGER)
        stream = StreamType(element=arr)
        assert stream.kind == "stream"
        assert stream.element.kind == "array"

    def test_stream_type_serialization(self):
        """Stream type should serialize correctly."""
        stream = StreamType(element=PrimitiveType.JSON)
        data = stream.model_dump()
        assert data["kind"] == "stream"
        assert data["element"] == "json"


class TestDomainType:
    """Test suite for domain-specific types."""

    def test_domain_type_creation(self):
        """Domain type should capture domain, name, and schema."""
        dt = DomainType(
            domain="ai",
            name="LLMResponse",
            schema_def={"content": "string", "model": "string"},
        )
        assert dt.kind == "domain"
        assert dt.domain == "ai"
        assert dt.name == "LLMResponse"
        assert dt.schema_def["content"] == "string"

    def test_domain_type_default_schema(self):
        """Domain type should have empty schema by default."""
        dt = DomainType(domain="db", name="QueryResult")
        assert dt.kind == "domain"
        assert dt.schema_def == {}

    def test_domain_type_serialization(self):
        """Domain type should serialize correctly."""
        dt = DomainType(domain="ai", name="Embedding", schema_def={"vector": "array"})
        data = dt.model_dump(by_alias=True)
        assert data["kind"] == "domain"
        assert data["domain"] == "ai"
        assert data["name"] == "Embedding"
        assert data["schema"] == {"vector": "array"}


class TestNodePortDefinition:
    """Test suite for node port definitions."""

    def test_port_definition_required(self):
        """Port definition with required field."""
        port = NodePortDefinition(
            id="input1",
            label="Input 1",
            type=PrimitiveType.STRING,
            required=True,
            description="A required string input",
        )
        assert port.id == "input1"
        assert port.label == "Input 1"
        assert port.type == PrimitiveType.STRING
        assert port.required is True
        assert port.description == "A required string input"

    def test_port_definition_optional_with_default(self):
        """Port definition with optional and default value."""
        port = NodePortDefinition(
            id="threshold",
            label="Threshold",
            type=PrimitiveType.NUMBER,
            required=False,
            default=0.5,
            description="Optional threshold with default",
        )
        assert port.id == "threshold"
        assert port.required is False
        assert port.default == 0.5

    def test_port_definition_complex_type(self):
        """Port definition should support complex types."""
        arr_type = ArrayType(element=PrimitiveType.INTEGER)
        port = NodePortDefinition(
            id="data", label="Data", type=arr_type, description="Array of integers"
        )
        assert port.id == "data"
        assert port.type.kind == "array"
        assert port.type.element == PrimitiveType.INTEGER

    def test_port_definition_defaults(self):
        """Port definition should have sensible defaults."""
        port = NodePortDefinition(
            id="simple", label="Simple", type=PrimitiveType.STRING
        )
        assert port.required is True
        assert port.default is None
        assert port.description == ""

    def test_port_definition_serialization(self):
        """Port definition should serialize to dict."""
        port = NodePortDefinition(
            id="output1",
            label="Output 1",
            type=PrimitiveType.BOOLEAN,
            required=True,
            description="Boolean output",
        )
        data = port.model_dump()
        assert data["id"] == "output1"
        assert data["label"] == "Output 1"
        assert data["type"] == "boolean"
        assert data["required"] is True
        assert data["description"] == "Boolean output"


class TestPortType:
    """Test suite for PortType model."""

    def test_basic_data_port(self):
        pt = PortType(name="prompt", type="string")
        assert pt.name == "prompt"
        assert pt.effective_type == "string"
        assert pt.is_primitive is True

    def test_is_array(self):
        pt = PortType(name="items", type="array<string>")
        assert pt.is_array is True
        assert pt.is_primitive is False

    def test_is_map(self):
        pt = PortType(name="kv", type="map<string,number>")
        assert pt.is_map is True

    def test_is_stream(self):
        pt = PortType(name="events", type="stream<json>")
        assert pt.is_stream is True

    def test_domain_type_port(self):
        pt = PortType(name="resp", type="ai.LLMResponse")
        assert pt.is_primitive is False

    def test_empty_name_with_type_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PortType(name="", type="string")

    def test_empty_type_with_name_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PortType(name="foo", type="")

    def test_type_descriptor_primitive_kind_bypasses_validation(self):
        from mascarade.node_engine.types import PortKind
        pt = PortType(name=PrimitiveType.STRING, type="", kind=PortKind.PRIMITIVE)
        assert pt.kind == PortKind.PRIMITIVE


class TestDomainTypeValidation:
    """Additional DomainType validation tests."""

    def test_qualified_name(self):
        dt = DomainType(domain="electronics", name="PCBLayout", schema={})
        assert dt.qualified_name == "electronics.PCBLayout"
        assert dt.full_name == "electronics.PCBLayout"

    def test_validate_schema_empty(self):
        dt = DomainType(domain="ai", name="X", schema={})
        valid, err = dt.validate_schema({"anything": 1})
        assert valid is True
        assert err is None

    def test_validate_schema_required_field_missing(self):
        dt = DomainType(
            domain="ai", name="Y",
            schema={"required": ["name"], "properties": {}},
        )
        valid, err = dt.validate_schema({})
        assert valid is False
        assert "name" in err

    def test_validate_schema_enum_violation(self):
        dt = DomainType(
            domain="ai", name="Z",
            schema={"properties": {"status": {"enum": ["ok", "error"]}}},
        )
        valid, err = dt.validate_schema({"status": "unknown"})
        assert valid is False
        assert "enum" in err

    def test_validate_schema_enum_ok(self):
        dt = DomainType(
            domain="ai", name="Z",
            schema={"properties": {"status": {"enum": ["ok", "error"]}}},
        )
        valid, err = dt.validate_schema({"status": "ok"})
        assert valid is True

    def test_domain_empty_name_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            DomainType(domain="", name="Foo", schema={})

    def test_name_empty_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            DomainType(domain="ai", name="", schema={})


class TestHelperFunctions:
    """Test port helper functions."""

    def test_primitive_port(self):
        from mascarade.node_engine.types import PortDirection, primitive_port
        p = primitive_port("voltage", PortDirection.INPUT, PrimitiveType.NUMBER)
        assert p.name == "voltage"
        assert p.effective_type == "number"
        assert p.direction == PortDirection.INPUT

    def test_primitive_port_swapped_args(self):
        from mascarade.node_engine.types import PortDirection, primitive_port
        p = primitive_port("temp", PrimitiveType.STRING, PortDirection.OUTPUT)
        assert p.direction == PortDirection.OUTPUT
        assert p.effective_type == "string"

    def test_domain_port(self):
        from mascarade.node_engine.types import PortDirection, domain_port
        p = domain_port("output", PortDirection.OUTPUT, "ai", "LLMResponse")
        assert p.effective_type == "ai.LLMResponse"

    def test_array_port_string_element(self):
        from mascarade.node_engine.types import PortDirection, array_port
        p = array_port("items", PortDirection.INPUT, "string")
        assert p.effective_type == "array<string>"
        assert p.is_array is True

    def test_void_port(self):
        from mascarade.node_engine.types import PortDirection, void_port
        p = void_port("done", PortDirection.OUTPUT)
        assert p.effective_type == "void"
        assert p.is_primitive is True


class TestPortTypeUnion:
    """Test PortTypeUnion encompasses all expected types."""

    def test_primitive_in_union(self):
        from mascarade.node_engine.types import PortTypeUnion
        import typing
        args = typing.get_args(PortTypeUnion)
        assert PrimitiveType in args

    def test_array_type_in_union(self):
        from mascarade.node_engine.types import PortTypeUnion
        import typing
        args = typing.get_args(PortTypeUnion)
        assert ArrayType in args

    def test_domain_type_in_union(self):
        from mascarade.node_engine.types import PortTypeUnion
        import typing
        args = typing.get_args(PortTypeUnion)
        assert DomainType in args


class TestTypeSystemIntegration:
    """Integration tests for the type system."""

    def test_deeply_nested_types(self):
        """Type system should support deep nesting."""
        # Map<String, Array<Optional<Integer>>>
        inner_opt = OptionalType(inner=PrimitiveType.INTEGER)
        inner_arr = ArrayType(element=inner_opt)
        m = MapType(key=PrimitiveType.STRING, value=inner_arr)

        assert m.kind == "map"
        assert m.value.kind == "array"
        assert m.value.element.kind == "optional"
        assert m.value.element.inner == PrimitiveType.INTEGER

    def test_union_with_optional(self):
        """Union type with optional variants."""
        opt_str = OptionalType(inner=PrimitiveType.STRING)
        opt_int = OptionalType(inner=PrimitiveType.INTEGER)
        union = UnionType(variants=[opt_str, opt_int])

        assert union.kind == "union"
        assert len(union.variants) == 2
        assert all(v.kind == "optional" for v in union.variants)

    def test_stream_of_domain_type(self):
        """Stream type containing domain-specific type."""
        domain = DomainType(
            domain="ai", name="ChatMessage", schema_def={"role": "string", "content": "string"}
        )
        stream = StreamType(element=domain)

        assert stream.kind == "stream"
        assert stream.element.kind == "domain"
        assert stream.element.domain == "ai"

    def test_port_with_complex_nested_type(self):
        """Port definition with complex nested type."""
        # Stream<Map<String, Array<Integer>>>
        arr = ArrayType(element=PrimitiveType.INTEGER)
        m = MapType(key=PrimitiveType.STRING, value=arr)
        stream = StreamType(element=m)

        port = NodePortDefinition(
            id="complex_stream",
            label="Complex Stream",
            type=stream,
            required=False,
            description="A complex nested type",
        )

        assert port.type.kind == "stream"
        assert port.type.element.kind == "map"
        assert port.type.element.value.kind == "array"
