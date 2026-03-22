"""Tests for LanceDB PyArrow schemas."""

import pyarrow as pa

from backend.lance.schemas import (
    BUILTIN_SCHEMAS,
    CURRICULUM_SCHEMA,
    DEPARTMENT_RESOURCES_SCHEMA,
    DOCUMENT_ID_FIELDS,
    PROFILES_SCHEMA,
    VECTOR_DIM,
    VECTOR_TYPE,
)


class TestVectorConfig:
    def test_vector_dimension(self):
        assert VECTOR_DIM == 1024

    def test_vector_type_is_fixed_size_list(self):
        assert pa.types.is_fixed_size_list(VECTOR_TYPE)
        assert VECTOR_TYPE.list_size == 1024
        assert VECTOR_TYPE.value_type == pa.float32()


class TestCurriculumSchema:
    def test_has_required_fields(self):
        names = CURRICULUM_SCHEMA.names
        expected = [
            "id",
            "document_key",
            "filename",
            "category",
            "difficulty",
            "chunk_index",
            "content",
            "heading_path",
            "metadata",
            "created_at",
            "vector",
        ]
        assert names == expected

    def test_id_not_nullable(self):
        assert not CURRICULUM_SCHEMA.field("id").nullable

    def test_content_not_nullable(self):
        assert not CURRICULUM_SCHEMA.field("content").nullable

    def test_vector_column_type(self):
        vec_field = CURRICULUM_SCHEMA.field("vector")
        assert vec_field.type == VECTOR_TYPE

    def test_created_at_is_timestamp(self):
        ts_field = CURRICULUM_SCHEMA.field("created_at")
        assert pa.types.is_timestamp(ts_field.type)
        assert ts_field.type.tz == "UTC"

    def test_chunk_index_is_int32(self):
        field = CURRICULUM_SCHEMA.field("chunk_index")
        assert field.type == pa.int32()


class TestProfilesSchema:
    def test_has_required_fields(self):
        names = PROFILES_SCHEMA.names
        expected = [
            "id",
            "user_id",
            "name",
            "title",
            "department",
            "content",
            "metadata",
            "created_at",
            "vector",
        ]
        assert names == expected

    def test_user_id_not_nullable(self):
        assert not PROFILES_SCHEMA.field("user_id").nullable

    def test_content_not_nullable(self):
        assert not PROFILES_SCHEMA.field("content").nullable

    def test_vector_column_type(self):
        vec_field = PROFILES_SCHEMA.field("vector")
        assert vec_field.type == VECTOR_TYPE


class TestDepartmentResourcesSchema:
    def test_has_required_fields(self):
        names = DEPARTMENT_RESOURCES_SCHEMA.names
        expected = [
            "id",
            "document_id",
            "department",
            "section",
            "source_file",
            "content",
            "metadata",
            "created_at",
            "vector",
        ]
        assert names == expected

    def test_id_not_nullable(self):
        assert not DEPARTMENT_RESOURCES_SCHEMA.field("id").nullable

    def test_content_not_nullable(self):
        assert not DEPARTMENT_RESOURCES_SCHEMA.field("content").nullable

    def test_vector_column_type(self):
        vec_field = DEPARTMENT_RESOURCES_SCHEMA.field("vector")
        assert vec_field.type == VECTOR_TYPE


class TestBuiltinMappings:
    def test_builtin_schemas_contains_all_collections(self):
        assert "curriculum" in BUILTIN_SCHEMAS
        assert "profiles" in BUILTIN_SCHEMAS
        assert "department_resources" in BUILTIN_SCHEMAS
        assert len(BUILTIN_SCHEMAS) == 3

    def test_document_id_fields(self):
        assert DOCUMENT_ID_FIELDS["curriculum"] == "document_key"
        assert DOCUMENT_ID_FIELDS["profiles"] == "user_id"
        assert DOCUMENT_ID_FIELDS["department_resources"] == "document_id"
