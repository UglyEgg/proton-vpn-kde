#!/usr/bin/env python3
"""Import exact shared strings from Proton's gettext catalogs into Qt TS files."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET


SOURCE_PATHS = (
    "qml",
    "src",
    "runner",
    "kcm/ProtonVpnKcm.cpp",
    "kcm/ProtonVpnKcm.h",
    "kcm/ui",
)


def qt_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    candidate = Path("/usr/lib64/qt6/bin") / name
    if candidate.is_file():
        return str(candidate)
    raise FileNotFoundError(f"Qt Linguist tool not found: {name}")


def translated_messages(root: ET.Element) -> dict[str, ET.Element]:
    candidates: dict[str, list[ET.Element]] = {}
    for message in root.findall("./context/message"):
        source = message.findtext("source")
        translation = message.find("translation")
        if not source or translation is None:
            continue
        if translation.get("type") in {"unfinished", "vanished", "obsolete"}:
            continue
        if not "".join(translation.itertext()).strip():
            continue
        candidates.setdefault(source, []).append(translation)

    unambiguous: dict[str, ET.Element] = {}
    for source, translations in candidates.items():
        serialized = {ET.tostring(item, encoding="unicode") for item in translations}
        if len(serialized) == 1:
            unambiguous[source] = translations[0]
    return unambiguous


def language_from_converted(root: ET.Element, fallback: str) -> str:
    # Proton ships explicit regional aliases such as zh_HK whose PO header uses
    # the parent catalog language. Keep the filename locale so Qt can select
    # the alias for that exact system locale.
    if "_" in fallback:
        return fallback
    language = root.findtext("extra-po-header-language")
    return language.strip() if language and language.strip() else fallback


def normalized_translation(translation: ET.Element) -> ET.Element:
    result = deepcopy(translation)
    for element in result.iter():
        if element.text and "\n" in element.text:
            element.text = "\n".join(
                line.rstrip() for line in element.text.split("\n")
            )
        if element.tail and "\n" in element.tail:
            element.tail = "\n".join(
                line.rstrip() for line in element.tail.split("\n")
            )
    return result


def write_catalog(
    template: ET.Element,
    translations: dict[str, ET.Element],
    language: str,
    output: Path,
) -> int:
    result = ET.Element(
        "TS", {"version": "2.1", "language": language, "sourcelanguage": "en"}
    )
    count = 0
    for source_context in template.findall("context"):
        messages: list[ET.Element] = []
        for source_message in source_context.findall("message"):
            source = source_message.findtext("source")
            if not source or source not in translations:
                continue
            message = ET.Element("message", source_message.attrib)
            for tag in ("source", "comment", "extracomment"):
                value = source_message.find(tag)
                if value is not None:
                    message.append(deepcopy(value))
            message.append(normalized_translation(translations[source]))
            messages.append(message)
            count += 1
        if messages:
            context = ET.SubElement(result, "context")
            name = ET.SubElement(context, "name")
            name.text = source_context.findtext("name", default="")
            context.extend(messages)

    ET.indent(result, space="    ")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=output.parent, prefix=f".{output.name}.", delete=False
    ) as temporary:
        temporary.write(b'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n')
        ET.ElementTree(result).write(temporary, encoding="utf-8", xml_declaration=False)
        temporary.write(b"\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(output)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "official_locale_dir",
        type=Path,
        help="directory containing Proton VPN GTK .po catalogs",
    )
    parser.add_argument(
        "--source-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("translations")
    )
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    locale_dir = args.official_locale_dir.resolve()
    output_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else source_root / args.output_dir
    )
    po_files = sorted(locale_dir.glob("*.po"))
    if not po_files:
        raise FileNotFoundError(f"No .po catalogs found in {locale_dir}")

    with tempfile.TemporaryDirectory(prefix="proton-vpn-kde-i18n-") as temp:
        temp_dir = Path(temp)
        template_path = temp_dir / "source.ts"
        subprocess.run(
            [
                qt_tool("lupdate"),
                *(str(source_root / path) for path in SOURCE_PATHS),
                "-no-obsolete",
                "-locations",
                "none",
                "-source-language",
                "en",
                "-ts",
                str(template_path),
            ],
            check=True,
        )
        template = ET.parse(template_path).getroot()

        outputs: set[Path] = set()
        for po_file in po_files:
            converted_path = temp_dir / f"{po_file.stem}.ts"
            subprocess.run(
                [qt_tool("lconvert"), "-i", str(po_file), "-o", str(converted_path)],
                check=True,
            )
            converted = ET.parse(converted_path).getroot()
            language = language_from_converted(converted, po_file.stem)
            output = output_dir / f"proton-vpn-kde_{language}.ts"
            if output in outputs:
                raise ValueError(
                    f"Multiple Proton catalogs resolve to the Qt locale {language}"
                )
            outputs.add(output)
            count = write_catalog(
                template, translated_messages(converted), language, output
            )
            print(f"{language}: imported {count} exact shared strings -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
