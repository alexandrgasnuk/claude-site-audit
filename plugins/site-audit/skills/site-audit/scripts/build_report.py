#!/usr/bin/env python3
"""Build the audit report (.docx) from findings.json and print the Google Drive upload arguments.

Usage:
  build_report.py AUDIT_DIR/findings.json [--out FILE.docx]

Checks every finding against the team's acceptance criteria first and exits
with a list of problems if any fail. Standard library only; when Pillow is
installed it also shrinks large screenshots and converts WebP.
"""
import argparse
import hashlib
import io
import json
import os
import re
import struct
import sys
import urllib.parse
import zipfile
from xml.sax.saxutils import escape

CATEGORY_COLORS = {
    "PERFORMANCE": "FCE5CD", "BUG": "F4CCCC", "UX": "00FFFF", "UI": "C9DAF8",
    "ACCESSIBILITY": "D9D2E9", "SEO": "D9EAD3", "FEATURE": "FFF2CC", "DEVOPS": "D0E0E3",
}
ALIASES = {"A11Y": "ACCESSIBILITY", "OPTIMIZATION": "PERFORMANCE", "SPEED": "PERFORMANCE", "FEATURES": "FEATURE"}
REQUIRED = ["category", "title", "impact", "where", "observed", "why", "recommendation"]
LENGTHS = {"title": 80, "observed": 400, "why": 250, "recommendation": 350}
IMPACT_COLORS = {"High": "F4CCCC", "Medium": "FFF2CC", "Low": "D9EAD3"}
RATING_COLORS = {"good": "D9EAD3", "needs improvement": "FFF2CC", "poor": "F4CCCC"}
CRUX_RATING = {"FAST": "good", "AVERAGE": "needs improvement", "SLOW": "poor"}
FIELD_METRICS = [("LARGEST_CONTENTFUL_PAINT_MS", "LCP"), ("INTERACTION_TO_NEXT_PAINT", "INP"),
                 ("CUMULATIVE_LAYOUT_SHIFT_SCORE", "CLS")]
LAB_METRICS = [("first-contentful-paint", "FCP"), ("largest-contentful-paint", "LCP"),
               ("total-blocking-time", "TBT"), ("cumulative-layout-shift", "CLS")]
SHOT_REQUIRED = ("UX", "UI")  # visual problems: a screenshot is mandatory, in findings and in minor items
PROOF = ["screenshots", "measurement", "steps", "error", "evidence"]
MEASUREMENT = ["metric", "value", "page", "device", "tool"]
CONFIG = os.path.expanduser("~/.config/site-audit/config.json")
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
EMU_PER_INCH = 914400
MAX_W_IN, MAX_H_IN = 6.4, 7.2
URL_RE = re.compile(r"https?://[^\s<>\"']+")

XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
NAMESPACES = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
              f'xmlns:r="{REL}" '
              'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
              'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
              'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')
SECTION = ('<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1080" w:right="1080" '
           'w:bottom="1080" w:left="1080" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>')
CONTENT_TYPES = XML_HEAD + (
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Default Extension="png" ContentType="image/png"/>'
    '<Default Extension="jpeg" ContentType="image/jpeg"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/word/numbering.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
    '</Types>')
ROOT_RELS = XML_HEAD + (
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    f'<Relationship Id="rId1" Type="{REL}/officeDocument" Target="word/document.xml"/></Relationships>')
STYLES = XML_HEAD + (
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:docDefaults><w:rPrDefault><w:rPr>'
    '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/>'
    '<w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:rPrDefault>'
    '<w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
    '</w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
    '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
    '<w:next w:val="Normal"/><w:pPr><w:spacing w:after="160"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="40"/><w:szCs w:val="40"/></w:rPr></w:style>'
    '</w:styles>')
# abstractNum 0: the findings (1. 2. 3.), 1: steps to reproduce, 2: evidence bullets.
NUMBERING = XML_HEAD + (
    '<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/>'
    '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/>'
    '<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="360" w:hanging="360"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:lvl></w:abstractNum>'
    '<w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="singleLevel"/>'
    '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/>'
    '<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>'
    '<w:abstractNum w:abstractNumId="2"><w:multiLevelType w:val="singleLevel"/>'
    '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/>'
    '<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>'
    '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><!--NUMS--></w:numbering>')


def clip(text, n=50):
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


def xml_text(text):
    return escape(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(text)))


def validate(doc, base_dir):
    errors, warnings = [], []
    for key in ("site", "date"):
        if not str(doc.get(key, "")).strip():
            errors.append(f"top level: '{key}' is required")
    findings = doc.get("findings")
    if not isinstance(findings, list) or not findings:
        errors.append("top level: 'findings' must be a non-empty list")
        return errors, warnings
    if len(findings) < 10 and not str(doc.get("summary", "")).strip():
        warnings.append(f"{len(findings)} findings: fewer than 10 is fine on a clean site, but say why in 'summary'")
    if len(findings) > 15:
        warnings.append(f"{len(findings)} findings: keep the most significant 15")
    for n, f in enumerate(findings, 1):
        label = f"finding {n} ({clip(f.get('title', '?'))})"
        for key in REQUIRED:
            if not str(f.get(key, "")).strip():
                errors.append(f"{label}: '{key}' is required")
        category = str(f.get("category", "")).strip().upper()
        category = ALIASES.get(category, category)
        if category not in CATEGORY_COLORS:
            errors.append(f"{label}: category must be one of {', '.join(CATEGORY_COLORS)}")
        f["category"] = category
        impact = str(f.get("impact", "")).strip().capitalize()
        if impact and impact not in IMPACT_COLORS:
            errors.append(f"{label}: impact must be one of {', '.join(IMPACT_COLORS)}")
        f["impact"] = impact
        for key, limit in LENGTHS.items():
            if len(str(f.get(key, ""))) > limit:
                warnings.append(f"{label}: '{key}' has {len(str(f[key]))} characters; keep it under about {limit} "
                                "(SKILL.md, \"Writing each finding\")")
        for key in ("screenshots", "steps", "evidence"):
            if key in f and not isinstance(f[key], list):
                errors.append(f"{label}: '{key}' must be a list")
        if "caveat" in f and not isinstance(f["caveat"], str):
            errors.append(f"{label}: 'caveat' must be a string")
        if not any(f.get(k) for k in PROOF):
            errors.append(f"{label}: add proof ({', '.join(PROOF)})")
        measurement = f.get("measurement")
        if measurement:
            missing = [k for k in MEASUREMENT if not str(measurement.get(k, "")).strip()]
            if missing:
                errors.append(f"{label}: measurement needs {', '.join(missing)}")
        elif category == "PERFORMANCE":
            errors.append(f"{label}: PERFORMANCE needs a measurement ({', '.join(MEASUREMENT)})")
        if category == "BUG" and not (f.get("steps") or f.get("error")):
            errors.append(f"{label}: BUG needs 'steps' to reproduce or the exact 'error' text")
        if category in SHOT_REQUIRED and not f.get("screenshots"):
            errors.append(f"{label}: {category} needs a screenshot")
        for shot in f.get("screenshots") or []:
            if not os.path.isfile(os.path.join(base_dir, shot)):
                errors.append(f"{label}: screenshot not found: {shot}")
    minor = doc.get("minor", [])
    if not isinstance(minor, list):
        errors.append("top level: 'minor' must be a list")
        minor = []
    for n, m in enumerate(minor, 1):
        label = f"minor {n}"
        if not isinstance(m, dict) or not str(m.get("text", "")).strip():
            errors.append(f"{label}: needs 'category' and 'text'")
            continue
        category = str(m.get("category", "")).strip().upper()
        m["category"] = ALIASES.get(category, category)
        if m["category"] not in CATEGORY_COLORS:
            errors.append(f"{label}: category must be one of {', '.join(CATEGORY_COLORS)}")
        shot = m.get("screenshot")
        if m["category"] in SHOT_REQUIRED and not shot:
            errors.append(f"{label}: {m['category']} needs a 'screenshot'")
        if shot and not os.path.isfile(os.path.join(base_dir, shot)):
            errors.append(f"{label}: screenshot not found: {shot}")
        if len(m["text"]) > 350:
            warnings.append(f"{label}: keep it to one or two sentences (now {len(m['text'])} characters)")
    if len(minor) > 8:
        warnings.append(f"{len(minor)} minor items: keep the 8 most useful")
    if len(str(doc.get("summary", ""))) > 400:
        warnings.append(f"summary has {len(doc['summary'])} characters; keep it to two or three sentences")
    psi = doc.get("psi", [])
    if not isinstance(psi, list):
        errors.append("top level: 'psi' must be a list of saved psi.py JSON files")
        psi = []
    for path in psi:
        if not os.path.isfile(os.path.join(base_dir, path)):
            errors.append(f"psi: file not found: {path}")
    categories = [f.get("category") for f in findings]
    if "FEATURE" in categories and any(c != "FEATURE" for c in categories[categories.index("FEATURE"):]):
        warnings.append("FEATURE findings go after all other findings")
    return errors, warnings


def image_info(data):
    """((width, height), kind) for PNG or JPEG bytes, else (None, None)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24]), "png"
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return (width, height), "jpeg"
            if marker == 0xFF:
                i += 1
            elif marker == 0x01 or 0xD0 <= marker <= 0xD9:
                i += 2
            else:
                i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None, None


def load_image(path):
    with open(path, "rb") as f:
        data = f.read()
    dims, kind = image_info(data)
    try:
        from PIL import Image
    except ImportError:
        Image = None
    if Image and (kind is None or len(data) > 700_000 or dims[0] > 1600):
        img = Image.open(io.BytesIO(data))
        if img.width > 1600:
            resample = getattr(Image, "Resampling", Image).LANCZOS
            img = img.resize((1600, round(img.height * 1600 / img.width)), resample)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=85, optimize=True)
        data, kind, dims = buf.getvalue(), "jpeg", img.size
    if kind is None:
        sys.exit(f"{path}: use PNG or JPEG screenshots (or install Pillow to convert other formats)")
    return data, kind, dims


class Docx:
    def __init__(self):
        self.body, self.rels, self.media, self.lists = [], [], [], []

    def _rel(self, kind, target, external=False):
        rid = f"rId{len(self.rels) + 10}"
        self.rels.append((rid, kind, target, external))
        return rid

    def run(self, text, bold=False, mono=False, color=None, size=None, underline=False, fill=None):
        props = ""
        if mono:
            props += '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/>'
        if bold:
            props += "<w:b/>"
        if color:
            props += f'<w:color w:val="{color}"/>'
        if size:
            props += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
        if underline:
            props += '<w:u w:val="single"/>'
        if fill:
            props += f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>'
        rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
        return f'<w:r>{rpr}<w:t xml:space="preserve">{xml_text(text)}</w:t></w:r>'

    def rich(self, text, **style):
        """Runs for `text`, with every URL turned into a hyperlink."""
        text, out, pos = str(text), [], 0
        for match in URL_RE.finditer(text):
            url = match.group(0).rstrip(".,;:!?)")
            if match.start() > pos:
                out.append(self.run(text[pos:match.start()], **style))
            rid = self._rel("hyperlink", url, external=True)
            link = self.run(url, color="1155CC", underline=True, size=style.get("size"))
            out.append(f'<w:hyperlink r:id="{rid}">{link}</w:hyperlink>')
            pos = match.start() + len(url)
        if pos < len(text):
            out.append(self.run(text[pos:], **style))
        return "".join(out)

    def para(self, content, style=None, num=None, indent=None, keep_next=False, before=None, after=None):
        ppr = ""
        if style:
            ppr += f'<w:pStyle w:val="{style}"/>'
        if keep_next:
            ppr += "<w:keepNext/>"
        if num:
            ppr += f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num}"/></w:numPr>'
        if before is not None or after is not None:
            ppr += f'<w:spacing w:before="{before or 0}" w:after="{80 if after is None else after}"/>'
        if indent is not None:
            ppr += f'<w:ind w:left="{indent}"/>'
        self.body.append(f"<w:p><w:pPr>{ppr}</w:pPr>{content}</w:p>")

    def table(self, widths, rows, header_fill="EFEFEF"):
        """rows: lists of cells; a cell is runs XML, or (runs XML, fill). The first row is the header."""
        border = "".join(f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>'
                         for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
        grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
        xml = [f'<w:tbl><w:tblPr><w:tblW w:w="{sum(widths)}" w:type="dxa"/><w:tblBorders>{border}</w:tblBorders>'
               '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="60" w:type="dxa"/>'
               '<w:left w:w="100" w:type="dxa"/><w:bottom w:w="60" w:type="dxa"/><w:right w:w="100" w:type="dxa"/>'
               f'</w:tblCellMar></w:tblPr><w:tblGrid>{grid}</w:tblGrid>']
        for i, row in enumerate(rows):
            trpr = '<w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>' if i == 0 else '<w:trPr><w:cantSplit/></w:trPr>'
            cells = []
            for width, cell in zip(widths, row):
                content, fill = cell if isinstance(cell, tuple) else (cell, header_fill if i == 0 else None)
                shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
                cells.append(f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shd}</w:tcPr>'
                             f'<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>{content}</w:p></w:tc>')
            xml.append(f"<w:tr>{trpr}{''.join(cells)}</w:tr>")
        self.body.append("".join(xml) + "</w:tbl>")

    def new_list(self, abstract_id):
        """A new list instance that starts counting at 1."""
        num_id = len(self.lists) + 2  # numId 1 is the findings list
        self.lists.append((num_id, abstract_id))
        return num_id

    def image(self, path, indent=360, max_w=MAX_W_IN, max_h=MAX_H_IN):
        data, kind, (width, height) = load_image(path)
        n = len(self.media) + 1
        name = f"image{n}.{'png' if kind == 'png' else 'jpeg'}"
        self.media.append((name, data))
        rid = self._rel("image", f"media/{name}")
        w_in = min(max_w, width / 96)
        h_in = w_in * height / width
        if h_in > max_h:
            w_in, h_in = w_in * max_h / h_in, max_h
        cx, cy = int(w_in * EMU_PER_INCH), int(h_in * EMU_PER_INCH)
        self.body.append(
            f'<w:p><w:pPr><w:spacing w:before="120" w:after="240"/><w:ind w:left="{indent}"/></w:pPr>'
            '<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{n}" name="Screenshot {n}"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>'
            f'<pic:nvPicPr><pic:cNvPr id="{n}" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            '<a:ln w="9525"><a:solidFill><a:srgbClr val="BFBFBF"/></a:solidFill></a:ln></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')

    def save(self, path):
        rels = [f'<Relationship Id="rId1" Type="{REL}/styles" Target="styles.xml"/>',
                f'<Relationship Id="rId2" Type="{REL}/numbering" Target="numbering.xml"/>']
        for rid, kind, target, external in self.rels:
            mode = ' TargetMode="External"' if external else ""
            target = escape(target, {'"': "&quot;"})
            rels.append(f'<Relationship Id="{rid}" Type="{REL}/{kind}" Target="{target}"{mode}/>')
        nums = "".join(
            f'<w:num w:numId="{num_id}"><w:abstractNumId w:val="{abstract}"/>'
            '<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'
            for num_id, abstract in self.lists)
        document = XML_HEAD + f'<w:document {NAMESPACES}><w:body>{"".join(self.body)}{SECTION}</w:body></w:document>'
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", CONTENT_TYPES)
            z.writestr("_rels/.rels", ROOT_RELS)
            z.writestr("word/document.xml", document)
            z.writestr("word/styles.xml", STYLES)
            z.writestr("word/numbering.xml", NUMBERING.replace("<!--NUMS-->", nums))
            z.writestr("word/_rels/document.xml.rels", XML_HEAD
                       + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       + "".join(rels) + "</Relationships>")
            for name, data in self.media:
                z.writestr(f"word/media/{name}", data)


def score_rating(score):
    if score is None:
        return None
    return "good" if score >= 0.9 else "needs improvement" if score >= 0.5 else "poor"


def seconds(v):
    return f"{v / 1000:.1f} s" if v >= 1000 else f"{v:.0f} ms"


def psi_rows(paths, base_dir):
    """One dict per saved psi.py run: page, device, field values and lab values, each as (text, rating)."""
    rows = []
    for path in paths:
        with open(os.path.join(base_dir, path), encoding="utf-8") as f:
            data = json.load(f)
        lr = data["lighthouseResult"]
        url = lr.get("finalDisplayedUrl") or lr.get("requestedUrl") or ""
        row = {"url": url, "page": urllib.parse.urlsplit(url).path or "/",
               "device": (lr.get("configSettings") or {}).get("formFactor", "?"),
               "date": (lr.get("fetchTime") or "")[:10], "version": lr.get("lighthouseVersion"),
               "runs": len(data.get("_runs") or []) or 1, "field": {}, "field_scope": "no data"}
        for key, scope in (("loadingExperience", "this page"), ("originLoadingExperience", "whole site")):
            exp = data.get(key) or {}
            if exp.get("metrics") and not exp.get("origin_fallback"):
                row["field_scope"] = scope
                for name, label in FIELD_METRICS:
                    m = exp["metrics"].get(name)
                    if m:
                        value = f"{m['percentile'] / 100:.2f}" if label == "CLS" else seconds(m["percentile"])
                        row["field"][label] = (value, CRUX_RATING.get(m.get("category")))
                break
        perf = (lr.get("categories") or {}).get("performance") or {}
        row["score"] = (str(round(perf["score"] * 100)) if perf.get("score") is not None else "-",
                        score_rating(perf.get("score")))
        audits = lr.get("audits") or {}
        row["lab"] = {label: ((audits.get(aid) or {}).get("displayValue", "-").replace(chr(160), " "),
                              score_rating((audits.get(aid) or {}).get("score"))) for aid, label in LAB_METRICS}
        rows.append(row)
    order = list(dict.fromkeys(r["url"] for r in rows))
    rows.sort(key=lambda r: (order.index(r["url"]), r["device"] != "mobile"))
    return rows


def psi_section(d, rows):
    def cell(pair):
        text, rating = pair
        return (d.run(text, size=19), RATING_COLORS.get(rating)) if rating else d.run(text, size=19)
    head = lambda *names: [d.run(n, bold=True, size=19) for n in names]
    page = lambda r: d.run(clip(r["page"], 40), size=19)
    device = lambda r: d.run(r["device"].capitalize(), size=19)
    d.para(d.run("Performance data", bold=True, size=26), keep_next=True, before=600, after=60)
    d.para(d.run("Real users: Core Web Vitals", bold=True), keep_next=True, before=120, after=60)
    d.para(d.run("What Chrome users of this site experienced over the last 28 days (75th percentile, Chrome UX "
                 "Report). Google uses these numbers to judge Core Web Vitals.", color="555555", size=20),
           keep_next=True, after=120)
    table, site_rows = [head("Page", "Device", "LCP", "INP", "CLS", "Data for")], set()
    for r in rows:
        if r["field_scope"] == "whole site":  # the same numbers for every page: one row per device
            if r["device"] in site_rows:
                continue
            site_rows.add(r["device"])
            label, scope = d.run("Whole site", size=19), "whole site (too few visits for page data)"
        else:
            label, scope = page(r), r["field_scope"]
        table.append([label, device(r)] + [cell(r["field"].get(m, ("-", None))) for m in ("LCP", "INP", "CLS")]
                     + [d.run(scope, size=19)])
    d.table([3000, 1100, 1300, 1300, 1300, 2080], table)
    runs = max(r["runs"] for r in rows)
    d.para(d.run("Lab test: Lighthouse", bold=True), keep_next=True, before=240, after=60)
    d.para(d.run(f"A synthetic load on Google's servers, the phone test on an emulated mid-range phone and a "
                 f"throttled mobile connection. {'Median of ' + str(runs) + ' runs. ' if runs > 1 else ''}"
                 "Lab results vary from run to run, so a new test shows close but not identical numbers.",
                 color="555555", size=20), keep_next=True, after=120)
    table = [head("Page", "Device", "Score", "FCP", "LCP", "TBT", "CLS")]
    for r in rows:
        table.append([page(r), device(r), cell(r["score"])] + [cell(r["lab"][m]) for m in ("FCP", "LCP", "TBT", "CLS")])
    d.table([2780, 1100, 1000, 1300, 1300, 1300, 1300], table)
    dates = sorted({r["date"] for r in rows if r["date"]})
    versions = sorted({str(r["version"]) for r in rows if r["version"]})
    d.para(d.run(f"Source: Google PageSpeed Insights, Lighthouse {', '.join(versions)}, {', '.join(dates)}. "
                 "Run the test yourself:", color="555555", size=20), before=120, after=40)
    links = d.new_list(2)
    for url in dict.fromkeys(r["url"] for r in rows):
        d.para(d.rich("https://pagespeed.web.dev/analysis?url=" + urllib.parse.quote(url, safe=""), size=19), num=links)


def build(doc, base_dir, out_path):
    d = Docx()
    d.para(d.run(f"Audit of {doc['site']}"), style="Title")
    for label, key in (("Date", "date"), ("Platform", "platform"), ("Pages reviewed", "scope"), ("Tools", "tools")):
        if doc.get(key):
            d.para(d.run(f"{label}: ", bold=True, color="555555", size=20)
                   + d.rich(doc[key], color="555555", size=20), after=40)
    if doc.get("summary"):
        d.para(d.rich(doc["summary"]), before=240, after=120)
    d.para(d.run("Findings at a glance", bold=True, size=26), keep_next=True, before=240, after=120)
    rows = [[d.run(h, bold=True, size=20) for h in ("#", "Type", "Finding", "Impact")]]
    for n, f in enumerate(doc["findings"], 1):
        impact = f.get("impact") or "-"
        rows.append([d.run(str(n), size=20), (d.run(f["category"], bold=True, size=18), CATEGORY_COLORS[f["category"]]),
                     d.run(f["title"], size=20), (d.run(impact, bold=True, size=20), IMPACT_COLORS.get(impact))])
    d.table([500, 1900, 6280, 1400], rows)
    bullets = d.new_list(2)
    shots = 0
    for f in doc["findings"]:
        tag = d.run(f" {f['category']} ", bold=True, fill=CATEGORY_COLORS[f["category"]])
        d.para(tag + d.run("  ") + d.run(f["title"], bold=True, size=24), num=1, keep_next=True, before=480, after=120)
        if f.get("impact"):
            d.para(d.run("Impact: ", bold=True) + d.run(f" {f['impact']} ", bold=True, fill=IMPACT_COLORS[f["impact"]]),
                   indent=360)
        for label, key in (("Where", "where"), ("Observed", "observed"),
                           ("Why it matters", "why"), ("Recommendation", "recommendation")):
            d.para(d.run(f"{label}: ", bold=True) + d.rich(f[key]), indent=360)
        if f.get("caveat"):
            d.para(d.run("Note: ", bold=True, color="B45F06") + d.rich(f["caveat"], color="B45F06"), indent=360)
        m = f.get("measurement")
        if m:
            line = f"{m['metric']}: {m['value']} — {m['device']}, {m['tool']}"
            line += (f", {m['date']}" if m.get("date") else "") + f" — {m['page']}"
            d.para(d.run("Measured: ", bold=True) + d.rich(line), indent=360)
        if f.get("steps"):
            d.para(d.run("Steps to reproduce:", bold=True), indent=360, keep_next=True)
            steps = d.new_list(1)
            for step in f["steps"]:
                d.para(d.rich(step), num=steps)
        if f.get("error"):
            d.para(d.run("Error: ", bold=True) + d.run(f["error"], mono=True, size=18), indent=360)
        for line in f.get("evidence") or []:
            d.para(d.rich(line), num=bullets)
        for shot in f.get("screenshots") or []:
            d.image(os.path.join(base_dir, shot))
            shots += 1
    if doc.get("minor"):
        d.para(d.run("Also worth mentioning", bold=True, size=26), keep_next=True, before=600, after=60)
        d.para(d.run("Smaller items that did not make the main list.", color="555555", size=20), after=120)
        minor = d.new_list(2)
        for m in doc["minor"]:
            d.para(d.run(f" {m['category']} ", bold=True, size=18, fill=CATEGORY_COLORS[m["category"]])
                   + d.run("  ") + d.rich(m["text"]), num=minor)
            if m.get("screenshot"):
                d.image(os.path.join(base_dir, m["screenshot"]), indent=720, max_w=4.5, max_h=4.0)
                shots += 1
    if doc.get("psi"):
        psi_section(d, psi_rows(doc["psi"], base_dir))
    d.save(out_path)
    return shots


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("findings", help="path to findings.json")
    parser.add_argument("--out", help="output .docx (default: Audit-of-<site>.docx next to findings.json)")
    args = parser.parse_args()
    path = os.path.abspath(args.findings)
    base_dir = os.path.dirname(path)
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    errors, warnings = validate(doc, base_dir)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        print("findings.json does not meet the report rules yet:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    name = re.sub(r"[^A-Za-z0-9.-]+", "-", doc["site"]).strip("-")
    out = os.path.abspath(args.out or os.path.join(base_dir, f"Audit-of-{name}.docx"))
    shots = build(doc, base_dir, out)
    with open(out, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    try:
        with open(CONFIG) as f:
            folder = json.load(f).get("drive_folder_id")
    except (OSError, ValueError):
        folder = None
    print(f"Report: {out} ({os.path.getsize(out) / 1048576:.1f} MB, "
          f"{len(doc['findings'])} findings, {shots} screenshots)")
    upload = {"title": f"Audit of {doc['site']}", "contentMimeType": DOCX_MIME,
              "base64Content": f"sha256:{digest}:{out}"}
    if folder:
        upload["parentId"] = folder
    print("Show this file to the user first: upload it only after they approve it in chat. "
          "Then call the Google Drive connector's create_file with exactly these arguments:")
    print(json.dumps(upload, indent=2))
    if not folder:
        print(f'(No "drive_folder_id" in {CONFIG}: the doc goes to the root of My Drive.)')


if __name__ == "__main__":
    main()
