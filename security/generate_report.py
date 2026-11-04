#!/usr/bin/env python3
"""Builds one human-readable HTML security report from the pipeline's scan results.

Inputs (all optional - a missing file is shown as "not run"):
  gitleaks-report.json   Gitleaks secrets scan
  trivy-report.json      Trivy container scan (HIGH + CRITICAL)
  .trivyignore           accepted risks
  nmap-app-report.xml    Nmap scan of the application port
  nmap-nodeports.gnmap   Nmap scan of the Kubernetes NodePort range
Output:
  security-report.html
Uses only the Python standard library.
"""
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime

OUT = "security-report.html"
OK, WARN, FAIL, NA = "PASS", "WARNING", "FAIL", "NOT RUN"
COLORS = {OK: "#1a7f37", WARN: "#9a6700", FAIL: "#cf222e", NA: "#57606a"}
SEV_COLORS = {"CRITICAL": "#cf222e", "HIGH": "#bc4c00", "MEDIUM": "#9a6700", "LOW": "#57606a"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "stops browsers from guessing content types (MIME sniffing)",
    "X-Frame-Options": "prevents the app from being embedded in another site (clickjacking)",
    "Content-Security-Policy": "limits where scripts and resources can be loaded from",
    "Referrer-Policy": "controls how much URL information is leaked to other sites",
}

e = lambda s: html.escape(str(s if s is not None else ""))


def badge(status):
    return f'<span style="background:{COLORS[status]};color:#fff;padding:2px 8px;border-radius:10px;font-weight:bold;font-size:12px">{status}</span>'


def sev(s):
    return f'<span style="color:{SEV_COLORS.get(s, "#000")};font-weight:bold">{e(s)}</span>'


def table(headers, rows):
    th = "".join(f'<th style="text-align:left;padding:6px 8px;background:#f6f8fa;border:1px solid #d0d7de">{h}</th>' for h in headers)
    trs = "".join("<tr>" + "".join(f'<td style="padding:6px 8px;border:1px solid #d0d7de;vertical-align:top">{c}</td>' for c in r) + "</tr>" for r in rows)
    return f'<table style="border-collapse:collapse;width:100%;font-size:13px;margin:8px 0">{"<tr>" + th + "</tr>"}{trs}</table>'


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---------- Gitleaks ----------
def gitleaks_section():
    data = load_json("gitleaks-report.json")
    if data is None:
        return NA, "Report not found (stage did not run).", "<p>The secrets scan did not run in this build.</p>"
    if not data:
        return OK, "No secrets found in the Git history.", "<p>Gitleaks scanned every commit of the repository and found <b>no passwords, tokens or keys</b>.</p>"
    rows = [[e(l.get("RuleID")), e(l.get("File")), e(l.get("StartLine")), e(str(l.get("Commit", ""))[:8]),
             e(l.get("Author")), e(l.get("Description"))] for l in data]
    body = ("<p><b>Secrets were found in the repository.</b> Each one must be revoked (changed at its source) "
            "and removed from the code. Values are redacted.</p>"
            + table(["Rule", "File", "Line", "Commit", "Author", "Description"], rows))
    return FAIL, f"{len(data)} secret(s) found.", body


# ---------- Trivy ----------
def accepted_risks():
    out = []
    try:
        with open(".trivyignore", encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\s*(CVE-[\d-]+)(?:\s+exp:(\S+))?", line)
                if m:
                    out.append((m.group(1), m.group(2) or "no expiry"))
    except OSError:
        pass
    return out


def trivy_section():
    data = load_json("trivy-report.json")
    if data is None:
        return NA, "Report not found (stage did not run).", "<p>The container scan did not run in this build.</p>"
    vulns = []
    for res in data.get("Results", []) or []:
        for v in res.get("Vulnerabilities", []) or []:
            vulns.append(v)
    order = {"CRITICAL": 0, "HIGH": 1}
    vulns.sort(key=lambda v: (order.get(v.get("Severity"), 9), v.get("PkgName", "")))
    crit = sum(1 for v in vulns if v.get("Severity") == "CRITICAL")
    high = sum(1 for v in vulns if v.get("Severity") == "HIGH")
    crit_fixable = sum(1 for v in vulns if v.get("Severity") == "CRITICAL" and v.get("FixedVersion"))
    status = FAIL if crit_fixable else (WARN if (crit or high) else OK)
    summary = f"{crit} critical, {high} high vulnerabilities."

    body = (f'<p>Image scanned: <b>{e(data.get("ArtifactName"))}</b>. '
            "The pipeline blocks the image only for <b>CRITICAL vulnerabilities that already have a fix</b>; "
            "HIGH findings are reported here so they can be planned.</p>")
    if not vulns:
        body += "<p>No HIGH or CRITICAL vulnerabilities found.</p>"
    else:
        # One line per library: what to upgrade, and why
        libs = {}
        for v in vulns:
            k = (v.get("PkgName"), v.get("InstalledVersion"))
            libs.setdefault(k, []).append(v)
        rows = []
        for (pkg, ver), vs in sorted(libs.items(), key=lambda kv: min(order.get(x.get("Severity"), 9) for x in kv[1])):
            worst = "CRITICAL" if any(x.get("Severity") == "CRITICAL" for x in vs) else "HIGH"
            fixes = sorted({f.strip() for x in vs for f in (x.get("FixedVersion") or "").split(",") if f.strip()})
            rows.append([e(pkg), e(ver), sev(worst), str(len(vs)), e(", ".join(fixes) or "no fix yet")])
        body += "<h4>What to upgrade (one line per library)</h4>" + table(
            ["Library", "Installed", "Worst severity", "Vulnerabilities", "Fixed in versions"], rows)
        rows = [[sev(v.get("Severity")), f'<a href="{e(v.get("PrimaryURL"))}">{e(v.get("VulnerabilityID"))}</a>',
                 e(v.get("PkgName")), e(v.get("InstalledVersion")), e(v.get("FixedVersion") or "no fix yet"), e(v.get("Title"))]
                for v in vulns]
        body += "<h4>All findings</h4>" + table(["Severity", "CVE", "Library", "Installed", "Fixed in", "Description"], rows)
    acc = accepted_risks()
    if acc:
        body += ("<h4>Accepted risks (.trivyignore)</h4><p>These are deliberately excluded from the scan, with a "
                 "written justification in <code>.trivyignore</code>. They come back automatically after the expiry date.</p>"
                 + table(["CVE", "Expires"], [[e(c), e(d)] for c, d in acc]))
    return status, summary, body


# ---------- Nmap ----------
def nodeports_part():
    allowed = os.environ.get("ALLOWED_NODEPORTS", "30080").split()
    try:
        with open("nmap-nodeports.gnmap", encoding="utf-8") as f:
            open_ports = sorted(set(re.findall(r"(\d+)/open", f.read())), key=int)
    except OSError:
        return NA, "", "<p>The NodePort exposure scan did not run.</p>"
    unexpected = [p for p in open_ports if p not in allowed]
    rows = [[e(p), "allowed" if p in allowed else '<b style="color:#cf222e">NOT ALLOWED</b>'] for p in open_ports]
    body = ("<h4>Ports exposed outside the cluster (NodePort range 30000-32767)</h4>"
            f"<p>Allowlist: <b>{e(' '.join(allowed))}</b>. Any other open port means a service is reachable from outside "
            "the cluster without being approved.</p>" + (table(["Port", "Status"], rows) if rows else "<p>No open ports.</p>"))
    return (FAIL if unexpected else OK), (f"unexpected open port(s): {', '.join(unexpected)}" if unexpected else
                                          f"only allowed ports open ({', '.join(open_ports) or 'none'})"), body


def nmap_section():
    np_status, np_summary, np_body = nodeports_part()
    try:
        root = ET.parse("nmap-app-report.xml").getroot()
    except (OSError, ET.ParseError):
        return np_status, np_summary or "Report not found (stage did not run).", np_body
    body, findings = "", []
    for port in root.iter("port"):
        state = port.find("state").get("state") if port.find("state") is not None else "?"
        body += f'<h4>Application port {e(port.get("portid"))}/{e(port.get("protocol"))}: {e(state)}</h4>'
        scripts = {s.get("id"): (s.get("output") or "").strip() for s in port.findall("script")}

        headers = scripts.get("http-headers", "")
        if headers:
            present = {h.split(":", 1)[0].strip().lower() for h in headers.splitlines() if ":" in h}
            rows = []
            for h, why in SECURITY_HEADERS.items():
                ok = h.lower() in present
                rows.append([e(h), '<span style="color:#1a7f37">present</span>' if ok else '<b style="color:#9a6700">missing</b>', e(why)])
                if not ok:
                    findings.append(f"missing header {h}")
            body += "<p><b>HTTP security headers</b> (checked on the app's health endpoint):</p>" + table(["Header", "Status", "Purpose"], rows)
            server = re.search(r"^\s*Server:\s*(.+)$", headers, re.M)
            if server:
                findings.append("server version disclosed")
                body += f'<p>The <code>Server</code> header reveals: <b>{e(server.group(1))}</b> (information useful to an attacker).</p>'
        else:
            body += "<p>HTTP headers check: no result.</p>"

        methods = scripts.get("http-methods", "")
        if methods:
            risky = re.search(r"Potentially risky methods:\s*(.+)", methods)
            if risky:
                findings.append(f"risky HTTP methods: {risky.group(1).strip()}")
            body += (f'<p><b>HTTP methods</b> accepted on <code>/student/</code>: {e(methods.splitlines()[0])}'
                     + (f'<br><b style="color:#9a6700">Potentially risky: {e(risky.group(1).strip())}</b>' if risky else "") + "</p>")
        title = scripts.get("http-title")
        if title:
            body += f"<p><b>Page title</b> of the Swagger UI: {e(title)}</p>"

    status = np_status if np_status == FAIL else (WARN if findings else OK)
    summary = "; ".join(filter(None, [np_summary, ", ".join(findings)])) or "no issues found"
    intro = "<p>Nmap scans the <b>deployed</b> application from the network, the way an attacker would see it.</p>"
    return status, summary, intro + np_body + body


# ---------- Page ----------
def main():
    checks = [
        ("Secrets in Git history", "Gitleaks", *gitleaks_section()),
        ("Container vulnerabilities", "Trivy", *trivy_section()),
        ("Network exposure &amp; HTTP security", "Nmap", *nmap_section()),
    ]
    result = os.environ.get("BUILD_RESULT", "UNKNOWN")
    build = f'{e(os.environ.get("JOB_NAME", "local"))} #{e(os.environ.get("BUILD_NUMBER", "-"))}'
    url = os.environ.get("BUILD_URL", "")
    res_color = {"SUCCESS": COLORS[OK], "FAILURE": COLORS[FAIL]}.get(result, COLORS[WARN])

    summary_rows = [[f"<b>{name}</b>", e(tool), badge(st), e(sm)] for name, tool, st, sm, _ in checks]
    sections = "".join(f'<h2 style="border-bottom:1px solid #d0d7de;padding-bottom:4px">{name} ({e(tool)}) {badge(st)}</h2>{body}'
                       for name, tool, st, sm, body in checks)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Security report - {build}</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;color:#1f2328;max-width:1000px;margin:auto;padding:16px">
<h1 style="margin-bottom:4px">DevSecOps security report</h1>
<p style="margin-top:0">Build <b>{build}</b> &middot; result: <b style="color:{res_color}">{e(result)}</b>
&middot; {datetime.now().strftime("%Y-%m-%d %H:%M")}{f' &middot; <a href="{e(url)}console">console output</a>' if url else ''}</p>
<h2>Summary</h2>
{table(["Check", "Tool", "Status", "Details"], summary_rows)}
<p style="font-size:12px;color:#57606a">PASS: no issue &middot; WARNING: issues to plan, not blocking &middot;
FAIL: blocking issue &middot; NOT RUN: the stage did not run (an earlier stage failed).</p>
{sections}
</body></html>"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()