#!/usr/bin/env python3
"""Regenerates aimomnivoice/templates/dashboard-cfg.yaml deterministically.

Sources (single source of truth):
  patch/web/nginx.conf   -- nginx config (Helm template, kept verbatim)
  patch/web/index.html   -- dashboard HTML (contains /*__FONTS__*/ placeholder)
  patch/web/fonts/*.woff2 -- Geist variable fonts, embedded as base64 @font-face
                             (self-hosted: no external requests at runtime)

Output:
  aimomnivoice/templates/dashboard-cfg.yaml
    ConfigMap "aimomnivoice-dashboard" with keys nginx.conf + index.html
    (4-space literal block scalars).

Usage: python3 patch/gen_dashboard_cfg.py
"""
import base64
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent  # .../aimomnivoice
WEB = ROOT / "patch" / "web"
OUT = ROOT / "aimomnivoice" / "templates" / "dashboard-cfg.yaml"

FONTS = [
    ("'Geist'", "fonts/Geist-Variable.woff2"),
    ("'Geist Mono'", "fonts/GeistMono-Variable.woff2"),
]

CHUNK = 8000  # chars per line -- must stay far below the 64 KB linter line limit


def b64_chunks(data: bytes) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return ",\n".join(
        '"%s"' % b64[i:i + CHUNK] for i in range(0, len(b64), CHUNK)
    )


def font_script() -> str:
    """Self-hosted fonts: base64 chunk arrays, injected as @font-face at runtime.
    No external requests (design guide: selbst gehostet, kein Nachladen)."""
    arrays = []
    for family, rel in FONTS:
        arrays.append("var F_%s=[\n%s\n]" % (family.strip("'").replace(" ", "_"),
                                             b64_chunks((WEB / rel).read_bytes())))
    return (
        "<script>\n"
        + "\n".join(arrays)
        + "\n;(function(){\n"
        "function inj(n,b){var c=\"@font-face{font-family:\"+n+\";font-style:normal;\"\n"
        "+\"font-weight:100 900;font-display:swap;src:url(data:font/woff2;base64,\"\n"
        "+b+\") format('woff2')}\";var s=document.createElement('style');\n"
        "s.textContent=c;document.head.appendChild(s);}\n"
        "inj('Geist',F_Geist.join(''));inj('Geist Mono',F_Geist_Mono.join(''));\n"
        "})();\n</script>"
    )


def indent(text: str, n: int = 4) -> str:
    pad = " " * n
    return "\n".join((pad + line) if line else "" for line in text.splitlines())


def main() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    if "/*__FONTS__*/" not in html:
        raise SystemExit("placeholder /*__FONTS__*/ missing in index.html")
    html = html.replace("/*__FONTS__*/", font_script())
    nginx = (WEB / "nginx.conf").read_text(encoding="utf-8")

    parts = [
        "---",
        "apiVersion: v1",
        "kind: ConfigMap",
        "metadata:",
        "  name: aimomnivoice-dashboard",
        "  namespace: {{ .Release.Namespace }}",
        "data:",
        "  nginx.conf: |",
        indent(nginx),
        "  index.html: |",
        indent(html),
        "",
    ]
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print("wrote %s (%d bytes)" % (OUT, OUT.stat().st_size))


if __name__ == "__main__":
    main()
