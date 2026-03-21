# Universal Type System Specification

**Document ID:** SPEC-029-TS
**Version:** 1.0.0
**Date:** 2026-03-17
**Status:** Draft — Type System Foundation
**Parent Specification:** UNIVERSAL_NODE_ENGINE_SPECIFICATION_2026-03-15.md

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Type Hierarchy](#2-type-hierarchy)
3. [Primitive Types](#3-primitive-types)
4. [Composite Types](#4-composite-types)
5. [Domain-Specific Types](#5-domain-specific-types)
6. [Validation Rules](#6-validation-rules)
7. [Coercion Rules](#7-coercion-rules)
8. [Type Adapter Interface](#8-type-adapter-interface)
9. [Port Type System](#9-port-type-system)
10. [Implementation Guidelines](#10-implementation-guidelines)
11. [Examples](#11-examples)

---

## 1. Introduction

### 1.1 Purpose

The Universal Type System provides a comprehensive, hierarchical type framework for the Universal Node Engine. It enables:

- **Type Safety** — Compile-time and runtime validation of data flowing through graph nodes
- **Interoperability** — Cross-domain data exchange via explicit type adapters
- **Extensibility** — Plugin developers can register custom domain types
- **Composability** — Complex types built from primitive types with clear semantics

### 1.2 Design Principles

1. **Explicit over Implicit** — Type conversions are explicit via adapters, not automatic coercion (except for safe primitive conversions)
2. **Pydantic-First** — All types are Pydantic models for validation and serialization
3. **Domain-Aware** — Types belong to specific domains, preventing accidental cross-domain connections
4. **Fail-Fast** — Invalid types caught at graph validation time, not execution time
5. **Self-Documenting** — Types include descriptions, constraints, and examples

### 1.3 Type System Goals

| Goal | Implementation |
|------|---------------|
| **Compile-time safety** | Pydantic models + mypy static checking |
| **Runtime validation** | Pydantic validation on all node I/O |
| **Cross-domain safety** | Explicit TypeAdapter interface |
| **Performance** | Validation overhead <1ms per node |
| **Developer experience** | Auto-generated TypeScript definitions |

---

## 2. Type Hierarchy

### 2.1 Abstract Type Tree

```
PortType (abstract base class)
├── PrimitiveType
│   ├── StringType
│   ├── IntegerType
│   ├── FloatType
│   ├── BooleanType
│   ├── BytesType
│   └── JSONType
├── CompositeType
│   ├── ListType[T]
│   ├── DictType[K, V]
│   ├── TupleType[T1, T2, ...]
│   ├── UnionType[T1, T2, ...]
│   └── OptionalType[T]
└── DomainType (abstract)
    ├── AIDomainType
    │   ├── LLMResponseType
    │   ├── EmbeddingVectorType
    │   ├── ConversationHistoryType
    │   └── PromptTemplateType
    ├── CADDomainType
    │   ├── MeshDataType
    │   ├── ToolpathType
    │   ├── SchematicType
    │   ├── PCBLayoutType
    │   ├── BOMType
    │   └── DesignParametersType
    ├── ElectronicsDomainType
    │   ├── NetlistType
    │   ├── WaveformType
    │   ├── DRCReportType
    │   ├── FirmwareBinaryType
    │   └── ComponentSpecType
    └── HardwareDomainType
        ├── MIDIMessageType
        ├── DMXFrameType
        ├── SerialDataType
        ├── HTTPResponseType
        └── GPIOStateType
```

### 2.2 Base PortType Interface

```python
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T')

class PortType(ABC, BaseModel):
    """
    Abstract base class for all port types in the Universal Node Engine.

    All port types must:
    - Implement validate() for runtime type checking
    - Implement coerce() for safe type conversions
    - Provide schema() for API documentation
    - Define domain membership
    """

    type_name: str = Field(..., description="Unique type identifier")
    domain: str | None = Field(None, description="Domain this type belongs to (None for primitives)")
    description: str = Field("", description="Human-readable type description")
    nullable: bool = Field(False, description="Whether this type accepts None values")

    @abstractmethod
    def validate(self, value: Any) -> tuple[bool, str | None]:
        """
        Validate that a value conforms to this type.

        Returns:
            (is_valid, error_message)
        """
        ...

    @abstractmethod
    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        """
        Attempt to coerce a value to this type.

        Returns:
            (coerced_value, error_message)

        Raises:
            TypeError: If coercion is not supported for the given value type
        """
        ...

    @abstractmethod
    def schema(self) -> dict[str, Any]:
        """
        Return JSON schema for this type (for API docs and UI generation).
        """
        ...

    def is_compatible_with(self, other: "PortType") -> bool:
        """
        Check if this type can accept values from another type.
        Default: exact match. Override for domain-specific compatibility.
        """
        return self.type_name == other.type_name
```

---

## 3. Primitive Types

### 3.1 Overview

Primitive types are domain-agnostic, fundamental data types. They support automatic coercion according to the rules in Section 7.

| Type | Python Type | JSON Type | Example | Nullable Default |
|------|------------|-----------|---------|-----------------|
| `String` | `str` | `string` | `"hello world"` | No |
| `Integer` | `int` | `number` | `42` | No |
| `Float` | `float` | `number` | `3.14` | No |
| `Boolean` | `bool` | `boolean` | `true` | No |
| `Bytes` | `bytes` | `string` (base64) | `b"binary"` | No |
| `JSON` | `dict` | `object` | `{"key": "value"}` | No |

### 3.2 StringType

```python
class StringType(PortType):
    """String type with optional constraints."""

    type_name: str = "String"
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None  # Regex pattern

    def validate(self, value: Any) -> tuple[bool, str | None]:
        if not isinstance(value, str):
            return False, f"Expected string, got {type(value).__name__}"

        if self.min_length and len(value) < self.min_length:
            return False, f"String too short (min: {self.min_length})"

        if self.max_length and len(value) > self.max_length:
            return False, f"String too long (max: {self.max_length})"

        if self.pattern:
            import re
            if not re.match(self.pattern, value):
                return False, f"String does not match pattern: {self.pattern}"

        return True, None

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        """Coerce primitives to string."""
        if isinstance(value, str):
            return value, None
        if isinstance(value, (int, float, bool)):
            return str(value), None
        if isinstance(value, bytes):
            try:
                return value.decode('utf-8'), None
            except UnicodeDecodeError as e:
                return None, f"Cannot decode bytes to UTF-8: {e}"

        return None, f"Cannot coerce {type(value).__name__} to String"

    def schema(self) -> dict[str, Any]:
        s = {"type": "string"}
        if self.min_length:
            s["minLength"] = self.min_length
        if self.max_length:
            s["maxLength"] = self.max_length
        if self.pattern:
            s["pattern"] = self.pattern
        return s
```

### 3.3 IntegerType

```python
class IntegerType(PortType):
    """Integer type with optional range constraints."""

    type_name: str = "Integer"
    minimum: int | None = None
    maximum: int | None = None

    def validate(self, value: Any) -> tuple[bool, str | None]:
        if not isinstance(value, int) or isinstance(value, bool):
            return False, f"Expected integer, got {type(value).__name__}"

        if self.minimum is not None and value < self.minimum:
            return False, f"Value {value} < minimum {self.minimum}"

        if self.maximum is not None and value > self.maximum:
            return False, f"Value {value} > maximum {self.maximum}"

        return True, None

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        """Coerce from string, float, bool to int."""
        if isinstance(value, int) and not isinstance(value, bool):
            return value, None
        if isinstance(value, bool):
            return int(value), None
        if isinstance(value, float):
            if value.is_integer():
                return int(value), None
            return None, f"Float {value} is not an integer value"
        if isinstance(value, str):
            try:
                return int(value), None
            except ValueError:
                return None, f"Cannot parse '{value}' as integer"

        return None, f"Cannot coerce {type(value).__name__} to Integer"

    def schema(self) -> dict[str, Any]:
        s = {"type": "integer"}
        if self.minimum is not None:
            s["minimum"] = self.minimum
        if self.maximum is not None:
            s["maximum"] = self.maximum
        return s
```

### 3.4 FloatType

```python
class FloatType(PortType):
    """Floating-point number type."""

    type_name: str = "Float"
    minimum: float | None = None
    maximum: float | None = None

    def validate(self, value: Any) -> tuple[bool, str | None]:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False, f"Expected number, got {type(value).__name__}"

        float_value = float(value)

        if self.minimum is not None and float_value < self.minimum:
            return False, f"Value {float_value} < minimum {self.minimum}"

        if self.maximum is not None and float_value > self.maximum:
            return False, f"Value {float_value} > maximum {self.maximum}"

        return True, None

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        """Coerce from int, string, bool to float."""
        if isinstance(value, float):
            return value, None
        if isinstance(value, int):
            return float(value), None
        if isinstance(value, bool):
            return float(value), None
        if isinstance(value, str):
            try:
                return float(value), None
            except ValueError:
                return None, f"Cannot parse '{value}' as float"

        return None, f"Cannot coerce {type(value).__name__} to Float"

    def schema(self) -> dict[str, Any]:
        s = {"type": "number"}
        if self.minimum is not None:
            s["minimum"] = self.minimum
        if self.maximum is not None:
            s["maximum"] = self.maximum
        return s
```

### 3.5 BooleanType

```python
class BooleanType(PortType):
    """Boolean type."""

    type_name: str = "Boolean"

    def validate(self, value: Any) -> tuple[bool, str | None]:
        if not isinstance(value, bool):
            return False, f"Expected boolean, got {type(value).__name__}"
        return True, None

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        """Coerce from int (0/1), string ('true'/'false') to bool."""
        if isinstance(value, bool):
            return value, None
        if isinstance(value, int):
            if value in (0, 1):
                return bool(value), None
            return None, f"Only 0 and 1 can be coerced to bool, got {value}"
        if isinstance(value, str):
            lower = value.lower()
            if lower in ("true", "1", "yes"):
                return True, None
            if lower in ("false", "0", "no"):
                return False, None
            return None, f"Cannot parse '{value}' as boolean"

        return None, f"Cannot coerce {type(value).__name__} to Boolean"

    def schema(self) -> dict[str, Any]:
        return {"type": "boolean"}
```

### 3.6 BytesType

```python
class BytesType(PortType):
    """Binary data type."""

    type_name: str = "Bytes"
    max_size: int | None = None  # Max size in bytes

    def validate(self, value: Any) -> tuple[bool, str | None]:
        if not isinstance(value, bytes):
            return False, f"Expected bytes, got {type(value).__name__}"

        if self.max_size and len(value) > self.max_size:
            return False, f"Bytes too large ({len(value)} > {self.max_size})"

        return True, None

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        """Coerce from string (utf-8 or base64) to bytes."""
        if isinstance(value, bytes):
            return value, None
        if isinstance(value, str):
            # Try UTF-8 encoding first
            try:
                return value.encode('utf-8'), None
            except UnicodeEncodeError:
                pass
            # Try base64 decoding
            try:
                import base64
                return base64.b64decode(value), None
            except Exception as e:
                return None, f"Cannot decode string as base64: {e}"

        return None, f"Cannot coerce {type(value).__name__} to Bytes"

    def schema(self) -> dict[str, Any]:
        s = {"type": "string", "format": "byte"}
        if self.max_size:
            s["maxLength"] = self.max_size
        return s
```

### 3.7 JSONType

```python
class JSONType(PortType):
    """Arbitrary JSON-serializable data."""

    type_name: str = "JSON"

    def validate(self, value: Any) -> tuple[bool, str | None]:
        """Check if value is JSON-serializable."""
        import json
        try:
            json.dumps(value)
            return True, None
        except (TypeError, ValueError) as e:
            return False, f"Value is not JSON-serializable: {e}"

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        """Parse string as JSON, or return value as-is if already valid."""
        if isinstance(value, str):
            import json
            try:
                return json.loads(value), None
            except json.JSONDecodeError as e:
                return None, f"Invalid JSON string: {e}"

        # Already a valid JSON type
        if isinstance(value, (dict, list, int, float, str, bool, type(None))):
            return value, None

        return None, f"Cannot coerce {type(value).__name__} to JSON"

    def schema(self) -> dict[str, Any]:
        return {"type": "object"}
```

---

## 4. Composite Types

### 4.1 Overview

Composite types are generic containers that wrap other types. They enable complex data structures while maintaining type safety.

### 4.2 ListType[T]

```python
class ListType(PortType, Generic[T]):
    """List of homogeneous elements."""

    type_name: str = "List"
    element_type: PortType = Field(..., description="Type of list elements")
    min_items: int | None = None
    max_items: int | None = None

    def validate(self, value: Any) -> tuple[bool, str | None]:
        if not isinstance(value, list):
            return False, f"Expected list, got {type(value).__name__}"

        if self.min_items and len(value) < self.min_items:
            return False, f"List too short ({len(value)} < {self.min_items})"

        if self.max_items and len(value) > self.max_items:
            return False, f"List too long ({len(value)} > {self.max_items})"

        # Validate each element
        for i, item in enumerate(value):
            is_valid, error = self.element_type.validate(item)
            if not is_valid:
                return False, f"Item {i}: {error}"

        return True, None

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        """Coerce tuple to list, or wrap single value in list."""
        if isinstance(value, list):
            # Try to coerce each element
            coerced = []
            for i, item in enumerate(value):
                item_coerced, error = self.element_type.coerce(item)
                if error:
                    return None, f"Item {i}: {error}"
                coerced.append(item_coerced)
            return coerced, None

        if isinstance(value, tuple):
            return self.coerce(list(value))

        # Wrap single value
        coerced, error = self.element_type.coerce(value)
        if error:
            return None, error
        return [coerced], None

    def schema(self) -> dict[str, Any]:
        s = {
            "type": "array",
            "items": self.element_type.schema()
        }
        if self.min_items:
            s["minItems"] = self.min_items
        if self.max_items:
            s["maxItems"] = self.max_items
        return s
```

### 4.3 DictType[K, V]

```python
class DictType(PortType):
    """Dictionary with typed keys and values."""

    type_name: str = "Dict"
    key_type: PortType = Field(..., description="Type of dictionary keys")
    value_type: PortType = Field(..., description="Type of dictionary values")

    def validate(self, value: Any) -> tuple[bool, str | None]:
        if not isinstance(value, dict):
            return False, f"Expected dict, got {type(value).__name__}"

        for k, v in value.items():
            # Validate key
            is_valid, error = self.key_type.validate(k)
            if not is_valid:
                return False, f"Key '{k}': {error}"

            # Validate value
            is_valid, error = self.value_type.validate(v)
            if not is_valid:
                return False, f"Value for key '{k}': {error}"

        return True, None

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        if not isinstance(value, dict):
            return None, f"Cannot coerce {type(value).__name__} to Dict"

        coerced = {}
        for k, v in value.items():
            # Coerce key
            k_coerced, error = self.key_type.coerce(k)
            if error:
                return None, f"Key '{k}': {error}"

            # Coerce value
            v_coerced, error = self.value_type.coerce(v)
            if error:
                return None, f"Value for key '{k}': {error}"

            coerced[k_coerced] = v_coerced

        return coerced, None

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": self.value_type.schema()
        }
```

### 4.4 TupleType[T1, T2, ...]

```python
class TupleType(PortType):
    """Fixed-length tuple with heterogeneous types."""

    type_name: str = "Tuple"
    element_types: list[PortType] = Field(..., description="Types of each tuple element")

    def validate(self, value: Any) -> tuple[bool, str | None]:
        if not isinstance(value, (tuple, list)):
            return False, f"Expected tuple, got {type(value).__name__}"

        if len(value) != len(self.element_types):
            return False, f"Expected {len(self.element_types)} elements, got {len(value)}"

        for i, (item, expected_type) in enumerate(zip(value, self.element_types)):
            is_valid, error = expected_type.validate(item)
            if not is_valid:
                return False, f"Element {i}: {error}"

        return True, None

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        if isinstance(value, tuple):
            value = list(value)

        if not isinstance(value, list):
            return None, f"Cannot coerce {type(value).__name__} to Tuple"

        if len(value) != len(self.element_types):
            return None, f"Expected {len(self.element_types)} elements, got {len(value)}"

        coerced = []
        for i, (item, expected_type) in enumerate(zip(value, self.element_types)):
            item_coerced, error = expected_type.coerce(item)
            if error:
                return None, f"Element {i}: {error}"
            coerced.append(item_coerced)

        return tuple(coerced), None

    def schema(self) -> dict[str, Any]:
        return {
            "type": "array",
            "items": [et.schema() for et in self.element_types],
            "minItems": len(self.element_types),
            "maxItems": len(self.element_types)
        }
```

### 4.5 UnionType[T1, T2, ...]

```python
class UnionType(PortType):
    """Union of multiple types (value matches at least one)."""

    type_name: str = "Union"
    types: list[PortType] = Field(..., description="Possible types")

    def validate(self, value: Any) -> tuple[bool, str | None]:
        errors = []
        for t in self.types:
            is_valid, error = t.validate(value)
            if is_valid:
                return True, None
            errors.append(f"{t.type_name}: {error}")

        return False, f"Value does not match any union type: {'; '.join(errors)}"

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        """Try to coerce to first matching type."""
        errors = []
        for t in self.types:
            coerced, error = t.coerce(value)
            if not error:
                return coerced, None
            errors.append(f"{t.type_name}: {error}")

        return None, f"Cannot coerce to any union type: {'; '.join(errors)}"

    def schema(self) -> dict[str, Any]:
        return {"oneOf": [t.schema() for t in self.types]}
```

### 4.6 OptionalType[T]

```python
class OptionalType(PortType):
    """Optional wrapper (value can be None)."""

    type_name: str = "Optional"
    inner_type: PortType = Field(..., description="Inner type when value is not None")

    def validate(self, value: Any) -> tuple[bool, str | None]:
        if value is None:
            return True, None
        return self.inner_type.validate(value)

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        if value is None:
            return None, None
        return self.inner_type.coerce(value)

    def schema(self) -> dict[str, Any]:
        inner_schema = self.inner_type.schema()
        return {"anyOf": [inner_schema, {"type": "null"}]}
```

---

## 5. Domain-Specific Types

### 5.1 Overview

Domain-specific types encapsulate rich data structures specific to AI, CAD, Electronics, or Hardware domains. They are implemented as Pydantic models and registered with the type system.

### 5.2 AI Domain Types

#### 5.2.1 LLMResponseType

```python
from pydantic import BaseModel

class LLMResponse(BaseModel):
    """Response from an LLM provider."""
    content: str
    model: str
    provider: str
    usage: dict[str, int] = {}
    metadata: dict[str, Any] = {}

class LLMResponseType(PortType):
    type_name: str = "LLMResponse"
    domain: str = "AI"

    def validate(self, value: Any) -> tuple[bool, str | None]:
        try:
            LLMResponse.model_validate(value)
            return True, None
        except Exception as e:
            return False, str(e)

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        if isinstance(value, LLMResponse):
            return value, None
        if isinstance(value, dict):
            try:
                return LLMResponse.model_validate(value), None
            except Exception as e:
                return None, str(e)
        return None, f"Cannot coerce {type(value).__name__} to LLMResponse"

    def schema(self) -> dict[str, Any]:
        return LLMResponse.model_json_schema()
```

#### 5.2.2 EmbeddingVectorType

```python
class EmbeddingVector(BaseModel):
    """Vector embedding from a text encoder."""
    vector: list[float]
    model: str
    dimensions: int

class EmbeddingVectorType(PortType):
    type_name: str = "EmbeddingVector"
    domain: str = "AI"
    expected_dimensions: int | None = None

    def validate(self, value: Any) -> tuple[bool, str | None]:
        try:
            emb = EmbeddingVector.model_validate(value)
            if self.expected_dimensions and emb.dimensions != self.expected_dimensions:
                return False, f"Expected {self.expected_dimensions} dimensions, got {emb.dimensions}"
            return True, None
        except Exception as e:
            return False, str(e)

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        if isinstance(value, EmbeddingVector):
            return value, None
        if isinstance(value, dict):
            try:
                return EmbeddingVector.model_validate(value), None
            except Exception as e:
                return None, str(e)
        if isinstance(value, list) and all(isinstance(x, (int, float)) for x in value):
            # Raw vector provided, wrap it
            return EmbeddingVector(vector=value, model="unknown", dimensions=len(value)), None
        return None, f"Cannot coerce {type(value).__name__} to EmbeddingVector"

    def schema(self) -> dict[str, Any]:
        return EmbeddingVector.model_json_schema()
```

#### 5.2.3 ConversationHistoryType

```python
class ConversationHistory(BaseModel):
    """Chat conversation history."""
    messages: list[dict[str, str]]
    max_length: int | None = None

class ConversationHistoryType(PortType):
    type_name: str = "ConversationHistory"
    domain: str = "AI"

    def validate(self, value: Any) -> tuple[bool, str | None]:
        try:
            ConversationHistory.model_validate(value)
            return True, None
        except Exception as e:
            return False, str(e)

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        if isinstance(value, ConversationHistory):
            return value, None
        if isinstance(value, dict):
            try:
                return ConversationHistory.model_validate(value), None
            except Exception as e:
                return None, str(e)
        if isinstance(value, list):
            # Raw message list
            return ConversationHistory(messages=value), None
        return None, f"Cannot coerce {type(value).__name__} to ConversationHistory"

    def schema(self) -> dict[str, Any]:
        return ConversationHistory.model_json_schema()
```

### 5.3 CAD Domain Types

#### 5.3.1 MeshDataType

```python
class MeshData(BaseModel):
    """3D mesh geometry."""
    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, int, int]]
    normals: list[tuple[float, float, float]] | None = None
    metadata: dict[str, Any] = {}

class MeshDataType(PortType):
    type_name: str = "MeshData"
    domain: str = "CAD"

    def validate(self, value: Any) -> tuple[bool, str | None]:
        try:
            MeshData.model_validate(value)
            return True, None
        except Exception as e:
            return False, str(e)

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        if isinstance(value, MeshData):
            return value, None
        if isinstance(value, dict):
            try:
                return MeshData.model_validate(value), None
            except Exception as e:
                return None, str(e)
        return None, f"Cannot coerce {type(value).__name__} to MeshData"

    def schema(self) -> dict[str, Any]:
        return MeshData.model_json_schema()
```

#### 5.3.2 DesignParametersType

```python
class DesignParameters(BaseModel):
    """Parametric CAD design inputs."""
    parameters: dict[str, float | int | str]
    constraints: dict[str, Any] = {}
    target_application: str | None = None

class DesignParametersType(PortType):
    type_name: str = "DesignParameters"
    domain: str = "CAD"

    def validate(self, value: Any) -> tuple[bool, str | None]:
        try:
            DesignParameters.model_validate(value)
            return True, None
        except Exception as e:
            return False, str(e)

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        if isinstance(value, DesignParameters):
            return value, None
        if isinstance(value, dict):
            try:
                return DesignParameters.model_validate(value), None
            except Exception as e:
                return None, str(e)
        return None, f"Cannot coerce {type(value).__name__} to DesignParameters"

    def schema(self) -> dict[str, Any]:
        return DesignParameters.model_json_schema()
```

### 5.4 Electronics Domain Types

#### 5.4.1 NetlistType

```python
class Netlist(BaseModel):
    """Electronic circuit netlist."""
    components: list[dict[str, Any]]
    connections: list[dict[str, str]]
    format: str = "spice"  # spice, kicad, etc.

class NetlistType(PortType):
    type_name: str = "Netlist"
    domain: str = "Electronics"

    def validate(self, value: Any) -> tuple[bool, str | None]:
        try:
            Netlist.model_validate(value)
            return True, None
        except Exception as e:
            return False, str(e)

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        if isinstance(value, Netlist):
            return value, None
        if isinstance(value, dict):
            try:
                return Netlist.model_validate(value), None
            except Exception as e:
                return None, str(e)
        return None, f"Cannot coerce {type(value).__name__} to Netlist"

    def schema(self) -> dict[str, Any]:
        return Netlist.model_json_schema()
```

### 5.5 Hardware Domain Types

#### 5.5.1 MIDIMessageType

```python
class MIDIMessage(BaseModel):
    """MIDI protocol message."""
    status: int  # Status byte
    data1: int   # First data byte
    data2: int   # Second data byte
    channel: int | None = None
    timestamp: float | None = None

class MIDIMessageType(PortType):
    type_name: str = "MIDIMessage"
    domain: str = "Hardware"

    def validate(self, value: Any) -> tuple[bool, str | None]:
        try:
            msg = MIDIMessage.model_validate(value)
            # Validate MIDI byte ranges
            if not (0 <= msg.status <= 255):
                return False, "Status byte must be 0-255"
            if not (0 <= msg.data1 <= 127):
                return False, "Data1 must be 0-127"
            if not (0 <= msg.data2 <= 127):
                return False, "Data2 must be 0-127"
            return True, None
        except Exception as e:
            return False, str(e)

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        if isinstance(value, MIDIMessage):
            return value, None
        if isinstance(value, dict):
            try:
                return MIDIMessage.model_validate(value), None
            except Exception as e:
                return None, str(e)
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            return MIDIMessage(status=value[0], data1=value[1], data2=value[2]), None
        return None, f"Cannot coerce {type(value).__name__} to MIDIMessage"

    def schema(self) -> dict[str, Any]:
        return MIDIMessage.model_json_schema()
```

---

## 6. Validation Rules

### 6.1 Validation Phases

| Phase | When | What | Implemented By |
|-------|------|------|---------------|
| **Schema Validation** | Graph save | Graph structure is well-formed | API layer |
| **Type Validation** | Graph save | All connections type-compatible | Type system |
| **Value Validation** | Node execution | Input values conform to types | Pydantic models |
| **Constraint Validation** | Node execution | Values satisfy constraints | Node workers |

### 6.2 Connection Validation Rules

**Rule 1: Type Compatibility**
```
A connection from Port A (type TA) to Port B (type TB) is valid if:
  - TA == TB (exact match), OR
  - TA can be automatically coerced to TB (primitive coercion), OR
  - An explicit TypeAdapter exists for TA → TB (domain conversion)
```

**Rule 2: Domain Boundaries**
```
Cross-domain connections require explicit TypeAdapter:
  - AI → CAD: LLMResponse → DesignParameters
  - CAD → Electronics: MeshData → ComponentGeometry
  - Electronics → Hardware: FirmwareBinary → FlashableImage
```

**Rule 3: Cardinality**
```
- One-to-one: Single output → Single input (default)
- One-to-many: Single output → Multiple inputs (broadcast)
- Many-to-one: Multiple outputs → Single input (requires merge node)
```

### 6.3 Runtime Validation

```python
class NodeExecutionContext:
    """Context for validating and executing a node."""

    def validate_inputs(self, inputs: dict[str, Any], port_defs: dict[str, PortDefinition]) -> list[str]:
        """
        Validate all inputs before execution.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required ports
        for name, port_def in port_defs.items():
            if port_def.required and name not in inputs:
                errors.append(f"Missing required input: {name}")

        # Validate each input value
        for name, value in inputs.items():
            if name not in port_defs:
                errors.append(f"Unknown input port: {name}")
                continue

            port_def = port_defs[name]
            is_valid, error = port_def.type.validate(value)
            if not is_valid:
                errors.append(f"Input '{name}': {error}")

        return errors
```

---

## 7. Coercion Rules

### 7.1 Automatic Primitive Coercion

| From | To | Rule | Example |
|------|-----|------|---------|
| `int` | `float` | Always safe | `42 → 42.0` |
| `int` | `str` | Always safe | `42 → "42"` |
| `int` | `bool` | Only 0/1 | `1 → True` |
| `float` | `int` | Only if `.is_integer()` | `42.0 → 42` |
| `float` | `str` | Always safe | `3.14 → "3.14"` |
| `bool` | `int` | Always safe | `True → 1` |
| `bool` | `str` | Always safe | `True → "True"` |
| `str` | `int` | If parseable | `"42" → 42` |
| `str` | `float` | If parseable | `"3.14" → 3.14` |
| `str` | `bool` | Specific strings | `"true" → True` |
| `str` | `bytes` | UTF-8 or base64 | `"hello" → b"hello"` |
| `bytes` | `str` | UTF-8 decode | `b"hello" → "hello"` |
| `list[T]` | `Optional[list[T]]` | Wrap | `[1, 2] → Some([1, 2])` |
| `T` | `list[T]` | Wrap single value | `42 → [42]` |
| `tuple` | `list` | Convert | `(1, 2) → [1, 2]` |

### 7.2 Composite Coercion

```python
# List element coercion
List[Integer] ← List[String]  # If each string is parseable as int
  ["1", "2", "3"] → [1, 2, 3]

# Dict value coercion
Dict[String, Float] ← Dict[String, Integer]
  {"a": 1, "b": 2} → {"a": 1.0, "b": 2.0}

# Optional wrapping
Optional[T] ← T  # Always safe
  42 → Some(42)
```

### 7.3 No Automatic Cross-Domain Coercion

Domain-specific types **never** auto-coerce. Explicit TypeAdapters required:

```python
# ❌ NOT ALLOWED - Compile error
LLMResponse → DesignParameters  # Different domains

# ✅ ALLOWED - Via TypeAdapter
LLMResponse → TypeAdapter[LLMResponse, DesignParameters] → DesignParameters
```

---

## 8. Type Adapter Interface

### 8.1 Abstract TypeAdapter

```python
from abc import ABC, abstractmethod

class TypeAdapter(ABC, Generic[TSource, TTarget]):
    """
    Adapter for converting between incompatible types (typically cross-domain).

    TypeAdapters are registered in the AdapterRegistry and automatically
    inserted by the graph compiler when cross-domain connections are detected.
    """

    source_type: PortType
    target_type: PortType

    @abstractmethod
    async def convert(self, value: TSource) -> TTarget:
        """
        Convert source value to target type.

        Raises:
            AdapterError: If conversion fails
        """
        ...

    @abstractmethod
    def can_convert(self, value: TSource) -> bool:
        """Check if this adapter can convert the given value."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description of what this adapter does."""
        return f"Convert {self.source_type.type_name} to {self.target_type.type_name}"
```

### 8.2 Example: LLMResponse → DesignParameters

```python
class LLMResponseToDesignParametersAdapter(TypeAdapter[LLMResponse, DesignParameters]):
    """
    Extract parametric CAD design parameters from LLM-generated text.

    The LLM output should contain JSON with design parameters.
    Example LLM output:
      {
        "length": 100,
        "width": 50,
        "height": 20,
        "material": "aluminum"
      }
    """

    source_type = LLMResponseType()
    target_type = DesignParametersType()

    async def convert(self, value: LLMResponse) -> DesignParameters:
        import json

        try:
            # Parse LLM response content as JSON
            params = json.loads(value.content)

            if not isinstance(params, dict):
                raise AdapterError("LLM output is not a JSON object")

            return DesignParameters(
                parameters=params,
                metadata={"source": "llm", "model": value.model}
            )
        except json.JSONDecodeError as e:
            raise AdapterError(f"LLM output is not valid JSON: {e}")

    def can_convert(self, value: LLMResponse) -> bool:
        import json
        try:
            params = json.loads(value.content)
            return isinstance(params, dict)
        except:
            return False
```

### 8.3 Adapter Registry

```python
class AdapterRegistry:
    """Registry of type adapters for cross-domain conversions."""

    def __init__(self):
        self._adapters: dict[tuple[str, str], TypeAdapter] = {}

    def register(self, adapter: TypeAdapter) -> None:
        """Register a new type adapter."""
        key = (adapter.source_type.type_name, adapter.target_type.type_name)
        if key in self._adapters:
            raise ValueError(f"Adapter {key} already registered")
        self._adapters[key] = adapter

    def get_adapter(self, source_type: PortType, target_type: PortType) -> TypeAdapter | None:
        """Find adapter for converting source to target type."""
        key = (source_type.type_name, target_type.type_name)
        return self._adapters.get(key)

    def can_convert(self, source_type: PortType, target_type: PortType) -> bool:
        """Check if conversion is possible."""
        return self.get_adapter(source_type, target_type) is not None
```

---

## 9. Port Type System

### 9.1 Port Definition

```python
@dataclass
class PortDefinition:
    """
    Definition of a node port (input or output).

    Ports are the connection points on nodes where data flows in/out.
    Each port has a type, which determines what values it can accept.
    """

    name: str
    type: PortType
    direction: Literal["input", "output"]
    required: bool = True
    default_value: Any | None = None
    description: str = ""

    def validate(self, value: Any) -> tuple[bool, str | None]:
        """Validate a value against this port's type."""
        if value is None and not self.required:
            return True, None
        if value is None and self.required:
            return False, "Value is required"
        return self.type.validate(value)

    def coerce(self, value: Any) -> tuple[Any | None, str | None]:
        """Attempt to coerce value to this port's type."""
        if value is None and not self.required:
            return None, None
        return self.type.coerce(value)
```

### 9.2 Port Connection

```python
@dataclass
class PortConnection:
    """A connection between two ports in a graph."""

    source_node_id: str
    source_port_name: str
    target_node_id: str
    target_port_name: str
    adapter: TypeAdapter | None = None  # Set if cross-domain conversion needed

    def validate(self, graph: "Graph") -> list[str]:
        """
        Validate this connection.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Get source and target nodes
        source_node = graph.get_node(self.source_node_id)
        target_node = graph.get_node(self.target_node_id)

        if not source_node:
            errors.append(f"Source node {self.source_node_id} not found")
            return errors

        if not target_node:
            errors.append(f"Target node {self.target_node_id} not found")
            return errors

        # Get port definitions
        source_port = source_node.get_output_port(self.source_port_name)
        target_port = target_node.get_input_port(self.target_port_name)

        if not source_port:
            errors.append(f"Output port '{self.source_port_name}' not found on {source_node.type}")

        if not target_port:
            errors.append(f"Input port '{self.target_port_name}' not found on {target_node.type}")

        if errors:
            return errors

        # Check type compatibility
        if source_port.type.is_compatible_with(target_port.type):
            return []  # Compatible

        # Check if adapter exists for cross-domain conversion
        adapter = graph.adapter_registry.get_adapter(source_port.type, target_port.type)
        if adapter:
            self.adapter = adapter
            return []  # Adaptable

        # Incompatible
        errors.append(
            f"Type mismatch: {source_port.type.type_name} → {target_port.type.type_name} "
            f"(no adapter available)"
        )

        return errors
```

---

## 10. Implementation Guidelines

### 10.1 Adding a New Primitive Type

1. **Define the type class** extending `PortType`
2. **Implement validation logic** in `validate()`
3. **Implement coercion logic** in `coerce()`
4. **Provide JSON schema** in `schema()`
5. **Register in type registry**
6. **Add tests** for validation, coercion, edge cases

### 10.2 Adding a New Domain Type

1. **Define Pydantic model** for the data structure
2. **Create PortType wrapper** extending `PortType` with `domain` set
3. **Implement validation** (usually delegates to Pydantic)
4. **Implement coercion** (handle dict → model conversion)
5. **Register in domain type registry**
6. **Document in domain specification**
7. **Add TypeAdapters** for cross-domain conversions

### 10.3 Adding a Type Adapter

1. **Identify source and target types** (must be from different domains)
2. **Create adapter class** extending `TypeAdapter[TSource, TTarget]`
3. **Implement conversion logic** in `convert()`
4. **Implement validation** in `can_convert()`
5. **Register in adapter registry**
6. **Add tests** for conversion success and failure cases

### 10.4 Type System Extension Points

```python
# Plugin interface for registering custom types
class TypeSystemPlugin(ABC):
    """Plugin for extending the type system with custom types."""

    @abstractmethod
    def register_types(self, registry: TypeRegistry) -> None:
        """Register custom PortTypes."""
        ...

    @abstractmethod
    def register_adapters(self, registry: AdapterRegistry) -> None:
        """Register custom TypeAdapters."""
        ...
```

---

## 11. Examples

### 11.1 Simple AI Workflow

```python
# Graph: Prompt Template → LLM Inference → Text Transform

# Node 1: Prompt Template
prompt_node = Node(
    id="n1",
    type="PromptTemplate",
    inputs={
        "template": "Generate a list of {count} {item_type}",
        "variables": {"count": 5, "item_type": "design ideas"}
    },
    outputs={}
)

# Connection: PromptTemplate.output (String) → LLMInference.prompt (String)
connection_1 = PortConnection(
    source_node_id="n1",
    source_port_name="output",
    target_node_id="n2",
    target_port_name="prompt"
)
# Type check: String → String ✅ Compatible

# Node 2: LLM Inference
llm_node = Node(
    id="n2",
    type="LLMInference",
    inputs={"temperature": 0.7},
    outputs={}
)

# Connection: LLMInference.response (LLMResponse) → TextTransform.input (String)
connection_2 = PortConnection(
    source_node_id="n2",
    source_port_name="response",
    target_node_id="n3",
    target_port_name="input"
)
# Type check: LLMResponse → String
#   LLMResponse.content is String, automatic extraction ✅
```

### 11.2 Cross-Domain Workflow

```python
# Graph: LLM Inference → [Adapter] → FreeCAD Model → STL Export

# Node 1: LLM generates design parameters
llm_node = Node(
    id="n1",
    type="LLMInference",
    inputs={
        "prompt": "Generate parameters for a simple box: length, width, height in mm"
    }
)

# Connection: LLMResponse → DesignParameters (cross-domain)
connection_1 = PortConnection(
    source_node_id="n1",
    source_port_name="response",
    target_node_id="n2",
    target_port_name="parameters"
)
# Type check: LLMResponse (AI domain) → DesignParameters (CAD domain)
#   Adapter: LLMResponseToDesignParametersAdapter ✅

# Node 2: FreeCAD generates 3D model
cad_node = Node(
    id="n2",
    type="FreeCADModel",
    inputs={}
)

# Connection: MeshData → STLExport
connection_2 = PortConnection(
    source_node_id="n2",
    source_port_name="mesh",
    target_node_id="n3",
    target_port_name="input"
)
# Type check: MeshData → MeshData ✅ Same domain, same type
```

### 11.3 List Coercion

```python
# Node: Text Split → List[String] → List Aggregator

# Text Split outputs: List[String]
text_split_output_type = ListType(element_type=StringType())

# List Aggregator expects: List[Integer]
aggregator_input_type = ListType(element_type=IntegerType())

# Connection validation:
connection = PortConnection(
    source_node_id="split",
    source_port_name="lines",
    target_node_id="agg",
    target_port_name="items"
)

# Type check: List[String] → List[Integer]
#   Requires each element String → Integer coercion
#   If strings are parseable ("1", "2", "3"), coercion succeeds ✅
#   If strings are not parseable ("a", "b", "c"), validation fails ❌
```

### 11.4 Optional Type Handling

```python
# Node: User Input (optional) → Default Value → Processing

# User Input port: Optional[String]
user_input_type = OptionalType(inner_type=StringType())

# Default Value node: if input is None, use default
default_node = Node(
    id="default",
    type="DefaultValue",
    inputs={
        "value": None,  # User didn't provide input
        "default": "default_text"
    }
)

# Type validation:
is_valid, error = user_input_type.validate(None)  # ✅ None is valid for Optional

# Coercion:
coerced, error = user_input_type.coerce(None)  # ✅ Returns None
```

---

## Appendix A: Type Registry Reference

```python
class TypeRegistry:
    """Central registry for all PortTypes."""

    def __init__(self):
        self._types: dict[str, PortType] = {}
        self._register_builtin_types()

    def _register_builtin_types(self):
        """Register primitive and composite types."""
        # Primitives
        self.register(StringType())
        self.register(IntegerType())
        self.register(FloatType())
        self.register(BooleanType())
        self.register(BytesType())
        self.register(JSONType())

        # Note: Composite types are factories, not registered directly

    def register(self, port_type: PortType) -> None:
        """Register a new type."""
        if port_type.type_name in self._types:
            raise ValueError(f"Type {port_type.type_name} already registered")
        self._types[port_type.type_name] = port_type

    def get(self, type_name: str) -> PortType | None:
        """Retrieve a type by name."""
        return self._types.get(type_name)

    def list_by_domain(self, domain: str) -> list[PortType]:
        """List all types for a specific domain."""
        return [t for t in self._types.values() if t.domain == domain]
```

---

## Appendix B: Validation Error Messages

| Error Code | Message Template | Example |
|------------|-----------------|---------|
| `TYPE_MISMATCH` | `Expected {expected}, got {actual}` | `Expected String, got Integer` |
| `MISSING_REQUIRED` | `Missing required input: {name}` | `Missing required input: prompt` |
| `INVALID_RANGE` | `Value {value} outside range [{min}, {max}]` | `Value 150 outside range [0, 100]` |
| `INVALID_PATTERN` | `String does not match pattern: {pattern}` | `String does not match pattern: ^[a-z]+$` |
| `COERCION_FAILED` | `Cannot coerce {from} to {to}` | `Cannot coerce Boolean to MeshData` |
| `ADAPTER_NOT_FOUND` | `No adapter for {from} → {to}` | `No adapter for LLMResponse → Netlist` |
| `ADAPTER_ERROR` | `Adapter failed: {reason}` | `Adapter failed: LLM output is not valid JSON` |

---

## Appendix C: Performance Considerations

### Validation Overhead

| Type Category | Validation Time | Notes |
|---------------|----------------|-------|
| Primitive | <0.1ms | Pydantic native validation |
| Composite (small) | <0.5ms | List/dict with <100 elements |
| Composite (large) | 1-10ms | List/dict with 1000+ elements |
| Domain (simple) | <1ms | Pydantic model with <10 fields |
| Domain (complex) | 1-5ms | Nested models with validation logic |

### Optimization Strategies

1. **Lazy Validation** — Only validate when crossing node boundaries
2. **Schema Caching** — Cache JSON schemas for type definitions
3. **Adapter Memoization** — Cache adapter lookups for repeated conversions
4. **Batch Validation** — Validate multiple values in single pass for lists

---

**End of Specification**
