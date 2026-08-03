#!/usr/bin/env python3
"""Generate Pydantic domain models, events, SQLAlchemy models and FastAPI routers from spec/domain.yaml."""

from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "spec" / "domain.yaml"
SRC = REPO_ROOT / "src"

PYDANTIC_TYPE_MAP = {
    "uuid": "UUID",
    "str": "str",
    "text": "str",
    "email": "EmailStr",
    "url": "HttpUrl",
    "url_str": "str",
    "int": "int",
    "float": "float",
    "bool": "bool",
    "datetime": "datetime",
    "date": "date",
    "json": "dict[str, Any]",
    "json_list": "Any",
    "list_str": "list[str]",
}

SQLALCHEMY_TYPE_MAP = {
    "uuid": "UUID(as_uuid=True)",
    "str": "String(255)",
    "text": "Text",
    "email": "String(255)",
    "url": "String(2048)",
    "url_str": "String(2048)",
    "int": "Integer",
    "float": "Float",
    "bool": "Boolean",
    "datetime": "DateTime(timezone=True)",
    "date": "Date",
    "json": "JSON",
    "json_list": "JSON",
    "list_str": "JSON",
}


def to_pascal(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_"))


def py_type(spec_type: str, enums: dict[str, list[str]], nullable: bool = False) -> str:
    if spec_type.startswith("enum:"):
        base = spec_type.split(":", 1)[1]
    elif spec_type.startswith("fk:"):
        base = "UUID"
    else:
        base = PYDANTIC_TYPE_MAP[spec_type]
    if nullable and base not in ("Any",):
        return f"{base} | None"
    return base


def sa_type(spec_type: str) -> str:
    if spec_type.startswith("enum:"):
        return "String(255)"
    if spec_type.startswith("fk:"):
        return "UUID(as_uuid=True)"
    return SQLALCHEMY_TYPE_MAP[spec_type]


def enum_member_name(value: str) -> str:
    key = re.sub(r"[^0-9a-zA-Z_]+", "_", value.upper()).lstrip("0123456789_")
    return key or "VALUE"


def py_default(default: Any) -> str:
    if isinstance(default, str) and default.startswith("'") and default.endswith("'"):
        return repr(default[1:-1])
    return repr(default)


def pydantic_default(
    field: dict[str, Any], enums: dict[str, list[str]], for_create: bool = False
) -> str:
    if field.get("primary"):
        return "Field(default_factory=uuid4)"
    if field.get("auto"):
        return "Field(default_factory=datetime.utcnow)"
    if for_create and field["name"] == "workspace_id":
        return "None"
    if for_create and field.get("nullable") and field.get("default") is None:
        return "None"
    default = field.get("default")
    py = py_type(field["type"], {})
    if default is None or default == [] or default == {}:
        if py == "dict[str, Any]":
            return "Field(default_factory=dict)"
        if py in ("list[str]", "Any"):
            return (
                "Field(default_factory=list)"
                if "list" in field.get("type", "")
                else "Field(default_factory=dict)"
            )
        return ""
    if field["type"].startswith("enum:"):
        enum_name = py_type(field["type"], enums)
        raw = (
            default[1:-1]
            if isinstance(default, str) and default.startswith("'") and default.endswith("'")
            else default
        )
        return f"{enum_name}.{enum_member_name(raw)}"
    return py_default(default)


def response_field(field: dict[str, Any], enums: dict[str, list[str]]) -> str:
    py = py_type(field["type"], enums, nullable=bool(field.get("nullable")))
    default = pydantic_default(field, enums)
    if default:
        return f"    {field['name']}: {py} = {default}"
    return f"    {field['name']}: {py}"


def create_field(field: dict[str, Any], enums: dict[str, list[str]]) -> str:
    if field.get("primary") or field.get("auto"):
        return ""
    py = py_type(field["type"], enums, nullable=bool(field.get("nullable")))
    if field["name"] == "workspace_id":
        return "    workspace_id: UUID | None = None"
    default = pydantic_default(field, enums, for_create=True)
    if default:
        return f"    {field['name']}: {py} = {default}"
    return f"    {field['name']}: {py}"


def update_field(field: dict[str, Any], enums: dict[str, list[str]]) -> str:
    if field.get("primary") or field.get("auto"):
        return ""
    nullable = bool(field.get("nullable"))
    py = py_type(field["type"], enums, nullable=nullable)
    if field["name"] == "workspace_id":
        return "    workspace_id: UUID | None = None"
    if nullable:
        return f"    {field['name']}: {py} = None"
    return f"    {field['name']}: {py} | None = None"


def sqlalchemy_field(field: dict[str, Any]) -> str:
    sql = sa_type(field["type"])
    kwargs: list[str] = []
    name = field["name"]
    nullable = bool(field.get("nullable"))
    if field.get("primary"):
        kwargs.append("primary_key=True")
        kwargs.append("default=uuid.uuid4")
    if field["type"].startswith("fk:"):
        target = field["type"].split(":", 1)[1]
        kwargs.append(f"ForeignKey('{target}.id')")
    if field.get("index"):
        kwargs.append("index=True")
    if nullable:
        kwargs.append("nullable=True")
    if field.get("auto"):
        if name == "created_at":
            kwargs.append("server_default=func.now()")
        elif name == "updated_at":
            kwargs.append("server_default=func.now(), onupdate=func.now()")
        else:
            kwargs.append("server_default=func.now()")
    default = field.get("default")
    if (
        not field.get("primary")
        and not field.get("auto")
        and default is not None
        and sql in ("String(255)", "String(2048)", "Boolean", "Integer", "Float")
    ):
        kwargs.append(f"default={py_default(default)}")
    args = sql + ((", " + ", ".join(kwargs)) if kwargs else "")
    return f"    {name}: Mapped[{mapped_py_type(field['type'], nullable)}] = mapped_column({args})"


def mapped_py_type(spec_type: str, nullable: bool = False) -> str:
    if spec_type.startswith("enum:"):
        base = "str"
    elif spec_type == "uuid" or spec_type.startswith("fk:"):
        base = "uuid.UUID"
    else:
        base = py_type(spec_type, {})
    if base in ("HttpUrl", "EmailStr"):
        base = "str"
    if nullable and base not in ("Any",):
        return f"{base} | None"
    return base


def generate_enums(enums: dict[str, list[str]]) -> str:
    lines = ["from enum import Enum", "", ""]
    for name, values in enums.items():
        lines.append(f"class {name}(str, Enum):")
        for value in values:
            lines.append(f'    {enum_member_name(value)} = "{value}"')
        lines.extend(["", ""])
    return "\n".join(lines).rstrip() + "\n"


def generate_base_event(base_fields: list[dict[str, Any]], enums: dict[str, list[str]]) -> str:
    fields = [response_field(f, enums) for f in base_fields]
    return (
        textwrap.dedent(
            """\
        from datetime import datetime
        from uuid import UUID, uuid4

        from pydantic import BaseModel, ConfigDict, Field


        class BaseEvent(BaseModel):
            model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)

        """
        )
        + "\n".join(fields)
        + '\n\n__all__ = ["BaseEvent"]\n'
    )


def generate_event(
    class_name: str,
    spec: dict[str, Any],
    base_fields: list[dict[str, Any]],
    enums: dict[str, list[str]],
) -> str:
    all_fields = base_fields + spec.get("fields", [])
    event_fields = [response_field(f, enums) for f in spec.get("fields", [])]
    version = spec.get("schema_version", "1.0.0")
    used_types = {f["type"] for f in all_fields}
    needs_date = "date" in used_types
    needs_uuid = any(t == "uuid" or t.startswith("fk:") for t in used_types)
    needs_any = any(t in ("json", "json_list") for t in used_types)
    needs_http_url = "url" in used_types
    needs_email = "email" in used_types
    needs_field = any("Field(" in f for f in event_fields)
    imports = ["from datetime import datetime"]
    if needs_date:
        imports[0] = "from datetime import date, datetime"
    if needs_uuid:
        imports.append("from uuid import UUID, uuid4")
    if needs_any:
        imports.append("from typing import Any")
    extra_pydantic: list[str] = []
    if needs_http_url:
        extra_pydantic.append("HttpUrl")
    if needs_email:
        extra_pydantic.append("EmailStr")
    pydantic_imports = extra_pydantic[:]
    if needs_field:
        pydantic_imports.insert(0, "Field")
    if pydantic_imports:
        imports.append(f"from pydantic import {', '.join(pydantic_imports)}")
    used_enums = {t.split(":", 1)[1] for t in used_types if t.startswith("enum:")}
    if used_enums:
        imports.append(f"from config.enums import {', '.join(sorted(used_enums))}")
    imports.extend(["", "from domain.events.base import BaseEvent", ""])
    lines = imports + [
        f"class {class_name}(BaseEvent):",
        f'    """{spec.get("description", "")}"""',
        f'    schema_version: str = "{version}"',
    ]
    lines.extend(event_fields)
    lines.extend(["", f'__all__ = ["{class_name}"]'])
    return "\n".join(lines) + "\n"


def generate_pydantic_models(
    class_name: str, spec: dict[str, Any], enums: dict[str, list[str]]
) -> str:
    response_fields = [response_field(f, enums) for f in spec["fields"]]
    create_fields = [line for line in (create_field(f, enums) for f in spec["fields"]) if line]
    update_fields = [line for line in (update_field(f, enums) for f in spec["fields"]) if line]
    used_enums = {
        py_type(f["type"], enums) for f in spec["fields"] if f["type"].startswith("enum:")
    }
    used_types = {f["type"] for f in spec["fields"]}
    needs_date = "date" in used_types
    needs_any = any(t in ("json", "json_list") for t in used_types)
    needs_http_url = "url" in used_types
    needs_email = "email" in used_types
    extra_pydantic: list[str] = []
    if needs_http_url:
        extra_pydantic.append("HttpUrl")
    if needs_email:
        extra_pydantic.append("EmailStr")
    pydantic_import = "from pydantic import BaseModel, ConfigDict, Field"
    if extra_pydantic:
        pydantic_import += f", {', '.join(extra_pydantic)}"
    imports = ["from datetime import datetime"]
    if needs_date:
        imports[0] = "from datetime import date, datetime"
    if needs_any:
        imports.append("from typing import Any")
    imports.extend(["from uuid import UUID, uuid4", "", pydantic_import])
    if used_enums:
        imports.append(f"from config.enums import {', '.join(sorted(used_enums))}")
    lines = imports + [
        "",
        f"class {class_name}(BaseModel):",
        f'    """{spec.get("description", class_name)}."""',
        '    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)',
    ]
    lines.extend(response_fields)
    lines.extend(
        [
            "",
            f"class {class_name}Create(BaseModel):",
            '    """Create request."""',
            '    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)',
        ]
    )
    lines.extend(create_fields)
    lines.extend(
        [
            "",
            f"class {class_name}Update(BaseModel):",
            '    """Partial update request."""',
            '    model_config = ConfigDict(extra="forbid", populate_by_name=True, from_attributes=True)',
        ]
    )
    lines.extend(update_fields)
    lines.extend(["", f'__all__ = ["{class_name}", "{class_name}Create", "{class_name}Update"]'])
    return "\n".join(lines) + "\n"


def generate_sqlalchemy_model(name: str, class_name: str, spec: dict[str, Any]) -> str:
    fields = [sqlalchemy_field(f) for f in spec["fields"]]
    has_json = any(f["type"] in ("json", "json_list") for f in spec["fields"])
    used_types = {f["type"] for f in spec["fields"]}
    needed: set[str] = set()
    for t in used_types:
        if t in ("str", "email", "url", "url_str") or t.startswith("enum:"):
            needed.add("String")
        elif t == "text":
            needed.add("Text")
        elif t == "int":
            needed.add("Integer")
        elif t == "float":
            needed.add("Float")
        elif t == "bool":
            needed.add("Boolean")
        elif t == "date":
            needed.add("Date")
        elif t == "datetime":
            needed.add("DateTime")
        elif t in ("json", "json_list", "list_str"):
            needed.add("JSON")
    has_fk = any(t.startswith("fk:") for t in used_types)
    has_auto = any(f.get("auto") for f in spec["fields"])
    if has_auto:
        needed.add("DateTime")
        needed.add("func")
    if has_fk:
        needed.add("ForeignKey")
    needs_date = "date" in used_types
    needs_datetime = any(t in ("datetime",) for t in used_types) or has_auto
    lines = ["import uuid"]
    if needs_date and needs_datetime:
        lines.append("from datetime import date, datetime")
    elif needs_date:
        lines.append("from datetime import date")
    elif needs_datetime:
        lines.append("from datetime import datetime")
    if has_json:
        lines.append("from typing import Any")
    sqlalchemy_imports = [c for c in sorted(needed) if c]
    lines.extend(
        [
            f"from sqlalchemy import {', '.join(sqlalchemy_imports)}",
            "from sqlalchemy.dialects.postgresql import UUID",
            "from sqlalchemy.orm import Mapped, mapped_column",
            "",
            "from db.base import Base",
            "",
            "",
            f"class {class_name}(Base):",
            f'    """{spec.get("description", class_name)}."""',
            f'    __tablename__ = "{name}"',
            "",
        ]
    )
    lines.extend(fields)
    lines.extend(["", f'__all__ = ["{class_name}"]'])
    return "\n".join(lines) + "\n"


def generate_router(name: str, model_class: str, db_class: str, spec: dict[str, Any]) -> str | None:
    route = spec.get("route")
    if route is None or route == "none":
        return None
    is_workspace = name == "workspace"
    workspace_references: dict[str, str] = spec.get("workspace_references", {})
    pk_name = "workspace_id" if is_workspace else f"{name}_id"
    create_extra = "" if is_workspace else ", workspace_id=auth_workspace_id"
    create_values = (
        "data.model_dump(exclude_unset=True)"
        if is_workspace
        else 'data.model_dump(exclude={"workspace_id"})'
    )
    update_values = (
        "data.model_dump(exclude_unset=True)"
        if is_workspace
        else 'data.model_dump(exclude_unset=True, exclude={"workspace_id"})'
    )
    list_filter = "" if is_workspace else f".where(DB{db_class}.workspace_id == auth_workspace_id)"
    get_filter = f"DB{db_class}.id == {pk_name}"
    if is_workspace:
        get_filter += f", DB{db_class}.id == auth_workspace_id"
    else:
        get_filter += f", DB{db_class}.workspace_id == auth_workspace_id"
    db_imports = [f"from db.models import {db_class} as DB{db_class}"]
    reference_checks: list[str] = []
    for field, entity in workspace_references.items():
        reference_class = to_pascal(entity)
        db_imports.append(f"from db.models import {reference_class} as DB{reference_class}")
        reference_checks.append(
            textwrap.dedent(
                f"""\
                value = values.get("{field}")
                if value is not None:
                    exists = await session.scalar(
                        select(DB{reference_class}.id).where(
                            DB{reference_class}.id == value,
                            DB{reference_class}.workspace_id == auth_workspace_id,
                        )
                    )
                    if not exists:
                        raise HTTPException(status_code=404, detail="{reference_class} not found")
                """
            ).rstrip()
        )
    reference_helper = ""
    reference_validation = ""
    if reference_checks:
        checks = textwrap.indent("\n".join(reference_checks), "    ")
        reference_helper = textwrap.indent(
            (
                "async def _validate_workspace_references(\n"
                "    values: dict[str, object],\n"
                "    auth_workspace_id: UUID,\n"
                "    session: AsyncSession,\n"
                ") -> None:\n"
                f"{checks}\n"
            ),
            "        ",
        )
        reference_validation = (
            "            await _validate_workspace_references(values, auth_workspace_id, session)\n"
        )
    db_import_block = textwrap.indent("\n".join(db_imports), "        ")
    return textwrap.dedent(
        f'''\
        from typing import Annotated
        from uuid import UUID

        from fastapi import APIRouter, Depends, HTTPException, Query
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from api.deps import require_workspace
{db_import_block}
        from db.session import get_session
        from domain.models import {model_class}, {model_class}Create, {model_class}Update

        router = APIRouter(prefix="{route}", tags=["{name}"])
{reference_helper}


        @router.get("/", response_model=list[{model_class}])
        async def list_{name}(
            auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
            session: Annotated[AsyncSession, Depends(get_session)],
            skip: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
        ) -> list[{model_class}]:
            result = await session.scalars(select(DB{db_class}){list_filter}.offset(skip).limit(limit))
            return [{model_class}.model_validate(r) for r in result.all()]


        @router.post("/", response_model={model_class}, status_code=201)
        async def create_{name}(
            data: {model_class}Create,
            auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> {model_class}:
            values = {create_values}
{reference_validation}            record = DB{db_class}(**values{create_extra})
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return {model_class}.model_validate(record)


        @router.get("/{{{pk_name}}}", response_model={model_class})
        async def get_{name}(
            {pk_name}: UUID,
            auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> {model_class}:
            record = await session.scalar(select(DB{db_class}).where({get_filter}))
            if not record:
                raise HTTPException(status_code=404, detail="Not found")
            return {model_class}.model_validate(record)


        @router.patch("/{{{pk_name}}}", response_model={model_class})
        async def update_{name}(
            {pk_name}: UUID,
            data: {model_class}Update,
            auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> {model_class}:
            record = await session.scalar(select(DB{db_class}).where({get_filter}))
            if not record:
                raise HTTPException(status_code=404, detail="Not found")
            values = {update_values}
{reference_validation}            for key, value in values.items():
                setattr(record, key, value)
            await session.commit()
            await session.refresh(record)
            return {model_class}.model_validate(record)


        @router.delete("/{{{pk_name}}}", status_code=204)
        async def delete_{name}(
            {pk_name}: UUID,
            auth_workspace_id: Annotated[UUID, Depends(require_workspace)],
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> None:
            record = await session.scalar(select(DB{db_class}).where({get_filter}))
            if not record:
                raise HTTPException(status_code=404, detail="Not found")
            await session.delete(record)
            await session.commit()
        '''
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", default=str(SPEC_PATH))
    args = parser.parse_args()

    with open(args.spec) as fh:
        data = yaml.safe_load(fh)

    enums = data.get("enums", {})
    base_event_fields = data.get("base_event_fields", [])
    events = data.get("events", {})
    entities = data.get("entities", {})

    (SRC / "config" / "enums.py").write_text(generate_enums(enums))
    (SRC / "domain" / "events" / "base.py").write_text(
        generate_base_event(base_event_fields, enums)
    )

    def safe_class_name(name: str) -> str:
        candidate = to_pascal(name)
        return candidate if candidate not in enums else f"{candidate}Event"

    events_init = []
    for name, spec in events.items():
        event_class = safe_class_name(name)
        (SRC / "domain" / "events" / f"{name}.py").write_text(
            generate_event(event_class, spec, base_event_fields, enums)
        )
        events_init.append(f"from domain.events.{name} import {event_class}")
    event_names = [line.split()[-1] for line in events_init]
    (SRC / "domain" / "events" / "__init__.py").write_text(
        "\n".join(events_init)
        + "\n\n__all__ = ["
        + ", ".join(f'"{n}"' for n in event_names)
        + "]\n"
    )

    domain_models_init = []
    db_models_init = []
    router_imports = []
    for name, spec in entities.items():
        db_class = to_pascal(name)
        model_class = db_class if db_class not in enums else f"{db_class}Record"
        (SRC / "domain" / "models" / f"{name}.py").write_text(
            generate_pydantic_models(model_class, spec, enums)
        )
        domain_models_init.append(
            f"from domain.models.{name} import {model_class}, {model_class}Create, {model_class}Update"
        )
        (SRC / "db" / "models" / f"{name}.py").write_text(
            generate_sqlalchemy_model(name, db_class, spec)
        )
        db_models_init.append(f"from db.models.{name} import {db_class}")
        router = generate_router(name, model_class, db_class, spec)
        if router:
            (SRC / "api" / "routers" / f"{name}.py").write_text(router)
            router_imports.append(f"from api.routers.{name} import router as {name}_router")

    domain_model_names = []
    for line in domain_models_init:
        domain_model_names.extend([n.strip() for n in line.split("import", 1)[1].split(",")])
    (SRC / "domain" / "models" / "__init__.py").write_text(
        "\n".join(domain_models_init)
        + "\n\n__all__ = ["
        + ", ".join(f'"{n}"' for n in domain_model_names)
        + "]\n"
    )
    db_model_names = [line.split()[-1] for line in db_models_init]
    (SRC / "db" / "models" / "__init__.py").write_text(
        "\n".join(db_models_init)
        + "\n\n__all__ = ["
        + ", ".join(f'"{n}"' for n in db_model_names)
        + "]\n"
    )
    router_imports.append("from api.routers.source_engine import router as source_engine_router")
    router_names = [imp.split()[-1] for imp in router_imports]
    router_init = (
        "\n".join(router_imports)
        + "\n\n__all__ = ["
        + ", ".join(f'"{n}"' for n in router_names)
        + "]\n"
    )
    (SRC / "api" / "routers" / "__init__.py").write_text(router_init)

    app_body = textwrap.dedent(
        """\
        from collections.abc import AsyncGenerator
        from contextlib import asynccontextmanager

        from fastapi import FastAPI

        from api.routers import (
        """
    )
    if router_imports:
        app_body += ",\n".join(f"    {name.split()[-1]}" for name in router_imports) + "\n)\n"
    else:
        app_body += ")\n"
    app_body += textwrap.dedent(
        """\
        from config.settings import Settings


        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            settings = Settings()
            app.state.settings = settings
            yield


        def create_app() -> FastAPI:
            app = FastAPI(
                title="VA Lead Intelligence API",
                version="1.0.0",
                lifespan=lifespan,
            )
        """
    )
    for imp in router_imports:
        router_name = imp.split()[-1]
        app_body += f"    app.include_router({router_name})\n"
    app_body += "    return app\n\n\napp = create_app()\n"
    (SRC / "api" / "app.py").write_text(app_body)

    print(f"Generated {len(entities)} entities and {len(events)} events.")


if __name__ == "__main__":
    main()
