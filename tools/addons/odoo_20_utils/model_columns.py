# ruff: noqa: C901, D419, PLR1704, RUF012
# pylint: disable=W0622

import inspect
import re
import textwrap
import traceback

from osv import fields, osv

from . import view_converter

LINE_LENGTH = 88
INDENT = " " * 4

# Columns automatically managed by Odoo, they must not be declared again
ODOO_DEFAULT_COLUMNS = {"id", "create_uid", "create_date", "write_uid", "write_date"}

RELATIONAL = ("many2one", "one2many", "many2many")

DATA_PLACEHOLDERS = {
    "boolean": "False",
    "integer": "0",
    "float": "0.0",
    "char": '""',
    "text": '""',
    "html": '""',
}
DEFAULT_PLACEHOLDER = "False"


class Raw(str):
    """Python code that must be written as is."""

def py_str(value):
    text = repr(value)
    if text.startswith("'"):
        if '"' not in value:
            return '"' + text[1:-1] + '"'
        if "'" in value:
            body = text[1:-1].replace("\\'", "'")
            if value.count('"') > value.count("'"):
                return "'" + body.replace("'", "\\'") + "'"
            return '"' + body.replace('"', '\\"') + '"'
    return text


def flat(value):
    if isinstance(value, Raw):
        return str(value)
    if isinstance(value, str):
        return py_str(value)
    if isinstance(value, (list, tuple)):
        items = ", ".join(flat(item) for item in value)
        if isinstance(value, list):
            return f"[{items}]"
        return f"({items},)" if len(value) == 1 else f"({items})"
    if isinstance(value, dict):
        items = ", ".join(f"{flat(k)}: {flat(v)}" for k, v in value.items())
        return "{" + items + "}"
    return repr(value)


def split_string(value, indent):
    inner = indent + 4
    width = LINE_LENGTH - inner - 6
    words = value.split(" ")
    chunks, current = [], ""
    for idx, word in enumerate(words):
        piece = word + (" " if idx < len(words) - 1 else "")
        if current and len(current) + len(piece) > width:
            chunks.append(current)
            current = ""
        current += piece
    chunks.append(current)
    if len(chunks) == 1:
        return py_str(value)
    lines = [" " * inner + py_str(chunk) for chunk in chunks]
    return "(\n" + "\n".join(lines) + "\n" + " " * indent + ")"


def render(value, col, indent):
    text = flat(value)
    if col + len(text) + 1 <= LINE_LENGTH:
        return text
    inner = indent + 4
    pad = " " * inner
    if isinstance(value, (list, tuple)) and value:
        opening, closing = ("[", "]") if isinstance(value, list) else ("(", ")")
        lines = [f"{pad}{render(item, inner, inner)}," for item in value]
        return f"{opening}\n" + "\n".join(lines) + f"\n{' ' * indent}{closing}"
    if isinstance(value, dict) and value:
        lines = []
        for key, item in value.items():
            prefix = f"{pad}{flat(key)}: "
            lines.append(f"{prefix}{render(item, len(prefix), inner)},")
        return "{\n" + "\n".join(lines) + "\n" + " " * indent + "}"
    if isinstance(value, str) and not isinstance(value, Raw):
        return split_string(value, indent)
    return text


def format_field(name, class_name, attrs):
    head = f"{INDENT}{name} = fields.{class_name}("
    one_line = head + ", ".join(f"{key}={flat(val)}" for key, val in attrs) + ")"
    if len(one_line) <= LINE_LENGTH:
        return one_line
    lines = [head]
    for key, val in attrs:
        prefix = f"{INDENT * 2}{key}="
        lines.append(f"{prefix}{render(val, len(prefix), len(INDENT) * 2)},")
    lines.append(f"{INDENT})")
    return "\n".join(lines)


def comment_lines(text):
    width = LINE_LENGTH - len(INDENT) - 2
    return [
        f"{INDENT}# {line}"
        for line in textwrap.wrap(text, width, break_long_words=False)
    ]


def old_code_comment(func):
    name = getattr(func, "__name__", None) or repr(func)
    if name != "<lambda>":
        return f"Old: {name}"
    try:
        line = inspect.getsource(func).split("\n", 1)[0].strip()
    except (OSError, TypeError):
        return "Old: lambda"
    return f"Old: {line}"


def default_label(field_name):
    base = field_name[:-4] if field_name.endswith("_ids") else field_name
    if base.endswith("_id"):
        base = base[:-3]
    return base.replace("_", " ").title()


def callable_name(func):
    return func if isinstance(func, str) else func.__name__


class model_columns(osv.osv_memory):
    _name = "model.columns"
    _rec_name = "model_name"

    @staticmethod
    def string_cleanup(string):
        # Remove newlines
        result: str = string.replace("\n", "")
        # Remove multiples spaces
        result = " ".join(result.split())
        return result

    def get_method_inheritance_chain(self, model_obj, method_name, res):
        """
        Retrieve all method overrides in order of execution for a given method
        and Odoo model.
        """
        # Check if method name is valid for object
        if not hasattr(model_obj, method_name):
            res["value"]["method_inheritance_chain"] = (
                f"No method called '{method_name}' found for this class"
            )
            return
        # Retrieve all override methods
        method_string = ""
        parent_classes = inspect.getmro(model_obj.__class__)
        for parent_class in parent_classes:
            # Break when hitting first base framework class
            if str(parent_class) == "<class 'osv.osv.osv'>":
                break
            # Skip base class used repeatedly for odoo class inheritance resolution
            if str(parent_class.__module__) == "osv.osv":
                continue
            # Check if override version is present in source
            # (otherwise inspect.getsource returns base class method code
            # regardless of whether the class actually overrides the method
            # or not)
            if not re.search(
                rf"^\s*def {re.escape(method_name)}\(", inspect.getsource(parent_class), re.M
            ):
                continue
            method_string += "====== CLASS ======\n"
            method_string += f"{parent_class}\n\n"
            method_string += (
                f"{inspect.getsource(getattr(parent_class, method_name))}\n\n"
            )

        res["value"]["method_inheritance_chain"] = method_string

    @staticmethod
    def new_method_name(registry, kind, old_name, field_name):
        known = registry[kind]
        if old_name in known:
            return known[old_name]
        prefix = f"_{kind}_"
        new_name = old_name if old_name.startswith(prefix) else f"{prefix}{field_name}"
        if new_name in known.values():
            new_name = f"{new_name}_{len(known)}"
        known[old_name] = new_name
        return new_name

    def field_attributes(self, model_obj, field_name, field_data, registry, methods):
        ftype = field_data._type
        class_name = field_data.__class__.__name__
        is_compute = class_name == "function"
        is_related = class_name == "related"
        obj = getattr(field_data, "_obj", None)
        attrs = []

        if ftype == "selection":
            selection = getattr(field_data, "selection", None)
            if callable(selection) or isinstance(selection, str):
                new_name = f"_selection_{field_name}"
                old = (
                    f"Old: {selection}"
                    if isinstance(selection, str)
                    else old_code_comment(selection)
                )
                methods["selection"].append((new_name, field_name, old))
                attrs.append(("selection", new_name))
            elif selection:
                attrs.append(("selection", [tuple(item) for item in selection]))
        elif ftype in RELATIONAL and obj and not is_related:
            attrs.append(("comodel_name", obj))
        if ftype == "one2many" and not is_compute and not is_related:
            attrs.append(("inverse_name", field_data._fields_id))
        if ftype == "many2many" and not is_compute and not is_related:
            attrs.append(("relation", field_data._rel))
            attrs.append(("column1", field_data._id1))
            attrs.append(("column2", field_data._id2))

        label = field_data.string
        if label != "unknown" and (
            is_related or label != default_label(field_name)
        ):
            attrs.append(("string", label))

        if is_related:
            attrs.append(("related", ".".join(str(arg) for arg in field_data._arg)))
        if is_compute:
            old_compute = callable_name(field_data._fnct)
            new_compute = self.new_method_name(
                registry, "compute", old_compute, field_name
            )
            attrs.append(("compute", new_compute))
            entry = methods["compute"].setdefault(
                new_compute, {"old": old_compute, "fields": []}
            )
            entry["fields"].append((field_name, ftype, bool(field_data.store)))
            if field_data._fnct_inv:
                old_inverse = callable_name(field_data._fnct_inv)
                new_inverse = self.new_method_name(
                    registry, "inverse", old_inverse, field_name
                )
                attrs.append(("inverse", new_inverse))
                methods["inverse"][new_inverse] = old_inverse
            if field_data._fnct_search:
                old_search = callable_name(field_data._fnct_search)
                new_search = self.new_method_name(
                    registry, "search", old_search, field_name
                )
                attrs.append(("search", new_search))
                methods["search"][new_search] = old_search
        if (is_related or is_compute) and field_data.store:
            attrs.append(("store", True))

        if ftype == "char" and field_data.size:
            attrs.append(("size", field_data.size))
        if ftype in ("char", "text") and field_data.translate:
            attrs.append(("translate", True))
        if ftype == "float" and field_data.digits:
            digits = field_data.digits
            if isinstance(digits, (list, tuple)):
                attrs.append(("digits", tuple(digits)))
            else:
                attrs.append(("digits", Raw(str(digits))))

        if field_data.required:
            attrs.append(("required", True))
        if field_data.readonly:
            attrs.append(("readonly", True))
        if field_data.select:
            attrs.append(("index", True))

        defaults = model_obj._defaults or {}
        if field_name in defaults:
            default_val = defaults[field_name]
            if callable(default_val):
                new_name = f"_default_{field_name}"
                methods["default"].append(
                    (new_name, field_name, ftype, old_code_comment(default_val))
                )
                attrs.append(("default", Raw(f"lambda self: self.{new_name}()")))
            elif default_val is not None:
                attrs.append(("default", default_val))

        if ftype in RELATIONAL and field_data._domain and not is_related:
            attrs.append(("domain", field_data._domain))
        if ftype == "many2one" and not is_compute and not is_related:
            ondelete = field_data.ondelete
            if ondelete == "set null":
                ondelete = "restrict" if field_data.required else None
            if ondelete:
                attrs.append(("ondelete", ondelete))

        if field_data.help:
            attrs.append(("help", self.string_cleanup(field_data.help)))

        return attrs

    @staticmethod
    def set_view_message(res, message):
        res["value"]["views_xml"] = message

    def get_view(self, cr, uid, view_ref, res, context=None):
        try:
            view_obj = self.pool.get("ir.ui.view")
            data_obj = self.pool.get("ir.model.data")
            ref = (view_ref or "").strip()
            if not ref:
                self.set_view_message(res, "Type in a view id or an xml id and click away")
                return
            if ref.isdigit():
                view_id = int(ref)
            elif "." in ref:
                module, name = ref.split(".", 1)
                data_ids = data_obj.search(
                    cr, uid,
                    [
                        ("model", "=", "ir.ui.view"),
                        ("module", "=", module),
                        ("name", "=", name),
                    ],
                    context=context,
                )
                if not data_ids:
                    self.set_view_message(res, f"No view with xml id '{ref}'.")
                    return
                data = data_obj.read(cr, uid, data_ids[:1], ["res_id"], context=context)
                view_id = data[0]["res_id"]
            else:
                self.set_view_message(
                    res, "Give a view id (number) or an xml id (module.name)."
                )
                return
            if not view_obj.search(cr, uid, [("id", "=", view_id)], context=context):
                self.set_view_message(res, f"View {view_id} not found.")
                return

            view = view_obj.read(
                cr, uid, [view_id],
                ["name", "model", "type", "inherit_id", "arch", "priority"],
                context=context,
            )[0]
            parent = view.get("inherit_id")
            view["inherit_id"] = (
                parent[0] if isinstance(parent, (list, tuple)) else parent
            ) or None
            wanted = [view_id] + ([view["inherit_id"]] if view["inherit_id"] else [])
            data_ids = data_obj.search(
                cr, uid,
                [("model", "=", "ir.ui.view"), ("res_id", "in", wanted)],
                context=context,
            )
            xml_ids = {}
            for data in data_obj.read(
                cr, uid, data_ids, ["module", "name", "res_id"], context=context
            ):
                xml_ids.setdefault(data["res_id"], f"{data['module']}.{data['name']}")
            _summary, xml = view_converter.convert_views(
                view.get("model") or "", [view], xml_ids
            )
            res["value"]["views_xml"] = xml
        except Exception:
            self.set_view_message(
                res, f"Error while reading the view:\n{traceback.format_exc()}"
            )

    def onchange_view_ref(self, cr, uid, ids, view_ref=None, context=None):
        res = {"value": {}}
        self.get_view(cr, uid, view_ref, res, context=context)
        return res

    @staticmethod
    def build_placeholders(methods):
        blocks = []
        uses_api = False

        def add(title, block_lines, first):
            lines = [f"{INDENT}# {title}"] if first else []
            blocks.append("\n".join(lines + block_lines))

        for idx, (name, field_name, ftype, old) in enumerate(methods["default"]):
            placeholder = DATA_PLACEHOLDERS.get(ftype, DEFAULT_PLACEHOLDER)
            add(
                "Default methods",
                [
                    *comment_lines(old),
                    f"{INDENT}def {name}(self):",
                    f"{INDENT * 2}return {placeholder}",
                ],
                idx == 0,
            )
        for idx, (name, field_name, old) in enumerate(methods["selection"]):
            add(
                "Selection methods",
                [
                    *comment_lines(old),
                    f"{INDENT}def {name}(self):",
                    f'{INDENT * 2}return [("option_a", "Option A"), '
                    '("option_b", "Option B")]',
                ],
                idx == 0,
            )
        for idx, (name, entry) in enumerate(methods["compute"].items()):
            stored = any(field[2] for field in entry["fields"])
            block = []
            if entry["old"] != name:
                block += comment_lines(f"Old: {entry['old']}")
            if stored:
                block += comment_lines("TODO: list the fields this method depends on")
                block.append(f"{INDENT}@api.depends()")
                uses_api = True
            block.append(f"{INDENT}def {name}(self):")
            block.append(f"{INDENT * 2}for record in self:")
            for field_name, ftype, _stored in entry["fields"]:
                placeholder = DATA_PLACEHOLDERS.get(ftype, DEFAULT_PLACEHOLDER)
                block.append(f"{INDENT * 3}record.{field_name} = {placeholder}")
            add("Compute methods", block, idx == 0)
        for idx, (name, old) in enumerate(methods["search"].items()):
            add(
                "Search methods",
                [
                    *(comment_lines(f"Old: {old}") if old != name else []),
                    f"{INDENT}def {name}(self, operator, value):",
                    f'{INDENT * 2}return [("id", operator, value)]',
                ],
                idx == 0,
            )
        for idx, (name, old) in enumerate(methods["inverse"].items()):
            add(
                "Inverse methods",
                [
                    *(comment_lines(f"Old: {old}") if old != name else []),
                    f"{INDENT}def {name}(self):",
                    f"{INDENT * 2}pass",
                ],
                idx == 0,
            )
        if not blocks:
            return "", uses_api
        return "\n\n".join(blocks) + "\n", uses_api

    def onchange_model_name(
        self, cr, uid, ids, model_name=None, method_name=None, context=None
    ):
        """ """
        if context is None:
            context = {}
        # Prepare default results
        res = {"value": {}}

        # Check model_name
        if not model_name:
            res["value"]["fields"] = "Type in model name and click away"
            res["value"]["placeholder_methods"] = "Type in model name and click away"
            return res
        # Search for model name
        model_obj = self.pool.get(model_name)
        if not model_obj:
            res["value"]["fields"] = "Model not found."
            res["value"]["placeholder_methods"] = "Model not found."
            res["value"]["method_inheritance_chain"] = "Model not found."
            return res

        # == CRUD METHODS ==
        if method_name:
            self.get_method_inheritance_chain(model_obj, method_name, res)

        # == COLUMNS TO FIELDS ==
        registry = {"compute": {}, "search": {}, "inverse": {}}
        methods = {
            "default": [],
            "selection": [],
            "compute": {},
            "search": {},
            "inverse": {},
        }
        field_lines = []
        for field_name, field_data in model_obj._columns.items():
            if field_name in ODOO_DEFAULT_COLUMNS:
                continue
            attrs = self.field_attributes(
                model_obj, field_name, field_data, registry, methods
            )
            field_lines.append(
                format_field(field_name, field_data._type.capitalize(), attrs)
            )

        # == PLACEHOLDER METHODS ==
        placeholders, uses_api = self.build_placeholders(methods)

        # == MODEL HEADER ==
        header = []
        for attr in ("_name", "_description", "_order"):
            if getattr(model_obj, attr, None):
                header.append(f"{INDENT}{attr} = {py_str(getattr(model_obj, attr))}")
        table = getattr(model_obj, "_table", None)
        if table and table != model_obj._name.replace(".", "_"):
            header.append(f"{INDENT}_table = {py_str(table)}")
        class_name = "".join(
            part.capitalize() for part in re.split(r"[._]", model_obj._name)
        )
        imports = "api, fields, models" if uses_api else "fields, models"

        lines = [
            f"from odoo import {imports}",
            "",
            "",
            f"class {class_name}(models.Model):",
            *header,
        ]
        if field_lines:
            lines += ["", *field_lines]
        res["value"]["fields"] = "\n".join(lines) + "\n"
        res["value"]["placeholder_methods"] = placeholders

        # Return results
        return res

    _columns = {
        "fields": fields.text(
            string="Fields",
            readonly=True,
        ),
        "placeholder_methods": fields.text(
            string="Placeholder methods",
            readonly=True,
        ),
        "model_name": fields.char(
            size=128,
            string="Model name",
        ),
        "method_name": fields.char(
            size=128,
            string="Method name",
        ),
        "method_inheritance_chain": fields.text(
            string="Method Inheritance",
            readonly=True,
        ),
        "view_ref": fields.char(
            size=128,
            string="View id or xml id",
        ),
        "views_xml": fields.text(
            string="Views (Odoo 20 syntax)",
            readonly=True,
        ),
    }


model_columns()
