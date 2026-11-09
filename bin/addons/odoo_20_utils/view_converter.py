# ruff: noqa
# pylint: disable=all

import ast
import re
import traceback
from xml.sax.saxutils import escape

from lxml import etree

INDENT = "    "
LINE_LENGTH = 88
DEFAULT_PRIORITY = 16

MODIFIERS = ("invisible", "readonly", "required", "column_invisible")
REMOVED_ATTRS = ("select", "expand")
CUSTOM_ATTR_RE = re.compile(
    r"^(hide_\w+_button|noteditable|ignore_access_error|depends|password|"
    r"password_with_eye)$"
)
LEGACY_ICON_PREFIXES = ("terp-", "gtk-", "STOCK_")
OPERATORS = {
    "=": "==",
    "!=": "!=",
    "<": "<",
    ">": ">",
    "<=": "<=",
    ">=": ">=",
    "in": "in",
    "not in": "not in",
}
COLORS = {
    "red": "decoration-danger",
    "blue": "decoration-info",
    "green": "decoration-success",
    "orange": "decoration-warning",
    "grey": "decoration-muted",
    "gray": "decoration-muted",
}
NAME_RE = re.compile(r"^\w+$")


def literal(value):
    if isinstance(value, list):
        value = tuple(value)
    return repr(value)


def describe(element):
    name = element.get("name")
    if name:
        return f"{element.tag} '{name}'"
    return f"<{element.tag}>"


class ArchConverter:
    def __init__(self):
        self.warnings = []
        self.removed = {}
        self.has_state_field = False

    def warn(self, message):
        message = " ".join(str(message).split())
        if message not in self.warnings:
            self.warnings.append(message)

    @staticmethod
    def _value(node, source):
        try:
            return True, ast.literal_eval(node)
        except (ValueError, TypeError, SyntaxError):
            return False, ast.get_source_segment(source, node)

    def _term(self, node, source):
        if not isinstance(node, (ast.Tuple, ast.List)) or len(node.elts) != 3:
            raise ValueError(f"term {ast.get_source_segment(source, node)} not supported")
        left_ok, left = self._value(node.elts[0], source)
        op_ok, op = self._value(node.elts[1], source)
        right_ok, right = self._value(node.elts[2], source)
        if not (left_ok and op_ok and isinstance(op, str)):
            raise ValueError(f"term {ast.get_source_segment(source, node)} not supported")
        op = op.lower()
        if isinstance(left, int) and not isinstance(left, bool) and op == "=" and right_ok:
            return ("True" if left == right else "False", "name")
        if op not in OPERATORS:
            raise ValueError(
                f"operator '{op}' on '{left}' has no equivalent in a view expression"
            )
        if not isinstance(left, str):
            raise ValueError(f"unexpected left operand {left!r}")
        if "." in left and not left.startswith("parent."):
            self.warn(f"Related path '{left}' in a view expression: check it works")
        if right_ok and op in ("=", "!=") and (right is True or right is False or right is None):
            wanted_truthy = (op == "=") if right is True else (op == "!=")
            return (left, "name") if wanted_truthy else (f"not {left}", "not")
        if right_ok:
            rhs = literal(right)
        else:
            rhs = right
            self.warn(f"Non literal value '{right}' used for '{left}': check it")
        return (f"{left} {OPERATORS[op]} {rhs}", "cmp")

    @staticmethod
    def _wrap(item, parent):
        text, kind = item
        if parent == "and" and kind == "or":
            return f"({text})"
        if parent == "or" and kind == "and":
            return f"({text})"
        if parent == "not" and not NAME_RE.match(text):
            return f"({text})"
        return text

    def domain_to_expr(self, node, source):
        items = []
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and elt.value in ("|", "&", "!"):
                items.append(elt.value)
            else:
                items.append(self._term(elt, source))
        pos = [0]

        def parse():
            if pos[0] >= len(items):
                raise ValueError("malformed domain")
            item = items[pos[0]]
            pos[0] += 1
            if isinstance(item, str):
                if item == "!":
                    inner = parse()
                    return (f"not {self._wrap(inner, 'not')}", "not")
                kind = "or" if item == "|" else "and"
                left, right = parse(), parse()
                return (
                    f"{self._wrap(left, kind)} {kind} {self._wrap(right, kind)}",
                    kind,
                )
            return item

        parts = []
        while pos[0] < len(items):
            parts.append(parse())
        if not parts:
            self.warn("Empty domain in attrs, replaced by True")
            return "True"
        if len(parts) == 1:
            return parts[0][0]
        return " and ".join(self._wrap(part, "and") for part in parts)

    def convert_attrs(self, raw, where):
        source = (raw or "").strip()
        if not source:
            self.warn(f"Empty attrs on {where}: check which modifiers it cleared")
            return {}
        try:
            tree = ast.parse(source, mode="eval").body
        except SyntaxError:
            self.warn(f"attrs left as is on {where}: not parsed ({source})")
            return None
        if not isinstance(tree, ast.Dict):
            self.warn(f"attrs left as is on {where}: not a dict ({source})")
            return None
        result = {}
        for key_node, value_node in zip(tree.keys, tree.values):
            if key_node is None:
                continue
            ok, key = self._value(key_node, source)
            if not ok or key not in MODIFIERS:
                self.warn(f"attrs left as is on {where}: key {key!r} not supported")
                return None
            if isinstance(value_node, (ast.List, ast.Tuple)):
                try:
                    result[key] = self.domain_to_expr(value_node, source)
                except ValueError as exc:
                    self.warn(f"attrs left as is on {where}: {exc}")
                    return None
            else:
                ok, val = self._value(value_node, source)
                if ok and val is True:
                    result[key] = "1"
                elif ok and not val:
                    continue
                else:
                    result[key] = str(val)
                    self.warn(f"attrs '{key}' on {where} is not a domain: check it")
        return result

    def states_expr(self, states):
        values = [s.strip() for s in states.split(",") if s.strip()]
        if not self.has_state_field:
            self.warn("states converted using the field 'state': check it exists")
        if len(values) == 1:
            return f"state != {values[0]!r}"
        return f"state not in {tuple(values)!r}"

    def colors_to_decorations(self, value):
        result = {}
        for part in value.split(";"):
            part = part.strip()
            if not part:
                continue
            color, _sep, cond = part.partition(":")
            if color.strip().lower() == "black":
                self.warn(
                    "colors 'black:...' (default text color) ignored: check it does "
                    "not override another color"
                )
                continue
            decoration = COLORS.get(color.strip().lower())
            if not decoration or not cond.strip():
                self.warn(f"colors entry not converted: '{part}'")
                continue
            cond = cond.strip()
            result[decoration] = (
                f"{result[decoration]} or {cond}" if decoration in result else cond
            )
        return result

    @staticmethod
    def convert_xpath(expr):
        return re.sub(r"(?<=/)tree(?![\w-])", "list", expr)

    def remove_attr(self, el, attr, where):
        del el.attrib[attr]
        self.removed.setdefault(attr, []).append(where)

    def flush_removed(self):
        for attr, places in self.removed.items():
            self.warn(
                f"'{attr}' does not exist anymore in Odoo 20: removed from "
                f"{len(places)} element(s): {', '.join(places)}"
            )
        self.removed = {}

    def convert_node(self, el):
        where = describe(el)
        if el.tag == "tree":
            el.tag = "list"
        if el.tag == "form" and "version" in el.attrib:
            del el.attrib["version"]
        if el.tag == "xpath" and el.get("expr"):
            el.set("expr", self.convert_xpath(el.get("expr")))
        if el.tag == "field" and el.get("mode"):
            tokens = [t.strip() for t in el.get("mode").split(",")]
            el.set("mode", ",".join("list" if t == "tree" else t for t in tokens))

        for attr in REMOVED_ATTRS:
            if attr in el.attrib:
                self.remove_attr(el, attr, where)
        for attr in el.attrib:
            if CUSTOM_ATTR_RE.match(attr):
                self.warn(
                    f"{where}: '{attr}' is a Unifield customization, not an Odoo 20 "
                    "attribute: remove it or re-implement it"
                )
        icon = el.get("icon") or ""
        if icon.startswith(LEGACY_ICON_PREFIXES):
            self.warn(
                f"{where}: legacy icon '{icon}' does not exist anymore: use a fa-... icon"
            )

        modifiers = {}
        if "attrs" in el.attrib:
            converted = self.convert_attrs(el.get("attrs"), where)
            if converted is not None:
                del el.attrib["attrs"]
                modifiers.update(converted)
        if "states" in el.attrib:
            expr = self.states_expr(el.attrib.pop("states"))
            if modifiers.get("invisible"):
                expr = f"{expr} or {modifiers['invisible']}"
            modifiers["invisible"] = expr
        for key, expr in modifiers.items():
            el.set(key, expr)

        if "colors" in el.attrib:
            for key, expr in self.colors_to_decorations(el.attrib.pop("colors")).items():
                el.set(key, expr)
        if "on_change" in el.attrib:
            value = el.attrib.pop("on_change")
            self.warn(
                f'on_change="{value}" removed from {where}: write an @api.onchange method'
            )

    def convert_attribute(self, el):
        name = el.get("name")
        text = (el.text or "").strip()
        where = "an <attribute> of an inherited view"
        if name == "attrs":
            converted = self.convert_attrs(text, where)
            if converted is None:
                return
            pairs = list(converted.items())
        elif name == "states":
            pairs = [("invisible", self.states_expr(text))] if text else []
            if not text:
                self.warn("Empty <attribute name='states'> removed: check it")
        elif name == "colors":
            pairs = list(self.colors_to_decorations(text).items())
        elif name == "on_change":
            self.warn(f"<attribute name='on_change'>{text}</attribute> removed")
            pairs = []
        elif name in REMOVED_ATTRS:
            self.removed.setdefault(name, []).append(describe(el.getparent()))
            pairs = []
        else:
            return
        parent = el.getparent()
        index = parent.index(el)
        parent.remove(el)
        for offset, (key, value) in enumerate(pairs):
            new = etree.Element("attribute", name=key)
            new.text = value
            parent.insert(index + offset, new)
        if parent.get("position") == "attributes" and not parent.findall("attribute"):
            grand = parent.getparent()
            if grand is not None:
                grand.remove(parent)

    def convert(self, root):
        self.has_state_field = bool(root.xpath("//field[@name='state']"))
        for el in [e for e in root.iter() if isinstance(e.tag, str)]:
            if el.tag == "attribute":
                self.convert_attribute(el)
            else:
                self.convert_node(el)
        self.flush_removed()
        return root


def extract_xpaths(root):
    nodes = list(root) if root.tag == "data" else [root]
    result = []
    for node in nodes:
        if not isinstance(node.tag, str):
            continue
        position = node.get("position") or "inside"
        if node.tag == "xpath":
            expr = node.get("expr") or ""
        else:
            conditions = "".join(
                f"[@{key}='{value}']"
                for key, value in node.attrib.items()
                if key != "position"
            )
            expr = f"//{node.tag}{conditions}"
        result.append((position, expr))
    return result

def _attr(key, value):
    return f'{key}="{escape(value, {chr(34): "&quot;"})}"'


def serialize(el, level=0):
    pad = INDENT * level
    if not isinstance(el.tag, str):
        if el.tag is etree.Comment:
            return [f"{pad}<!--{el.text}-->"]
        return []
    attrs = [_attr(key, value) for key, value in el.attrib.items()]
    inline = " ".join([el.tag] + attrs)
    children = [c for c in el if isinstance(c.tag, str) or c.tag is etree.Comment]
    text = " ".join((el.text or "").split())

    if not children and not text:
        line = f"{pad}<{inline} />"
        if len(line) <= LINE_LENGTH or not attrs:
            return [line]
        return [f"{pad}<{el.tag}"] + [f"{pad}{INDENT}{a}" for a in attrs] + [f"{pad}/>"]
    if not children:
        line = f"{pad}<{inline}>{escape(text)}</{el.tag}>"
        if len(line) <= LINE_LENGTH or not attrs:
            return [line]
        return (
            [f"{pad}<{el.tag}"]
            + [f"{pad}{INDENT}{a}" for a in attrs]
            + [f"{pad}>{escape(text)}</{el.tag}>"]
        )

    start = f"{pad}<{inline}>"
    if len(start) <= LINE_LENGTH or not attrs:
        lines = [start]
    else:
        lines = [f"{pad}<{el.tag}"] + [f"{pad}{INDENT}{a}" for a in attrs] + [f"{pad}>"]
    if text:
        lines.append(f"{pad}{INDENT}{escape(text)}")
    for child in children:
        lines += serialize(child, level + 1)
        tail = " ".join((child.tail or "").split())
        if tail:
            lines.append(f"{pad}{INDENT}{escape(tail)}")
    lines.append(f"{pad}</{el.tag}>")
    return lines


def _comment(text, level):
    return f"{INDENT * level}<!-- {str(text).replace('--', '- -')} -->"


def _record_name(view, xml_ids, model_name):
    xml_id = xml_ids.get(view["id"])
    if xml_id and "." in xml_id:
        return xml_id.split(".", 1)[1]
    prefix = model_name.replace(".", "_") + "_" if model_name else ""
    return f"view_{prefix}{view['id']}"


def convert_views(model_name, views, xml_ids):
    summary = [f"{model_name}: {len(views)} view(s)", ""]
    records = []
    all_warnings = []

    for view in views:
        converter = ArchConverter()
        parent_id = view.get("inherit_id") or None
        xml_id = xml_ids.get(view["id"])
        label = xml_id or f"id {view['id']}"
        priority = view.get("priority")
        try:
            root = etree.fromstring(
                (view.get("arch") or "<data/>").encode("utf-8"),
                etree.XMLParser(remove_blank_text=False),
            )
            converter.convert(root)
            arch_lines = serialize(root, 3)
            xpaths = extract_xpaths(root) if parent_id else []
        except Exception:
            converter.warn(f"View could not be converted: {traceback.format_exc()}")
            arch_lines = [f"{INDENT * 3}<!-- arch not converted -->"]
            xpaths = []

        header = f"[{label}] {view.get('type') or ''}  priority={priority}"
        if parent_id:
            header += f"  inherits {xml_ids.get(parent_id) or 'id %s' % parent_id}"
        else:
            header += "  (base view)"
        summary.append(header)
        width = max([len(pos) for pos, _expr in xpaths] or [0])
        for position, expr in xpaths:
            summary.append(f"    {position.ljust(width)}  {expr}")
        summary.append("")
        all_warnings += [f"[{label}] {w}" for w in converter.warnings]

        lines = []
        origin = f"Unifield: {xml_id or 'no xml id'} ({view.get('type') or '?'})"
        lines.append(_comment(origin, 1))
        for warning in converter.warnings:
            lines.append(_comment(f"TODO: {warning}", 1))
        lines.append(
            f'{INDENT}<record id="{_record_name(view, xml_ids, model_name)}" '
            'model="ir.ui.view">'
        )
        lines.append(f'{INDENT * 2}<field name="name">{escape(view["name"])}</field>')
        if model_name:
            lines.append(f'{INDENT * 2}<field name="model">{model_name}</field>')
        if parent_id:
            ref = xml_ids.get(parent_id) or ""
            if not ref:
                lines.append(_comment(f"TODO: parent view id {parent_id} has no xml id", 2))
            lines.append(f'{INDENT * 2}<field name="inherit_id" ref="{ref}" />')
        if priority not in (None, False, DEFAULT_PRIORITY):
            lines.append(f'{INDENT * 2}<field name="priority">{priority}</field>')
        lines.append(f'{INDENT * 2}<field name="arch" type="xml">')
        lines += arch_lines
        lines.append(f"{INDENT * 2}</field>")
        lines.append(f"{INDENT}</record>")
        records.append("\n".join(lines))

    if all_warnings:
        summary.append("Warnings:")
        summary += [f"  - {w}" for w in all_warnings]
        summary.append("")

    xml = '<?xml version="1.0" encoding="utf-8" ?>\n<odoo>\n'
    xml += "\n\n".join(records)
    xml += "\n</odoo>\n"
    return "\n".join(summary).rstrip() + "\n", xml
