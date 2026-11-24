"""Generate the Pages inventory and routes from the tagged Python package."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.1"
LOCALES = ("en", "ru", "zh-CN")
# Each public module belongs to one reading topic and one editorial glossary.
TOPICS = {
    "generation": ("market", ("config", "generation", "models", "streaming", "registry")),
    "market-data": ("market", ("market_data", "io", "scenario")),
    "alternative-models": ("market", ("extended_models",)),
    "analysis": ("research", ("analysis", "fuzzy_diagnostics")),
    "monte-carlo": ("research", ("monte_carlo",)),
    "calibration": ("research", ("calibration", "evaluation")),
    "indicators": ("chart", ("indicators",)),
    "charts": ("chart", ("rendering.api", "rendering.adapters", "rendering.interactive",
                         "rendering.static", "rendering.exports", "rendering.theme")),
    "chart-types": ("chart", ("rendering.spec",)),
    "cli": ("chart", ("cli", "rendering.__main__")),
}


def PackageSources(package: Path | None) -> dict[str, str]:
    """Read the released source tree without importing the library or optional extras."""
    if package:
        return {p.relative_to(package).as_posix(): p.read_text(encoding="utf-8")
                for p in sorted(package.rglob("*.py"))}

    tree = f"v{VERSION}:pricegenerator"
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", tree],
                                    cwd=ROOT, text=True).splitlines()
    return {path: subprocess.check_output(["git", "show", f"{tree}/{path}"], cwd=ROOT,
                                          encoding="utf-8") for path in paths if path.endswith(".py")}


def FunctionArguments(args: ast.arguments) -> tuple[list[str], list[str]]:
    """Retain keyword-only markers, optional values and annotations from the declaration."""
    parts, names = [], []
    positional = args.posonlyargs + args.args
    defaults = [None] * (len(positional) - len(args.defaults)) + args.defaults

    def Add(arg: ast.arg, default: ast.expr | None = None, prefix: str = "") -> None:
        if arg.arg in ("cls", "self"):
            return
        names.append(arg.arg)
        part = prefix + ast.unparse(arg)
        if default is not None:
            part += (" = " if arg.annotation else "=") + ast.unparse(default)
        parts.append(part)

    for index, (arg, default) in enumerate(zip(positional, defaults), 1):
        Add(arg, default)
        if index == len(args.posonlyargs):
            parts.append("/")
    if args.vararg:
        Add(args.vararg, prefix="*")
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        Add(arg, default)
    if args.kwarg:
        Add(args.kwarg, prefix="**")
    return parts, names


def Entry(node: ast.FunctionDef | ast.ClassDef, module: str, parent: str = "") -> dict:
    """Describe one callable, including the generated constructor of a dataclass."""
    name = f"{parent}.{node.name}" if parent else node.name
    returns = ""
    if isinstance(node, ast.FunctionDef):
        parts, names = FunctionArguments(node.args)
        kind = "method" if parent else "function"
        if node.returns:
            returns = " -> " + ast.unparse(node.returns)
    else:
        fields = [s for s in node.body if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)]
        parts = [ast.unparse(field) for field in fields]
        names = [field.target.id for field in fields]
        kind = "class"

    signature = f"{name}({', '.join(parts)}){returns}"
    if len(signature) > 95 and parts:
        signature = name + "(\n    " + ",\n    ".join(parts) + ",\n)" + returns
    if isinstance(node, ast.ClassDef) and node.bases:
        signature = "class " + name + "(" + ", ".join(map(ast.unparse, node.bases)) + ")"
    return {"key": f"{module}.{name}", "name": name, "kind": kind, "signature": signature,
            "terms": names, "line": node.lineno}


def Inventory(sources: dict[str, str]) -> dict:
    """Index all public definitions and resolve the two published import facades."""
    modules, aliases = {}, {}
    public_paths = {path for path in sources if not any(piece.startswith("_") for piece in path.split("/"))}
    public_paths.add("rendering/__main__.py")
    for topic, (domain, module_ids) in TOPICS.items():
        for module in module_ids:
            path = module.replace(".", "/") + ".py"
            public_paths.remove(path)
            body = ast.parse(sources[path]).body
            entries, constants = [], []
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
                    entries.append(Entry(node, module))
                    if isinstance(node, ast.ClassDef):
                        entries.extend(Entry(member, module, node.name) for member in node.body
                                       if isinstance(member, ast.FunctionDef) and not member.name.startswith("_"))
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                    key = node.targets[0].id
                    if key.isupper() and not key.startswith("_"):
                        value = ast.unparse(node.value)
                        constants.append({"name": key, "line": node.lineno,
                                          "value": value if len(value) <= 135 else ""})
            modules[module] = {"topic": topic, "domain": domain, "file": path,
                               "entries": entries, "constants": constants}
    if public_paths:
        raise ValueError(f"Unassigned public modules: {sorted(public_paths)}")

    for facade, path in (("pricegenerator", "__init__.py"), ("pricegenerator.rendering", "rendering/__init__.py")):
        imports, exports, lazy = {}, [], {}
        for node in ast.parse(sources[path]).body:
            if isinstance(node, ast.ImportFrom):
                prefix = "rendering." if node.level else ""
                target = prefix + (node.module or "").removeprefix("pricegenerator.")
                imports.update({item.asname or item.name: f"{target}.{item.name}" for item in node.names})
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id == "_EXPORTS":
                    lazy = ast.literal_eval(node.value)
                    for name, (module, member) in lazy.items():
                        imports[name] = f"{module}.{member}"
                elif node.targets[0].id == "__all__":
                    for item in node.value.elts:
                        if isinstance(item, ast.Starred):
                            if item.value.id != "_EXPORTS":
                                raise ValueError(f"Unknown export group: {ast.unparse(item)}")
                            exports.extend(lazy)
                        else:
                            exports.append(ast.literal_eval(item))
        for name in exports:
            aliases[f"{facade}.{name}"] = imports[name]
    return {"version": VERSION, "topics": list(TOPICS), "modules": modules, "aliases": aliases}


def OutputFiles(catalog: dict) -> dict[Path, str]:
    """Create the versioned data file and the matching locales and latest aliases."""
    files = {ROOT / "_data/api_2_2_1.json": json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"}
    for locale in LOCALES:
        prefix = locale.lower()
        for topic in ("index", *TOPICS):
            suffix = "" if topic == "index" else topic + "/"
            route = f"/api/{VERSION}/{prefix}/{suffix}"
            aliases = [f"/api/latest/{prefix}/{suffix}"]
            if topic == "index" and locale == "en":
                aliases.extend(("/api/", "/api/latest/", f"/api/{VERSION}/"))
            files[ROOT / route.strip("/") / "index.html"] = (
                f"---\nlayout: api\nlang: {locale}\napi_topic: {topic}\npermalink: {route}\n"
                + "redirect_from:\n" + "".join(f"  - {alias}\n" for alias in aliases) + "---\n")
    return files


def CheckCopy(catalog: dict) -> None:
    """Check all three translations for every release declaration and its parameters."""
    domains = {module["domain"] for module in catalog["modules"].values()}
    copies = {domain: json.loads((ROOT / f"_data/api_copy/{domain}.json").read_text(encoding="utf-8"))
              for domain in domains}

    def Require(entries: dict, key: str) -> None:
        translations = entries.get(key, {})
        if set(translations) != set(LOCALES) or not all(isinstance(t, str) and t.strip()
                                                       for t in translations.values()):
            raise ValueError(f"Incomplete API translation: {key}")

    for mod, module in catalog["modules"].items():
        copy = copies[module["domain"]]
        Require(copy["modules"], mod)
        for constant in module["constants"]:
            Require(copy["symbols"], mod + "." + constant["name"])
        for entry in module["entries"]:
            Require(copy["symbols"], entry["key"])
            for name in entry["terms"]:
                qualified = entry["key"] + "." + name
                Require(copy["terms"], qualified if qualified in copy["terms"] else name)


def Main() -> int:
    """Refresh files, or check that the committed version matches the release tag."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, help="Read an unpacked wheel's pricegenerator directory")
    parser.add_argument("--check", action="store_true", help="Report stale or missing files without writing")
    parser.add_argument("--check-copy", action="store_true", help="Check translations and routes in a shallow checkout")
    options = parser.parse_args()
    if options.check_copy:
        catalog = json.loads((ROOT / "_data/api_2_2_1.json").read_text(encoding="utf-8"))
    else:
        catalog = Inventory(PackageSources(options.package))
    CheckCopy(catalog)
    stale = []
    for path, content in OutputFiles(catalog).items():
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        if options.check or options.check_copy:
            stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    for path in stale:
        print(f"Out of date: {path}")
    return int(bool(stale))


if __name__ == "__main__":
    raise SystemExit(Main())
