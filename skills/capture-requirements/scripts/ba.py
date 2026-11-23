#!/usr/bin/env python3
"""ba: the BA skills helper. Standard library only. One file.

This file is built. Its source is the modules in helper/src/, joined in the order tools/build.py states;
each part below starts with a banner naming its module (ADR 0027). Edit a module, then run
`python3 tools/build.py`. Never edit this file or the copies in skills/*/scripts/.

It finds its own files from its own path (HERE), never from the current folder.
Reading records is find_workspace, read_workspace and read_store; a store is described in records.
"""
import argparse
import datetime
import difflib
import hashlib
import os
import re
import shlex
import shutil
import sys
import tempfile
import time
import traceback
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))


# ==== helper/src/findings.py ================================================
"""Findings: the catalogue of kinds, how a finding is worded, and how this run was started.

Owns CATALOGUE (ADR 0019), the command strings a fix may quote (BA, CHECK, BUNDLE, FOLDER, set by main), and
_problem, which words one finding from the catalogue.
Must not know: what a record, a brief or a baseline is. It sees a record only as a dict with file, kind and name.
"""

# The kinds of finding (ADR 0019). One table; lint counts the keys. Budget: 12 in all,
# 8 for records and 4 held back for the lints on faces, which join this table with `ba bundle`.
# Each entry is (level, message, fix). The {names} are filled from what the parser found.
# {check} and {fixcmd} are the commands as this run was started, so a skill's path is kept.
# Exit code 0 whatever is found: findings are advice (ADR 0019).
CATALOGUE = {
    # A line, heading or record that is needed and not there.
    "missing": ("finding", "There is no {what}.", "In {file}, add {at}: {add}"),
    # A value outside what the line takes, or a name that points at nothing.
    "bad-value": ("finding", "'{key}' is '{value}'. {why}", "In {file}, change {where} to: {write}"),
    # Two readings and no way to pick: reported with two options, never resolved by the tool.
    "ambiguous": ("finding", "{what} ba will not choose between them.", "Option 1: {one} Option 2: {two} Then run: {check}"),
    # Lines that are in the file but are not read as the records they look like.
    "not-read": ("finding", "{what}", "{how}"),
    # A line, key or sub-heading ba does not use. Kept as written.
    "hand-edit": ("info", "{count} line(s) here are not ones a {kind} uses (lines {lines}). They are kept as written.",
                  "{renamed}{nothing} ba keeps them and --fix never changes them. If one was meant as a field, "
                  "write it '- Key: value' with a key from: {keys}."),
    # An optional line that is worth having and is not there. Never a finding.
    "not-given": ("info", "'{key}' is not given.",
                  "If {unknown} is not known, leave the line out; do not write a placeholder. If it is: in {file}, "
                  "add after line {after}: {add}"),
    # Something made or said before what it rests on changed: a brief or an approval of earlier records
    # (the two versions are named), or a brief's approval table made before an approval was recorded; and a
    # defect called against a requirement that is still a draft: a verdict said before what it rests on is agreed.
    "stale": ("info", "{what}{versions}.", "{how}"),
    # Confirmed records that carry a handle or no ID: advice to run --fix. Drafts are not mentioned.
    "no-id": ("info", "{count} confirmed record(s) have a handle or no ID, the first at line {first}.",
              "Run: {fixcmd}   It assigns the IDs and writes a backup first."),
}
# How to run check, as this run was started: main() sets these from the path and folder it was given.
BA = "python3 ba.py"
CHECK = "python3 ba.py check"
BUNDLE = "python3 ba.py bundle signoff"
FOLDER = ""


def _problem(code, record, line, **params):
    """One problem, worded from the catalogue.

    code     a key of CATALOGUE
    level    "finding" (something to fix) or "info" (kept, worth knowing)
    file, line, kind, name   where it is; kind and name are '' outside a record
    message  one plain line; fix  what to do about it, ending the finding
    params   what the wording used, kept for callers: key, value, allowed, lines, first
    """
    level, message, fix = CATALOGUE[code]
    p = {"code": code, "level": level, "file": record["file"], "line": line,
         "kind": record.get("kind", ""), "name": record.get("name", "")}
    p.update(params)
    text = {k: ", ".join(str(x) for x in v) if isinstance(v, list) else v for k, v in p.items()}
    text.setdefault("check", CHECK + FOLDER)  # `check --adopt` says its own
    text.setdefault("fixcmd", _fixcmd())
    text["file"] = p.get("fixfile", p["file"])  # a fix may be an edit to another file than the finding's
    text.setdefault("unknown", "the name")
    text.setdefault("where", "line %s" % line)
    text.setdefault("renamed", "")
    text.setdefault("nothing", "Nothing to do.")
    text.setdefault("versions", " (version %s then, %s now)" % (p["old"], p["new"]) if "old" in p else "")
    p["message"] = message.format(**text)
    p["fix"] = p.get("says") or fix.format(**text)  # `says`: the fix as the ADR words it, for a case the catalogue's sentence does not fit
    return p


def _fixcmd():
    return CHECK + " --fix" + FOLDER


def _show(problems):
    """Findings as check shows them, for a command that is not check."""
    out = []
    for p in problems:
        out += ["  %s line %d: %s: %s" % (p["file"], p["line"], p["level"], p["message"]), "    Fix: " + p["fix"]]
    return out


# ==== helper/src/records.py =================================================
"""Records: the grammar of work.md and the parser that reads it (ADR 0011, 0017).

A store is a dict:

  folder    the workspace folder, or None
  files     {file name: [line, ...]}. Lines keep their endings, so "".join(lines)
            is the file byte for byte. Every "line" number is 1-based into this
            list; a writer changes lines[n - 1] and nothing else moves.
  records   one dict per record, in reading order (see _new_record)
  problems  one dict per problem, in reading order (see _problem)

The parser never drops a line. A line it does not understand stays in `files`
and is listed in its record's "other".

Owns the tables of kinds and fields, _parse_file, and the small readers of a record (value, status_of,
feature_named, to_deliver). Must not know: folders on disk (workspace), cross-record checks (validate),
or anything about briefs and baselines.
"""

# ---------------------------------------------------------------------------
# The record grammar (ADR 0011). Keys are held lower-case.
# ---------------------------------------------------------------------------

# The sixth kind, Observed (ADR 0035), is written only when material says what something does today: `check --shape all`
# and the first capture's examples stay the first five.
KINDS = ("work", "requirement", "question", "flow", "feature", "observed")
FIRST_FIVE = KINDS[:5]
ID_LETTER = {"work": "W", "requirement": "R", "question": "Q", "flow": "F", "feature": "FE", "observed": "OB"}
VERDICTS = ("intended", "accidental", "defect")
SIGNALS = ("more than one approver", "more than one team", "regulation or contract",
           "data from an old system")
# The fifth yes or no line of the Work (ADR 0032): the goal needs several features, scoped and forecast together.
# It is not one of SIGNALS: it makes a Work Large, and the four make it Medium.
SEVERAL = "several features"
FIELDS = {
    "work": ("id", "status", "withdrawn because", "goal", "tracker", "house", "home", "sign-off form", "approvers") + SIGNALS + (SEVERAL,),
    "requirement": ("id", "category", "feature", "status", "withdrawn because", "priority", "priority notes", "statement", "source",
                    "why", "measure", "threshold"),
    "question": ("id", "raised by", "raised", "asked", "context", "about", "answer", "answered by", "working answer", "owner"),
    "flow": ("id", "status", "withdrawn because", "source", "overview", "trigger"),
    "feature": ("id", "status", "withdrawn because", "intent", "sliced from", "flow", "tracker", "business item"),
    "observed": ("id", "behaviour", "seen in", "raised by", "raised", "about", "owner", "verdict", "verdict by", "requirement",
                 "status", "withdrawn because"),
}
REQUIRED = {"work": (), "requirement": ("statement", "source"), "question": (), "flow": (), "feature": (),
            "observed": ("behaviour", "seen in")}
# Lines that are optional, and worth a note when they are missing (information, never a finding).
# A Question that has a working answer and no answer is an assumption, and its owner is worth asking for.
# A Question with no `Raised by` draws nothing: one a skill writes for itself has nobody who raised it.
ASKED = {"feature": ("intent",)}
# The two lines ADR 0021 renamed. Only the note about an unknown line reads this, to name the line to write.
RENAMED = {("work", "outcome"): "goal", ("requirement", "type"): "category"}
STEP_FIELDS = ("description", "inputs", "outputs", "stakeholders", "tools")
FIXED = {
    "status": ("draft", "confirmed", "withdrawn"),
    "priority": ("must", "should", "could", "wont"),
    "verdict": VERDICTS,
}
FIXED.update((signal, ("yes", "no")) for signal in SIGNALS + (SEVERAL,))
MARKS = ("said", "proposed")
# The Work's list sections that the records version leaves out (ADR 0011, 0031, 0038): what was agreed is not changed by them.
# Destinations say where the Work's pages go, and linked documents are another team's: neither says what was agreed.
LEFT_OUT = ("approvals", "published", "delivery", "actuals", "destinations", "linked documents")
# Which list sub-headings belong to which kind. "### Step: <name>" belongs to a flow.
LISTS = {"examples": "requirement", "people": "work", "assumptions": "work", "out of scope": "work",
         "approvals": "work", "published": "work", "glossary": "work", "stakeholders": "work", "tolerances": "work",
         "delivery": "work", "actuals": "work", "destinations": "work", "linked documents": "work",
         "left to engineering": "requirement", "flow steps": "feature"}

_RECORD = re.compile(r"^##\s+([A-Za-z]+)\s*:\s*(.*)$")
_SUB = re.compile(r"^###\s+(.*)$")
_STEP = re.compile(r"^step\s*:\s*(.*)$", re.I)
_BULLET = re.compile(r"^[-*+]\s+(.*)$")
_KEY = re.compile(r"^(?:[-*+]\s+)?(?:\*\*)?([A-Za-z][A-Za-z -]*?)(?:\*\*)?\s*:(?:\*\*)?\s*(.*)$")
# A Go to may end in a condition in brackets, with or without the word "when".
_WHEN = re.compile(r"^(.*?)\s*\((?:when\s+)?(.*)\)$", re.I)
_ASSIGNED = re.compile(r"^(W|R|Q|F|FE|OB)-\d+$")
_RULE = re.compile(r"^([-*_])(\s*\1){2,}$")  # a horizontal rule: ---, ***, ___, - - -
_APPROVAL = re.compile(r"^(?P<name>[^:]+?)\s*:\s*(?P<decision>approved|changes asked)\s*,\s*(?P<date>.+?)\s*,\s*"
                       r"(?:records version\s+(?P<version>[^,\s]+)(?:\s*,\s*baseline\s+(?P<its>[^,\s]+))?|"
                       r"baseline\s+(?P<baseline>[^,\s]+)(?:\s*,\s*records version\s+[^,\s]+)?)"  # both: the baseline is what was approved
                       r"\s*(?:,\s*[\"\u201c](?P<words>.*?)[\"\u201d])?\s*$", re.I)
# One sending, as the note gives it (ADR 0026): the signoff is a page, a handover or business brief is an item.
_PUBLISHED = re.compile(
    r"^(?P<face>signoff|scope|delivery|(?:handover|business)\s+\S+)\s*:\s*(?:page\s+(?P<page>\d+)\s*,\s*version\s+(?P<version>\d+)|"
    r"item\s+(?P<item>[A-Za-z][A-Za-z0-9]*-\d+))\s*,\s*(?P<date>[^,]+?)\s*,\s*"
    r"(?P<from>records version\s+[0-9a-f]{8}|baseline\s+[A-Za-z0-9][A-Za-z0-9._-]*)\s*,\s*(?P<link>https?://\S+)\s*$", re.I)
PUBLISHED_FORM = "- signoff: page <ID>, version <number>, <date>, records version <8 characters>, <link>   (scope and delivery are " \
                 "written the same way, with their own name in place of signoff)   or   " \
                 "- handover <Feature ID>: item <key>, <date>, records version <8 characters> (or baseline <name>), <link>"
_NO_FEATURE = re.compile(r"^none\s*(?:\((.*)\))?$", re.I)
# A handle: lower-case words joined by hyphens, or an ID's letters and a hyphen before words that are not a number
# (`Q-goal`): the person meant an ID and the number was never given.
_HANDLE = re.compile(r"^(?:(?:W|R|Q|F|FE|OB)-(?!\d+$)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*|[a-z][a-z0-9]*(?:-[a-z0-9]+)*)$")
# A line ends at LF, CRLF or CR only, as an editor counts them. str.splitlines also
# breaks at form feeds and U+2028, which arrive in pasted text and would shift every number.
_LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+")




def label(key):
    """A key as the shipped examples write it: 'raised by' -> 'Raised by'."""
    return "ID" if key == "id" else key[:1].upper() + key[1:]


def value(record, key):
    """The value of a field of a record or step, or '' when it is absent."""
    field = record["fields"].get(key)
    return field["value"] if field else ""


def status_of(record):
    """A record's status. One with no Status line is a draft (blueprint section 4, ADR 0011)."""
    return value(record, "status") or "draft"


def standing_of(record):
    """An Observed record's standing (ADR 0035): withdrawn; else its verdict; else unconfirmed. It is never a draft and
    never confirmed: those are the analyst agreeing a record says the right thing, which is not a verdict."""
    if value(record, "status") == "withdrawn":
        return "withdrawn"
    return value(record, "verdict") if value(record, "verdict") in VERDICTS else "unconfirmed"


def _new_record(kind, name, file, line):
    return {
        "kind": kind,          # one of KINDS
        "name": name,
        "id": "",              # the ID line's value: an assigned ID, a handle, or ''
        "file": file,
        "line": line,          # the "## Kind: name" line
        "end": line,           # the last line of the block
        "fields": {},          # {key: {"key": as written, "value": str, "line": n}}
        "empty": {},           # {key: line} for known keys written with no value
        "about": [],           # Question: the IDs and handles on its About line
        "examples": [],        # Requirement: [{"mark", "text", "line"}]
        "people": [],          # Work: [{"role", "name", "line"}]
        "approvals": [],       # Work: [{"name", "decision", "date", "version", "baseline", "words", "line"}]
        "approvals span": None,  # Work: (first, last) line of the ### Approvals section, which the version leaves out
        "published": [],       # Work: [{"face", "page", "version", "item", "date", "from", "link", "line"}]
        "published span": None,  # Work: (first, last) line of the ### Published section, which the version leaves out
        "stakeholders": [],    # Work: [{"text", "line"}]: `<name>: <their say>, <what they need>`
        "tolerances": [],      # Work: [{"text", "line"}]
        "delivery": [],        # Work: [{"text", "line"}]: the forecast's inputs (ADR 0031)
        "delivery span": None,  # Work: (first, last) line of the ### Delivery section, which the version leaves out
        "actuals": [],         # Work: [{"text", "line"}]: what has finished and started
        "actuals span": None,  # Work: (first, last) line of the ### Actuals section, which the version leaves out
        "destinations": [],    # Work: [{"text", "line"}]: where its pages go (ADR 0038)
        "destinations span": None,  # Work: (first, last) line of the ### Destinations section, which the version leaves out
        "linked documents": [],  # Work: [{"text", "line"}]: documents another team keeps
        "linked documents span": None,  # Work: (first, last) line of the ### Linked documents section, which the version leaves out
        "assumptions": [],     # Work: [{"text", "line"}]
        "out of scope": [],    # Work: [{"text", "line"}]
        "glossary": [],        # Work: [{"word", "meaning", "line"}]
        "left to engineering": [],  # Requirement: [{"text", "line"}]
        "flow steps": [],      # Feature: [{"text", "line"}]: names of steps in the feature's flows
        "flows": [],           # Feature: the IDs and handles on its Flow line
        "steps": [],           # Flow: [{"name", "line", "fields", "empty", "go to"}]
        "other": [],           # [{"line", "text"}]: lines kept but not understood
    }



_FENCE = re.compile(r"^(```|~~~)")
PLACEHOLDER = {
    "statement": "As a <who> I want <what> so that <why>",
    "source": "<who said it, and when>",
    "raised by": "<name>",
    "owner": "<name>",
    "behaviour": "<what happens, and to whom, in the business's own words>",
    "seen in": "<where it was seen: the document and page, or the file and lines>",
    "description": "<what happens in this step>",
    "intent": "<what a named person can do or see once this is built>",
}
HEADINGS = ("'## Work: <name>', '## Requirement: <name>', '## Question: <name>', '## Flow: <name>', "
            "'## Feature: <name>' or '## Observed: <name>'")


def _keep(rec, n, raw, reported=False):
    """Keep a line the parser does not use. `reported` means a finding already names it."""
    rec["other"].append({"line": n, "text": raw.rstrip("\r\n"), "reported": reported})


def _record_heading(line, file, n, records, problems):
    """A '## ' line: starts a record (returned), or is a finding and returns None."""
    m = _RECORD.match(line)
    if m and m.group(1).lower() in KINDS:
        rec = _new_record(m.group(1).lower(), m.group(2).strip(), file, n)
        records.append(rec)
        return rec
    problems.append(_problem(
        "not-read", {"file": file}, n, value=line,
        what="'%s' does not start a record, so it and the lines under it are not read." % line,
        how="If it is a record, change line %d to one of %s. If it is a note, delete the line or "
            "write it inside <!-- and -->." % (n, HEADINGS)))
    return None


def _sub_heading(rec, line, raw, n, problems):
    """A '### ' line inside a record. Returns (step or None, the section that now applies)."""
    m = _SUB.match(line)
    title = m.group(1).strip()
    sm = _STEP.match(title)
    if sm and rec["kind"] == "flow":
        step = {"name": sm.group(1).strip(), "line": n, "fields": {}, "empty": {}, "go to": []}
        rec["steps"].append(step)
        return step, "step"
    if LISTS.get(title.lower()) == rec["kind"]:
        if title.lower() in LEFT_OUT:
            rec[title.lower() + " span"] = [n, n]
        return None, title.lower()
    if _RECORD.match("## " + title) and title.split(":")[0].strip().lower() in KINDS:
        _keep(rec, n, raw, reported=True)
        problems.append(_problem(
            "not-read", rec, n, value=line,
            what="'%s' has three hashes, so it and the lines under it are read as part of this %s."
                 % (line, rec["kind"]),
            how="To start a record, change line %d to '## %s'." % (n, title)))
        return None, "hidden"
    _keep(rec, n, raw)
    return None, "unknown"


def _list_line(rec, section, line, n, raw, problems):
    """A line under '### Examples', '### People', '### Assumptions' or '### Out of scope'."""
    b = _BULLET.match(line)
    if not b and section == "actuals":  # a line that is not read must never be shown as a feature that has not started
        _keep(rec, n, raw, reported=True)
        problems.append(_problem("bad-value", rec, n, key="Actuals", value=line, allowed=[],
                                 why="A line of this list starts with '- ', so this one is not read.", write="- " + line))
        return
    if not b:
        _keep(rec, n, raw)
        return
    item = b.group(1).strip()
    if section == "glossary":
        word, colon, meaning = item.partition(":")
        if colon and word.strip() and meaning.strip():
            rec["glossary"].append({"word": word.strip(), "meaning": meaning.strip(), "line": n})
        else:
            _keep(rec, n, raw)
    elif section == "examples":
        k = _KEY.match(line)
        if k and k.group(1).lower() in MARKS and k.group(2).strip():
            rec["examples"].append({"mark": k.group(1).lower(), "text": k.group(2).strip(), "line": n})
        else:
            _keep(rec, n, raw, reported=True)
            problems.append(_problem(
                "bad-value", rec, n, key="Example", value=item, allowed=list(MARKS),
                why="An example says who gave it.",
                write="- said: <what the person gave> (or '- proposed: <text>' if you suggested it)"))
    elif section == "approvals":
        m = _APPROVAL.match(item)
        if m:
            rec["approvals"].append({"name": m.group("name").strip(), "decision": m.group("decision").lower(),
                                     "date": m.group("date"),
                                     "version": "" if m.group("its") else (m.group("version") or "").lower(),
                                     "baseline": m.group("baseline") or m.group("its") or "", "words": m.group("words") or "", "line": n})
        else:
            _keep(rec, n, raw)
    elif section == "published":
        m = _PUBLISHED.match(item)
        face = m.group("face").lower() if m else ""
        if m and (face in ("signoff", "scope", "delivery")) == bool(m.group("page")):
            rec["published"].append({"face": " ".join(m.group("face").split()), "page": m.group("page") or "",
                                     "version": m.group("version") or "", "item": m.group("item") or "",
                                     "date": m.group("date"), "from": " ".join(m.group("from").split()), "link": m.group("link"),
                                     "line": n})
        else:
            _keep(rec, n, raw, reported=True)
            problems.append(_problem(
                "bad-value", rec, n, key="Published", value=item, allowed=[],
                why="A sending is written as the note gave it, with each value filled in from the tool's reply.",
                write=PUBLISHED_FORM))
    elif section == "people":
        role, colon, who = item.partition(":")
        role, who = role.strip().strip("*").strip(), who.strip().strip("*").strip()
        if colon and role and who:
            rec["people"].append({"role": role, "name": who, "line": n})
        else:
            _keep(rec, n, raw)
    else:
        rec[section].append({"text": item, "line": n})


def _field_line(rec, step, section, line, n, raw, problems):
    """A '- Key: value' line of a record or of its current step."""
    k = _KEY.match(line)
    if not k:
        _keep(rec, n, raw)
        return
    key, val = " ".join(k.group(1).lower().split()), k.group(2).strip()
    target = step if section == "step" else rec
    if section == "step" and key == "go to":
        if val:
            w = _WHEN.match(val)
            step["go to"].append({"to": w.group(1) if w else val, "when": w.group(2).strip() if w else "",
                                  "text": val, "line": n})
        else:
            step["empty"]["go to"] = n
        return
    if key not in (STEP_FIELDS if section == "step" else FIELDS[rec["kind"]]):
        _keep(rec, n, raw)
        return
    if not val:
        target["empty"][key] = n
        return
    if key in target["fields"]:
        first = target["fields"][key]["line"]
        problems.append(_problem(
            "ambiguous", rec, n, key=label(key), lines=[first, n],
            what="'%s' is written twice, on lines %d and %d." % (label(key), first, n),
            one="keep line %d and delete line %d." % (first, n),
            two="keep line %d and delete line %d." % (n, first)))
        return
    target["fields"][key] = {"key": k.group(1), "value": val.lower() if key in FIXED else val, "line": n}


def _parse_file(file, lines, records, problems):
    rec = step = None
    section = None  # None: the record's own fields. Else a LISTS key, "step", "unknown" or "hidden".
    in_comment, comment_line = False, 0
    fence, fence_line = "", 0
    span = None  # the open ### Approvals section: the Work's list [first, last]

    for n, raw in enumerate(lines, 1):
        line = raw.strip().lstrip("\ufeff")
        if rec:
            rec["end"] = n
        if in_comment or (not fence and line.startswith("<!--")):
            if not in_comment:
                comment_line = n
            in_comment = "-->" not in line
            continue
        if fence or _FENCE.match(line):
            # Inside a code fence nothing starts a record. The lines are kept with their record.
            if not fence:
                fence, fence_line = line[:3], n
            elif line.startswith(fence):
                fence = ""
            if rec:
                _keep(rec, n, raw)
            continue
        if not line or _RULE.match(line):
            continue
        if span and (line.startswith("##") and not line.startswith("####")):
            span[1], span = n - 1, None
        if line == "##" or line.startswith("## "):
            if rec:
                rec["end"] = n - 1
            step, section = None, None
            rec = _record_heading(line, file, n, records, problems)
        elif rec is None:
            continue  # before the first record, or under a heading that is not a record
        elif _SUB.match(line):
            step, section = _sub_heading(rec, line, raw, n, problems)
            if section in LEFT_OUT:
                span = rec[section + " span"]
        elif section in ("unknown", "hidden"):
            _keep(rec, n, raw, reported=section == "hidden")
        elif section in LISTS:
            _list_line(rec, section, line, n, raw, problems)
        else:
            _field_line(rec, step, section, line, n, raw, problems)

    if span:
        span[1] = len(lines)
    if in_comment:
        problems.append(_problem(
            "not-read", rec or {"file": file}, comment_line,
            what="The comment that opens on line %d never closes, so nothing after it is read." % comment_line,
            how="Close it: add --> at the end of the line where the comment should stop."))
    if fence:
        problems.append(_problem(
            "not-read", rec or {"file": file}, fence_line,
            what="The code fence that opens on line %d never closes, so no record after it is read." % fence_line,
            how="Close it: add a line holding only %s where the fence should stop." % fence))


def _names(items):
    return ", ".join(items)


def _parts(text):
    """A value that lists names: split at commas, each part trimmed, empty parts dropped."""
    return [x.strip() for x in text.split(",") if x.strip()]


def feature_named(records, part):
    """The Feature record a part of a `Feature` line, a `Sliced from` line or a command names, or None (ADR 0024).
    By ID or handle, ignoring case; else by name, ignoring case and outer spaces, the one that is not
    withdrawn if there is one, else the withdrawn one. The one rule for naming a feature."""
    part = part.strip().lower()
    features = [r for r in records if r["kind"] == "feature"]
    for r in features:
        if r["id"] and r["id"].lower() == part:
            return r
    same = [r for r in features if r["name"].strip().lower() == part]
    return next((r for r in same if status_of(r) != "withdrawn"), same[0] if same else None)


def _parts_of(store, feature):
    """The Features sliced from this one: those whose `Sliced from` line names it."""
    return [x for x in store["records"] if x["kind"] == "feature" and x is not feature and _parts(value(x, "sliced from"))
            and feature_named(store["records"], _parts(value(x, "sliced from"))[0]) is feature]


def kept_original(store, feature):
    """True for a Feature that is not withdrawn and that another Feature, not withdrawn, names on `Sliced from` (ADR 0038): a
    sliced Feature left standing because work is logged against its tracker item. It is not counted as a Feature, has no
    brief, and its parts carry the requirements. The one definition."""
    return status_of(feature) != "withdrawn" and any(status_of(p) != "withdrawn" for p in _parts_of(store, feature))


def live_features(store):
    """The Features that are not withdrawn and not a kept original, in store order: what counts as a Feature."""
    return [r for r in store["records"] if r["kind"] == "feature" and status_of(r) != "withdrawn" and not kept_original(store, r)]


def left_out_of_features(req):
    """None, or the reason ('' when none is given) when the requirement's `Feature` line says it is deliberately in no
    feature: `- Feature: none`, or `- Feature: none (handled by the office by hand)` (ADR 0024)."""
    m = _NO_FEATURE.match(value(req, "feature").strip())
    return None if not m else (m.group(1) or "").strip()


def feature_parts(req):
    """The parts of a requirement's `Feature` line that each name a Feature: none when the line says `none`."""
    return [] if left_out_of_features(req) is not None else _parts(value(req, "feature"))


def to_deliver(store):
    """The requirements the work must deliver: confirmed, and not 'wont' (ADR 0024). The one definition;
    check, status and the ADRs use it. A baseline's 'in scope' is a different thing."""
    return [r for r in store["records"] if r["kind"] == "requirement" and status_of(r) == "confirmed"
            and value(r, "priority") != "wont"]


# ==== helper/src/forecast.py ================================================
"""Forecast: the figures of the Delivery plan, worked out from the Work's `### Delivery` and `### Actuals` (ADR 0031).

Owns the reading of the two sections and the arithmetic: whole days and exact fractions (Fraction), a Feature counted
as one, every date shown the Friday of its week. forecast_of takes the two lists of lines and the Features, reads
nothing else (no clock, no network, no file) and writes nothing; forecast_for is the one call that finds those in a
store. Must not know: how a figure is laid out in a brief (blocks), how a problem is worded (check), or what a
Feature record holds beyond being one.
"""

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_NUMBER = re.compile(r"^(\d+)(?:\.(\d{1,2}))?$")
_RANGE = re.compile(r"^(\S+)\s+to\s+(\S+)$", re.I)
_WEEKS = re.compile(r"^(\d+)\s+weeks?$", re.I)
_ITEMS_DONE = re.compile(r"^(\d+)\s+of\s+(\d+)\s+items\s+done$", re.I)
_DATED = re.compile(r"^(started|finished)\s+(\S+)$", re.I)
# The forms a line is written in, as a fix gives them.
START_FORM = "- Start: <YYYY-MM-DD>"
PERIOD_FORM = "- Period: <a whole number from 1> weeks"
VELOCITY_FORM = "- Velocity: <low> to <high>"
READ_FORM = "- Read: <YYYY-MM-DD>, <where it was read from, and by whom>"
ACTUAL_FORM = "- <a Feature>: started <YYYY-MM-DD>, finished <YYYY-MM-DD>, <d> of <t> items done"


def show_date(day):
    """A date as a table shows it: `8 May 2026`."""
    return "%d %s %d" % (day.day, MONTHS[day.month - 1], day.year)


def friday_of(day):
    """The Friday of the week (Monday to Sunday) a day falls in."""
    return day + datetime.timedelta(days=4 - day.weekday())


def _date(text):
    """A `YYYY-MM-DD` as a date, or None when it is not one."""
    m = _ISO_DATE.match(text.strip())
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    except ValueError:
        return None


def _number(text):
    """A number above 0 with at most two decimal places, as a Fraction, or None."""
    m = _NUMBER.match(text.strip())
    if not m:
        return None
    n = Fraction(int(m.group(1)) * 100 + int((m.group(2) or "0").ljust(2, "0")), 100)
    return n if n > 0 else None


def _ceil(n):
    return -(-n.numerator // n.denominator)


def _issue(code, section, line, **more):
    more.update(code=code, section=section, line=line)
    return more


def _read_delivery(items, live, named, issues):
    """The `### Delivery` lines: ({key: value}, the Features named by Order, their lines)."""
    got, order = {}, []
    for item in items:
        key, _, val = item["text"].partition(":")
        key = " ".join(key.lower().split())
        if key in ("start", "period", "velocity", "order") and key not in got:
            got[key] = (val.strip(), item["line"])
    out = {"start": None, "weeks": 2, "low": None, "high": None, "velocity": ""}
    if "start" in got:
        val, line = got["start"]
        out["start"] = _date(val)
        if out["start"] is None:
            issues.append(_issue("bad-value", "delivery", line, key="Start", value=val, why="It is the first day of the first period, "
                                 "written year-month-day.", write=START_FORM))
    if "period" in got:
        val, line = got["period"]
        m = _WEEKS.match(val)
        if m and int(m.group(1)) >= 1:
            out["weeks"] = int(m.group(1))
        else:
            issues.append(_issue("bad-value", "delivery", line, key="Period", value=val, why="It is a whole number of weeks, from 1; "
                                 "with no line it is 2 weeks.", write=PERIOD_FORM))
    if "velocity" in got:
        val, line = got["velocity"]
        m = _RANGE.match(val)
        low, high = (_number(m.group(1)), _number(m.group(2))) if m else (_number(val), _number(val))
        if low is None or high is None or low > high:
            issues.append(_issue("bad-value", "delivery", line, key="Velocity", value=val, why="It is how many Features finish in a "
                                 "period, slowest to fastest: numbers above 0 with at most two decimal places, the low "
                                 "not above the high. One number is a range of one.", write=VELOCITY_FORM))
        else:
            out["low"], out["high"], out["velocity"] = low, high, val.strip()
    if "order" in got:
        val, line = got["order"]
        seen = []
        for part in [x.strip() for x in val.split(",") if x.strip()]:
            f = named(part)
            if f is None or not any(f is x for x in live):
                issues.append(_issue("bad-value", "delivery", line, key="Order", value=part, why="It names no Feature that is "
                                     "not withdrawn.", write="- Order: " + ", ".join(x["name"] for x in live)))
            elif any(f is x for x in seen):
                issues.append(_issue("bad-value", "delivery", line, key="Order", value=part, why="It names a Feature twice.",
                                     write="- Order: " + ", ".join(x["name"] for x in live)))
            else:
                seen.append(f)
        order = seen
    return out, order


_ACTUAL_HOLE = {"started": "started <YYYY-MM-DD>", "finished": "finished <YYYY-MM-DD>", "items": "<d> of <t> items done"}


def _actual_form(name, parts, bad):
    """A Feature's Actuals line in its form, with this line's own values: each part that reads is kept as written and
    each that does not is the form of the part it was meant to be (the first form the line still lacks, when it cannot
    be told)."""
    kind = lambda p: "started" if p.lower().startswith("started") else "finished" if p.lower().startswith("finished") else \
        "items" if re.search(r"\bof\b|\bitems?\b", p.lower()) else None
    if all(kind(p) is None for p in parts):  # nothing in the line says which part it is: the whole form, under its name
        return "- %s: %s" % (name, ", ".join(_ACTUAL_HOLE[k] for k in ("started", "finished", "items")))
    have, shown = {kind(p) for p in parts if p not in bad}, []
    for p in parts:
        if p not in bad:
            shown.append(p)
            continue
        k = kind(p) or next((k for k in ("items", "started", "finished") if k not in have), "items")
        have.add(k)
        shown.append(_ACTUAL_HOLE[k])
    return "- %s: %s" % (name, ", ".join(shown))


def _read_actuals(items, live, named, issues):
    """The `### Actuals` lines: (the Read line as (date, rest, line) or None, {id of a Feature: its figures})."""
    read, actual = None, {}
    for item in items:
        key, _, val = item["text"].partition(":")
        line = item["line"]
        if " ".join(key.lower().split()) == "read":
            day = _date(val.split(",", 1)[0])
            if day is None:
                issues.append(_issue("bad-value", "actuals", line, key="Read", value=val.strip(), why="It starts with the day the "
                                     "actuals were read, written year-month-day.", write=READ_FORM))
            elif read is None:
                read = (day, val.split(",", 1)[1].strip() if "," in val else "", line)
            continue
        f = named(key.strip())
        if f is None or not any(f is x for x in live):
            issues.append(_issue("bad-value", "actuals", line, key="Actuals", value=key.strip(), why="It names no Feature that is "
                                 "not withdrawn.", write="- <one of %s>: started <date>, finished <date>, <d> of <t> items done"
                                 % ", ".join(x["name"] for x in live)))
            continue
        if id(f) in actual:
            issues.append(_issue("bad-value", "actuals", line, key="Actuals", value=key.strip(), why="It names a Feature twice.",
                                 write=ACTUAL_FORM))
            continue
        got, ok, bad = {"started": None, "finished": None, "items": None}, True, []
        val = val.strip()
        val = val[:-1].rstrip() if val.endswith(".") else val  # a full stop ends a sentence; it is not part of a figure
        parts = [x.strip() for x in val.split(",") if x.strip()]
        for part in parts:
            dated, items_done = _DATED.match(part), _ITEMS_DONE.match(part)
            if dated and _date(dated.group(2)):
                got[dated.group(1).lower()] = _date(dated.group(2))
            elif items_done and int(items_done.group(2)) >= 1 and int(items_done.group(1)) <= int(items_done.group(2)):
                got["items"] = (int(items_done.group(1)), int(items_done.group(2)))
            else:
                ok = False
                why = ("The first number cannot be more than the second, and the second is at least 1." if items_done else
                       "A date is written year-month-day." if dated else
                       "A Feature's line takes started <date>, finished <date> and <d> of <t> items done, with commas between.")
                bad.append((part, why))
        for part, why in bad:
            issues.append(_issue("bad-value", "actuals", line, key="Actuals", value=part, why=why,
                                 write=_actual_form(key.strip(), parts, [p for p, _ in bad])))
        if got["started"] and got["finished"] and got["finished"] < got["started"]:
            ok = False
            issues.append(_issue("bad-value", "actuals", line, key="Actuals", value=val.strip(), why="It finished before it started.",
                                 write=ACTUAL_FORM))
        if ok:
            actual[id(f)] = got
    return read, actual


def forecast_of(delivery, actuals, live, named):
    """The figures of the Delivery plan.

    delivery, actuals  the two sections' items, [{"text", "line"}]
    live               the Features that are not withdrawn, in store order
    named              a function from a name, handle or ID to a Feature, or None

    Returns a dict:
      ok        True when there is a Start, a Velocity and a Feature, so the forecast can be worked out
      needs     when not ok, the lines to add to `### Delivery`, in their form
      issues    what is wrong with the lines, for check: {code, section, line, key, value, why, write}
      missing   the lines that are not there: "start", "velocity" (of Delivery), "read" (of Actuals)
      start, weeks, low, high, velocity (as written), read (date or None), read_rest
      rows      one for each Feature in order: {feature, early, late, started, finished, items, pace, against}
      days, done, pace (Fraction or None), shown_pace ("0.42" or None), finished (count), last (date, against) or None
    """
    issues = []
    d, order = _read_delivery(delivery, live, named, issues)
    read, actual = _read_actuals(actuals, live, named, issues)
    missing = [k for k, v in (("start", d["start"]), ("velocity", d["low"])) if v is None and not any(
        i["section"] == "delivery" and i["key"] == k.capitalize() for i in issues)]
    out = {"issues": issues, "missing": missing + (["read"] if read is None and not any(
        i["key"] == "Read" for i in issues) else []), "start": d["start"], "weeks": d["weeks"], "low": d["low"],
           "high": d["high"], "velocity": d["velocity"], "read": read[0] if read else None, "read_rest": read[1] if read else "",
           "rows": [], "days": None, "done": Fraction(0), "pace": None, "shown_pace": None, "finished": 0, "last": None}
    needs = ([START_FORM] if d["start"] is None else []) + ([VELOCITY_FORM] if d["low"] is None else [])
    out["needs"] = needs
    out["ok"] = not needs and bool(live)
    if not out["ok"]:
        return out
    start, n, low, high = d["start"], d["weeks"], d["low"], d["high"]
    features = order + [f for f in live if not any(f is x for x in order)]
    end = lambda k: friday_of(start + datetime.timedelta(days=k * 7 * n - 1))
    for i, f in enumerate(features, 1):
        a = actual.get(id(f), {"started": None, "finished": None, "items": None})
        early, late = end(_ceil(Fraction(i) / high)), end(_ceil(Fraction(i) / low))
        part = Fraction(1) if a["finished"] else Fraction(a["items"][0], a["items"][1]) if a["items"] else Fraction(0)
        against = None
        if a["finished"]:
            day = friday_of(a["finished"])
            against = "earlier" if day < early else "later" if day > late else "within"
        out["rows"].append({"feature": f, "early": early, "late": late, "started": a["started"], "finished": a["finished"],
                            "items": a["items"], "part": part, "pace": None, "against": against})
    out["finished"] = sum(1 for r in out["rows"] if r["finished"])
    out["done"] = sum((r["part"] for r in out["rows"]), Fraction(0))
    if out["read"]:
        days = (out["read"] - start).days + 1
        out["days"] = days
        if days >= 7 * n and out["done"] > 0:
            out["pace"] = out["done"] * 7 * n / days
            out["shown_pace"] = "%d.%02d" % divmod(int((out["pace"] * 100 + Fraction(1, 2)) // 1), 100)
            left = Fraction(0)
            for r in out["rows"]:
                if r["finished"]:
                    continue
                left += 1 - r["part"]
                r["pace"] = friday_of(out["read"] + datetime.timedelta(days=_ceil(left * days / out["done"])))
            paced = [r for r in out["rows"] if r["pace"]]
            if paced:
                last = out["rows"][-1]
                day = paced[-1]["pace"]
                out["last"] = (day, "earlier" if day < last["early"] else "later" if day > last["late"] else "within")
    if out["last"] is None and out["read"] and out["finished"] == len(out["rows"]):
        last = out["rows"][-1]  # every Feature is finished: the plan is what happened
        out["last"] = (last["finished"], last["against"])
    return out


def forecast_for(store):
    """forecast_of for the Work in a store: its two sections and its Features that are not withdrawn."""
    work = next((r for r in store["records"] if r["kind"] == "work"), None)
    live = live_features(store)
    return forecast_of(work["delivery"] if work else [], work["actuals"] if work else [], live,
                       lambda part: feature_named(store["records"], part))


# ==== helper/src/workspace.py ===============================================
"""Workspace: finding work.md on disk and reading its files as text.

Owns find_workspace, read_workspace, read_text and the sentence for "there is no workspace here".
Must not know: what is in the files (records and validate read the text this module hands over).
"""

class Unreadable(Exception):
    """A workspace file the helper cannot read as UTF-8 text. args[0] is its path."""



def find_workspace(start=None, cwd=None):
    """The folder holding work.md: `start` if given, else `cwd` (default: here) or the nearest above it."""
    if start is not None:
        start = os.path.abspath(start)
        return start if os.path.isfile(os.path.join(start, "work.md")) else None
    folder = os.path.abspath(cwd or os.getcwd())
    while True:
        if os.path.isfile(os.path.join(folder, "work.md")):
            return folder
        parent = os.path.dirname(folder)
        if parent == folder:
            return None
        folder = parent


def _no_workspace(given, command):
    """Why there is no workspace: (where it was looked for, a sentence when the place is the skill's own folder).

    A model that changes into the skill's folder to run the helper is told so, never that there are no
    records: it would start a new work.md over the workspace's own (seen in a capture trial)."""
    if given:
        return "in %s" % given, ""
    cwd = os.path.realpath(os.getcwd())
    skill = os.path.realpath(os.path.dirname(HERE))
    if os.path.basename(HERE) == "scripts" and (cwd == skill or cwd.startswith(skill + os.sep)):
        return "in %s or in any folder above" % cwd, (
            "This was run from inside the skill's own folder (%s), which never holds records, so this says nothing "
            "about whether records exist. Run it again from the folder this session started in, or give that "
            "folder: %s <folder>" % (cwd, command))
    return "in %s or in any folder above" % cwd, ""


def read_workspace(folder):
    """Read work.md, then records/*.md in name order."""
    names = ["work.md"]
    extra = os.path.join(folder, "records")
    if os.path.isdir(extra):
        names += ["records/" + n for n in sorted(os.listdir(extra))
                  if n.endswith(".md") and os.path.isfile(os.path.join(extra, n))]
    sources = []
    for name in names:
        try:
            with open(os.path.join(folder, name), encoding="utf-8", newline="") as f:
                sources.append((name, f.read()))
        except UnicodeDecodeError:
            raise Unreadable(os.path.join(folder, name)) from None
    return read_store(sources, folder)


def _bytes(path):
    with open(path, "rb") as f:
        return f.read()


def read_text(path):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return f.read()
    except UnicodeDecodeError:
        raise Unreadable(path) from None


# ==== helper/src/validate.py ================================================
"""Validate: the checks made when records are read, and read_store, the one way to get a store from text.

  read_store([(file name, text), ...])  a store read from text already in hand

Owns what must hold across a record or across records: required lines, fixed values, IDs, steps, About and
Feature references, one Work. Must not know: briefs, baselines, the house, or anything about files on disk.
"""

def _missing(problems, rec, what, key, after, add, line=None):
    problems.append(_problem("missing", rec, rec["line"] if line is None else line, what=what, key=key,
                             at="after line %d" % after, add=add))


def _check_fields(rec, problems):
    """Required lines are there, and fixed values are among the allowed ones."""
    kind = rec["kind"]
    if not rec["name"]:
        problems.append(_problem("bad-value", rec, rec["line"], key="Name", value="",
                                 why="This %s heading has no name after the colon." % kind,
                                 write="## %s: <a short name>" % label(kind)))
    for key in REQUIRED[kind]:
        if key not in rec["fields"] and key in rec["empty"]:
            problems.append(_problem(
                "bad-value", rec, rec["empty"][key], key=label(key), value="",
                why="The line is there with nothing after the colon.",
                write="- %s: %s" % (label(key), PLACEHOLDER[key])))
        elif key not in rec["fields"]:
            _missing(problems, rec, "'%s' line" % label(key), label(key), rec["line"],
                     "- %s: %s" % (label(key), PLACEHOLDER[key]))
    assumed = kind == "question" and "working answer" in rec["fields"] and "answer" not in rec["fields"]
    for key in ASKED.get(kind, ()) + (("owner",) if assumed else ()):
        if key not in rec["fields"]:
            problems.append(_problem("not-given", rec, rec["empty"].get(key, rec["line"]), key=label(key),
                                     after=rec["line"], add="- %s: %s" % (label(key), PLACEHOLDER[key]),
                                     unknown="the intent" if key == "intent" else "the name"))
    for key, field in sorted(rec["fields"].items(), key=lambda kv: kv[1]["line"]):
        if key in FIXED and field["value"] not in FIXED[key]:
            allowed = _names(FIXED[key])
            problems.append(_problem(
                "bad-value", rec, field["line"], key=label(key), value=field["value"], allowed=list(FIXED[key]),
                why="It takes one of: %s." % allowed, write="- %s: <one of %s>" % (label(key), allowed)))


def _last_line(rec):
    """The last line of a record's own fields, where a missing line is written after."""
    return max([f["line"] for f in rec["fields"].values()] + list(rec["empty"].values()) + [rec["line"]])


def _not_given(problems, rec, key, who, placeholder):
    problems.append(_problem("not-given", rec, rec["line"], key=label(key), after=_last_line(rec), unknown=who,
                             add="- %s: %s" % (label(key), placeholder)))


def _check_observed(rec, problems):
    """What an Observed record must hold (ADR 0035): its status is only `withdrawn`; a `Requirement` goes beside a verdict
    of intended or defect; a missing owner, verdict-giver or requirement is information, never a finding."""
    status, verdict = rec["fields"].get("status"), value(rec, "verdict")
    if status and status["value"] != "withdrawn":
        problems.append(_problem(
            "bad-value", rec, status["line"], key="Status", value=status["value"], allowed=["withdrawn"],
            why="An Observed record takes only 'withdrawn' here: it is unconfirmed until it has a 'Verdict' line.",
            says="In %s, delete line %d, or change it to: - Status: withdrawn" % (rec["file"], status["line"])))
    req = rec["fields"].get("requirement")
    if req and verdict not in ("intended", "defect"):
        problems.append(_problem(
            "bad-value", rec, req["line"], key="Requirement", value=req["value"], allowed=[],
            why="A requirement is named here only beside a verdict of intended or defect, and this record has neither.",
            says="If a person has called it intended, or a defect, add after line %d: - Verdict: <intended or defect>   "
                 "Otherwise delete line %d." % (req["line"], req["line"])))
    if not verdict and "owner" not in rec["fields"]:
        _not_given(problems, rec, "owner", "who can say whether this is meant to happen", "<who can say>")
    if verdict == "intended" and "requirement" not in rec["fields"]:
        problems.append(_problem(
            "not-given", rec, rec["line"], key="Requirement", after=_last_line(rec), unknown="the requirement",
            add="- Requirement: <its ID or handle>",
            says="A person called this intended, so it becomes a requirement. Write the Requirement in the business's own "
                 "words (see the shape: %s --shape requirement), then in %s add after line %d: - Requirement: <its ID or "
                 "handle>   If a requirement already says it, name that one." % (CHECK + FOLDER, rec["file"], _last_line(rec))))
    if verdict == "defect" and "requirement" not in rec["fields"]:
        problems.append(_problem(
            "not-given", rec, rec["line"], key="Requirement", after=_last_line(rec), unknown="the requirement",
            add="- Requirement: <its ID or handle>",
            says="A defect departs from a required behaviour. In %s add after line %d: - Requirement: <the ID or handle of the "
                 "requirement this departs from>   If no required behaviour has been stated yet, raise it as a Question "
                 "(see the shape: %s --shape question) and take the Verdict line off this record."
                 % (rec["file"], _last_line(rec), CHECK + FOLDER)))

    if verdict in VERDICTS and "verdict by" not in rec["fields"]:
        _not_given(problems, rec, "verdict by", "who gave the verdict", "<name>")

def _check_requirement_lines(records, problems):
    """An Observed record's `Requirement` line names a Requirement that exists, by ID, handle or name (ADR 0035)."""
    reqs = [r for r in records if r["kind"] == "requirement"]
    for rec in records:
        field = rec["fields"].get("requirement") if rec["kind"] == "observed" else None
        if not field or value(rec, "verdict") not in ("intended", "defect"):
            continue
        part = field["value"].strip().lower()
        named = next((r for r in reqs if part in ((r["id"] or "").lower(), r["name"].strip().lower())), None)
        if named is not None and value(rec, "verdict") == "defect" and status_of(named) == "draft":
            _defect_against_a_draft(problems, rec, named)
        if named is None:
            known = [r["id"] or r["name"] for r in reqs]
            shown = _names(known[:12]) + (", ..." if len(known) > 12 else "") if known else "none yet"
            problems.append(_problem(
                "bad-value", rec, field["line"], key="Requirement", value=field["value"], allowed=known,
                why="No Requirement has that ID, handle or name.",
                write="- Requirement: <the ID, handle or name of a Requirement that exists: %s>" % shown))


def _defect_against_a_draft(problems, rec, req):
    """A defect passes the test of observed behaviour and required behaviour (the maintainer, 24 November). A draft
    requirement is not yet a required behaviour, so the verdict rests on nothing agreed: information, with both ways out."""
    status = req["fields"].get("status")
    confirm = ("change line %d to: - Status: confirmed" % status["line"] if status else
               "add after line %d: - Status: confirmed" % req["fields"]["id"]["line"] if "id" in req["fields"] else
               "add under line %d: - Status: confirmed" % req["line"])
    own = sorted(rec["fields"][k]["line"] for k in ("verdict", "verdict by", "requirement") if k in rec["fields"])
    who = value(rec, "verdict by") or value(rec, "owner") or "the person who called it a defect"
    problems.append(_problem(
        "stale", rec, rec["fields"]["requirement"]["line"], key="Requirement", value=rec["fields"]["requirement"]["value"],
        what="This is called a defect against %s, which is still a draft, so the required behaviour is not yet agreed"
             % " ".join(x for x in (req["id"], "'%s'" % req["name"]) if x),
        how="Ask %s whether that requirement says what must happen. If yes: in %s, %s   If not, or nobody has said: in %s, "
            "delete %s %s (this record's verdict and requirement lines) and raise a Question asking what should happen "
            "(see the shape: %s --shape question)."
            % (who, req["file"], confirm, rec["file"], "lines" if len(own) > 1 else "line", _names(str(n) for n in own), CHECK + FOLDER)))


def _check_id(rec, problems, ids):
    """The ID line is well formed and carries the letter of its record's kind."""
    kind = rec["kind"]
    rid = rec["id"] = value(rec, "id")
    if not rid:
        return
    line = rec["fields"]["id"]["line"]
    m = _ASSIGNED.match(rid)
    if m and m.group(1) != ID_LETTER[kind]:
        problems.append(_problem(
            "ambiguous", rec, line, key="ID", value=rid,
            what="ID '%s' starts with the letter of a different kind of record, but this is a %s (letter %s)."
                 % (rid, kind, ID_LETTER[kind]),
            one="the record is right: change line %d to '- ID: <a handle, for example %s>' and run %s so it gets "
                "the next %s- number." % (line, re.sub(r"[^a-z0-9]+", "-", rec["name"].lower()).strip("-") or kind,
                                    _fixcmd(), ID_LETTER[kind]),
            two="the ID is right and the kind is wrong: change line %d to '## %s: %s'."
                % (rec["line"], label({v: k for k, v in ID_LETTER.items()}[m.group(1)]), rec["name"])))
    elif not m and not _HANDLE.match(rid):
        problems.append(_problem(
            "bad-value", rec, line, key="ID", value=rid, why="An ID is one or two capital letters, a hyphen and a number, or a handle.",
            write="- ID: <a handle: lower-case words joined by hyphens, for example parking-permit>"))
    ids.append(rec)


def _check_steps(rec, problems):
    """A flow has a step, step names are unique, each step has a Description, each Go to names a step."""
    if not rec["steps"]:
        _missing(problems, rec, "'### Step:' heading", "Step", rec["end"],
                 "### Step: <name>, then under it: - Description: %s" % PLACEHOLDER["description"],
                 line=rec["line"])
    names = {}
    for s in rec["steps"]:
        if not s["name"]:
            problems.append(_problem("bad-value", rec, s["line"], key="Name", value="",
                                     why="This step heading has no name after the colon.",
                                     write="### Step: <a short name>"))
        elif s["name"].lower() in names:
            first = names[s["name"].lower()]
            problems.append(_problem(
                "ambiguous", rec, s["line"], key="Step", value=s["name"], lines=[first["line"], s["line"]],
                what="Two steps of this flow are named '%s' (lines %d and %d), so a Go to cannot say which."
                     % (s["name"], first["line"], s["line"]),
                one="they are different steps: rename line %d, for example '### Step: %s again', and point any "
                    "Go to that meant it at the new name." % (s["line"], s["name"]),
                two="they are one step: move what is under line %d up under line %d and delete line %d."
                    % (s["line"], first["line"], s["line"])))
        else:
            names[s["name"].lower()] = s
    for s in rec["steps"]:
        if "description" not in s["fields"] and "description" in s["empty"]:
            problems.append(_problem(
                "bad-value", rec, s["empty"]["description"], key="Description", value="",
                why="The line is there with nothing after the colon.",
                write="- Description: %s" % PLACEHOLDER["description"]))
        elif "description" not in s["fields"]:
            _missing(problems, rec, "'Description' line", "Description", s["line"],
                     "- Description: %s" % PLACEHOLDER["description"], line=s["line"])
        for g in s["go to"]:
            # A step's own name may hold "(when ...)": take the longest reading that names a step.
            last = re.match(r"(?i)^(.*\S)\s*\((?:when\s+)?(.*)\)$", g["text"])
            for to, when in [(g["text"], "")] + ([(last.group(1), last.group(2).strip())] if last else []):
                if to.lower() in names:
                    g["to"], g["when"] = to, when
                    break
            if g["to"].lower() not in names:
                steps = list(dict.fromkeys(x["name"] for x in rec["steps"] if x["name"]))
                problems.append(_problem(
                    "bad-value", rec, g["line"], key="Go to", value=g["to"], allowed=steps,
                    why="Step '%s' must go to a step of this flow." % s["name"],
                    write="- Go to: <one of %s> (keep any '(when ...)' ending)" % _names(steps)))


def _check_record(rec, problems, ids):
    _check_fields(rec, problems)
    if rec["kind"] == "observed":
        _check_observed(rec, problems)
    _check_id(rec, problems, ids)
    rec["about"] = _parts(value(rec, "about"))
    rec["flows"] = _parts(value(rec, "flow")) if rec["kind"] == "feature" else []
    if rec["kind"] == "flow":
        _check_steps(rec, problems)


def _check_store(records, problems, first_file):
    seen = {}
    for rec in records:
        if not rec["id"] or "id" not in rec["fields"]:
            continue
        line = rec["fields"]["id"]["line"]
        if rec["id"] in seen:
            first = seen[rec["id"]]
            where = "%s on line %d" % (first["file"], first["line"])
            problems.append(_problem(
                "ambiguous", rec, line, key="ID", value=rec["id"], first=first,
                what="ID '%s' is also used in %s." % (rec["id"], where),
                one="these are two records: change line %d to '- ID: <a new handle>' and run %s so it gets a "
                    "number." % (line, _fixcmd()),
                two="these are one record: delete this block (lines %d to %d) and keep the one in %s."
                    % (rec["line"], rec["end"], where)))
        else:
            seen[rec["id"]] = {"file": rec["file"], "line": line}
    for rec in records:
        for ref in rec["about"]:
            if ref not in seen:
                known = sorted(i for i in seen if _ASSIGNED.match(i) or _HANDLE.match(i))
                shown = _names(known[:12]) + (", ..." if len(known) > 12 else "") if known else "none yet"
                problems.append(_problem(
                    "bad-value", rec, rec["fields"]["about"]["line"], key="About", value=ref, allowed=known,
                    why="No record has that ID or handle.",
                    write="- About: <IDs or handles of records that exist: %s> (or add a record with '- ID: %s')"
                          % (shown, ref)))
    _check_features(records, problems)
    _check_requirement_lines(records, problems)
    works = [r for r in records if r["kind"] == "work"]
    if not works:
        problems.append(_problem("missing", {"file": first_file}, 1, what="Work record", key="Work", at="at the top",
                                 add="## Work: <the name of this piece of work>"))
    main = [w for w in works if w["file"] == first_file]
    for w in works:
        if w["file"] != first_file:
            problems.append(_problem(
                "ambiguous", w, w["line"], key="Work", value=w["name"],
                what="The Work record is in %s, and it belongs in %s." % (w["file"], first_file),
                one="move it: cut lines %d to %d from %s and paste them into %s (if %s already has a Work, "
                    "this is a second one: see that finding)." % (w["line"], w["end"], w["file"], first_file, first_file),
                two="it repeats the Work in %s: delete lines %d to %d from %s." % (first_file, w["line"], w["end"], w["file"])))
    for w in main[1:]:
        problems.append(_problem(
            "ambiguous", w, w["line"], key="Work", value=w["name"],
            what="A workspace has one Work record, and '%s' is another (the first is on line %d)." % (w["name"], main[0]["line"]),
            one="it is a different piece of work: it belongs in its own folder with its own work.md; cut lines %d to %d "
                "from %s." % (w["line"], w["end"], w["file"]),
            two="it is the same piece of work: copy anything you need from lines %d to %d into the first Work, then "
                "delete them." % (w["line"], w["end"])))


def _check_features(records, problems):
    """A Feature's Flow, Flow steps and Sliced from name what exists; two live Features do not share a name."""
    first = {}
    for r in records:
        if r["id"]:
            first.setdefault(r["id"].lower(), r)
    features = [r for r in records if r["kind"] == "feature"]
    live = {}
    for f in features:
        key = f["name"].strip().lower()
        if status_of(f) == "withdrawn" or not key:
            continue
        if key in live:
            one = live[key]
            problems.append(_problem(
                "ambiguous", f, f["line"], key="Name", value=f["name"], lines=[one["line"], f["line"]],
                what="Two Feature records that are not withdrawn are named '%s' (lines %d and %d), so a Feature line "
                     "cannot say which." % (f["name"], one["line"], f["line"]),
                one="they are two features: rename line %d, for example '## Feature: %s, part 2', and point any "
                    "Feature line that meant it at the new name or at its ID." % (f["line"], f["name"]),
                two="they are one feature: delete the second block (lines %d to %d) and keep the first."
                    % (f["line"], f["end"])))
        else:
            live[key] = f
    for f in features:
        flows = []
        known = sorted(r["id"] for r in records if r["kind"] == "flow" and r["id"])
        for ref in f["flows"]:
            there = first.get(ref.lower())
            if there is not None and there["kind"] == "flow":
                flows.append(there)
                continue
            shown = _names(known[:12]) + (", ..." if len(known) > 12 else "") if known else "none yet"
            why = ("No record has that ID or handle." if there is None else
                   "That is a %s, and this line names flows." % there["kind"])
            problems.append(_problem(
                "bad-value", f, f["fields"]["flow"]["line"], key="Flow", value=ref, allowed=known, why=why,
                write="- Flow: <IDs or handles of flows that exist: %s>" % shown))
        steps = list(dict.fromkeys(s["name"] for fl in flows for s in fl["steps"] if s["name"]))
        for item in f["flow steps"]:
            if item["text"].lower() not in [x.lower() for x in steps]:
                problems.append(_problem(
                    "bad-value", f, item["line"], key="Flow steps", value=item["text"], allowed=steps,
                    why="It is not the name of a step in the feature's Flow." if steps else
                        "The feature has no Flow line that names a flow, so there are no steps to choose from.",
                    write="- <one of: %s>" % _names(steps) if steps else
                          "- <a step name>, after adding a '- Flow: <ID or handle of a flow>' line"))
        if "sliced from" in f["fields"]:
            value_, line = value(f, "sliced from"), f["fields"]["sliced from"]["line"]
            parts = _parts(value_)
            offers = _names("'%s'" % (x["name"] if "," not in x["name"] else x["id"] or x["name"])
                            for x in features if x is not f)
            if len(parts) != 1 or feature_named(records, parts[0]) is None:
                other = first.get(parts[0].lower()) if len(parts) == 1 else None
                why = ("It names one Feature, and this names %d." % len(parts) if len(parts) > 1 else
                       "That is a %s, and this line names a Feature." % other["kind"] if other else
                       "No Feature record has that ID, handle or name.")
                problems.append(_problem(
                    "bad-value", f, line, key="Sliced from", value=value_, allowed=[], why=why,
                    write="- Sliced from: <the ID or name of the one Feature this was cut from%s>"
                          % (": " + offers if offers else "")))


def _hand_edits(records, problems):
    for rec in records:
        lines = [o["line"] for o in rec["other"] if not o["reported"]]
        if lines:
            keys = list(FIELDS[rec["kind"]]) + (list(STEP_FIELDS) if rec["kind"] == "flow" else [])
            renamed = ""
            for o in rec["other"]:
                k = _KEY.match(o["text"].strip()) if not o["reported"] else None
                new = RENAMED.get((rec["kind"], " ".join(k.group(1).lower().split()))) if k else None
                if new:
                    renamed += "Line %d: '%s' is now called '%s'; change it to '- %s: <the same text>'. " % (
                        o["line"], k.group(1).strip(), label(new), label(new))
            problems.append(_problem("hand-edit", rec, lines[0], count=len(lines), lines=lines,
                                     keys=_names(label(k) for k in keys), renamed=renamed,
                                     nothing="Nothing else to do." if renamed else "Nothing to do."))


def read_store(sources, folder=None):
    """Read records from [(file name, text), ...], in that order. See the module docstring."""
    files, records, problems, ids = {}, [], [], []
    for file, text in sources:
        files[file] = _LINE.findall(text)
        _parse_file(file, files[file], records, problems)
    for rec in records:
        _check_record(rec, problems, ids)
    first_file = "work.md" if "work.md" in files or not files else next(iter(files))
    _check_store(records, problems, first_file)
    _hand_edits(records, problems)
    order = {file: i for i, file in enumerate(files)}
    problems.sort(key=lambda p: (order.get(p["file"], 0), p["line"]))
    return {"folder": folder, "files": files, "records": records, "problems": problems}


# ==== helper/src/shapes.py ==================================================
"""Shapes: one filled-in example of each kind of record, printed by `check --shape` (ADR 0011).

Pure text, and `_sample`: the same examples read as a store, for the commands that need records and have no
workspace (`check --adopt`, `bundle landing`). Must not know: anything else. It changes when the grammar in
records.py does.
"""

# ---------------------------------------------------------------------------
# Shipped examples: one filled-in record of each kind (Work, Requirement, Question, Flow, Feature). `check --shape <kind>`
# prints one. These are what an agent copies, so they change with ADR 0011.
# ---------------------------------------------------------------------------

# Printed first, whatever shape is asked for: a cheap model took the example Work for the workspace's own.
SHAPE_NOTE = ("Made-up example records, to copy the shape of. They are not this workspace's records: the leave-booking "
              "work, its people and its IDs exist nowhere. This workspace's records are the ones in work.md.\n\n")

SHAPES = {
    "work": """\
## Work: Leave booking for shift staff

<!-- One per workspace, in work.md. Leave out any line you have nothing for. The last five lines take yes or no. -->
<!-- Fixed values. Status: draft | confirmed | withdrawn. The five size lines take yes | no:
More than one approver: more than one person must say yes before this goes ahead.
More than one team: people outside the requester's own team must change how they work.
Regulation or contract: a law, regulation or contract sets rules this work must follow.
Data from an old system: information must be moved or read from a system that is being replaced.
Several features: the goal needs several features that are scoped and forecast together. -->
<!-- Where its pages go, and documents another team keeps: "### Destinations" with - Parent page: <link>, - Parent page ID: <number>, - Space key: <key>, - Space ID: <number>; "### Linked documents" with - <name>: <link>, kept by <who>. A linked document is never copied or published. -->
<!-- When an approver answers, add "### Approvals" with: - <name>: approved, <date>, records version <the brief's version>, "<their words>" (or changes asked). -->
<!-- More lists, each optional: "### Stakeholders" with - <name>: <decides, consulted or told>, <what they need from this work>   and   "### Tolerances" with - <what may change without going back to the approvers, and how far>. -->
<!-- The forecast: "### Delivery" with - Start: <YYYY-MM-DD>, - Period: <n> weeks, - Velocity: <low> to <high> (Features finished in a period), - Order: <Feature names, commas between>; "### Actuals" with - Read: <date>, <where from, by whom> and a line for each Feature: - <Feature>: started <date>, finished <date>, <d> of <t> items done. -->
- ID: leave-booking
- Status: draft
- Goal: Shift staff book leave themselves and managers stop keeping paper diaries.
- Tracker: HR-212
- Approvers: Maria Okafor
- More than one approver: no
- More than one team: yes
- Regulation or contract: no
- Data from an old system: no
- Several features: no

### People

- Sponsor: Maria Okafor
- Product owner: Dana Whitlock
- Business analyst: Lee Tran

### Assumptions

- Agency staff stay on timesheets.

### Out of scope

- Sick leave.
""",
    "requirement": """\
## Requirement: Overlap warning

<!-- Statement and Source are needed; leave out any other line you have nothing for.
ID: lower-case words joined by hyphens. Status: draft | confirmed | withdrawn (draft until the BA confirms).
A withdrawn record is kept, and may say why on a "- Withdrawn because: <reason>" line.
Category is an optional line, "- Category: <value>", added only when the material makes it plain. Usual values:
functional | non-functional | business | compliance | transition, or the house's own.
Feature is an optional line, "- Feature: <name>": add it only when the material itself groups requirements under a
named capability, in the material's words.
Other lines, only when the person said so: Priority (must | should | could | wont), Priority notes, and for a
non-functional need Measure and Threshold.
Each example is a concrete case: a named person and numbers. It starts "said:" (a person gave it) or
"proposed:" (you suggested it). -->
- ID: overlap-warning
- Status: draft
- Statement: As a shift manager I want a warning when a leave request overlaps approved leave on my ward so that I do not leave a shift short.
- Source: Dana Whitlock, workshop 3 November
- Why: Two night shifts ran short last quarter because nobody noticed overlapping leave.

### Examples

- said: Ward 4 has 6 nurses and needs 4 on each night shift. Aisha is approved for 12 December, and Ben asks for the same night. Dana, the ward manager, sees a warning that names Aisha.
- proposed: Chen on Ward 6 asks for 12 December, the night Aisha is off on Ward 4. Dana sees no warning, because Chen works on another ward.
""",
    "question": """\
## Question: Can leave be booked in half days?

<!-- The heading is the question. Raised by and Context are optional: leave a line out when you do not know it.
About names the IDs of the records it concerns, separated by commas.
Owner is who can answer it; About names the Feature or Requirement it concerns.
Raised is the day the question came up; today's date is shown, so change it only for a question that came up earlier.
Add the Answer and Answered by lines only once someone has answered.
When the person says they have asked it, add a "- Asked: <today's date>" line: it is then left out of the chasers until it is answered.
An assumption is a question with a "- Working answer: <what is taken as true meanwhile, a statement that stands alone>"
line and an "- Owner: <who can confirm it>" line, and no Answer. -->
- ID: half-days
- Raised by: Dana Whitlock
- Raised: <today>
- Context: Two ward managers asked for it when the paper diary was retired.
- About: overlap-warning
- Answer: Yes, in half shifts.
- Answered by: Maria Okafor
""",
    "feature": """\
## Feature: Overlap warning for ward managers

<!-- A feature groups the requirements that are built and handed over together. A requirement names it on its
"- Feature:" line, by this name or its ID, or several separated by commas. Intent is one line: what a named person
can do or see once the feature is built. Flow names the flows it runs through, by ID or handle; "### Flow steps"
lists the steps of those flows that this feature delivers (with no list it takes every step). Status: draft |
confirmed | withdrawn; a withdrawn one that was not sliced may say why on a "- Withdrawn because: <reason>" line.
Optional lines, only when they apply: "- Sliced from: <the feature this was cut from>" and
"- Tracker: <the tracker item the brief is published to>". -->
- ID: overlap-feature
- Status: draft
- Intent: A ward manager who asks for leave that overlaps approved leave on their ward sees a warning that names who is off.
- Flow: requesting-leave

### Flow steps

- Manager decides
""",
    "flow": """\
## Flow: Requesting leave

<!-- One "### Step: <name>" per step, each with a Description.
"Go to" names the next step exactly as its heading does. A decision has one "Go to" line per branch.
A step with no "Go to" line ends the flow.
Fixed values. Status: draft | confirmed | withdrawn. -->
- ID: requesting-leave
- Status: draft
- Source: Dana Whitlock, workshop 3 November
- Overview: How a leave request goes from a member of staff to an answer.
- Trigger: A member of staff wants time off.

### Step: Staff member asks for leave

- Description: The staff member picks the dates and sends the request.
- Inputs: Dates wanted
- Outputs: Leave request
- Stakeholders: Shift staff
- Tools: Rostering system
- Go to: Manager decides

### Step: Manager decides

- Description: The manager checks the request against the ward roster.
- Go to: Leave approved (when the ward is still covered)
- Go to: Leave declined (when the ward would be short)

### Step: Leave approved

- Description: The leave goes on the roster and the staff member is told.

### Step: Leave declined

- Description: The staff member is told why and may ask for other dates.
""",
    "observed": """\
## Observed: Leave of more than ten days waits for a second manager

<!-- Something an existing system or document was seen to do. It is not a requirement.
The heading and Behaviour say what happens and to whom, in the business's own words, with no name of a file,
function, table, field or screen. Seen in is where it was seen: the one line that may hold such a name.
Add Verdict (intended | accidental | defect) and Verdict by only once a person has said which.
A defect is behaviour that departs from a requirement someone has stated: name it. If none has been stated, raise a
question and leave the verdict off. Intended or defect, then name the Requirement here on a "- Requirement: <its ID>" line. -->
- ID: second-manager
- Behaviour: A request for more than ten days of leave is not granted until a second manager has agreed it.
- Seen in: rota system code, leave/approve.py lines 40 to 62, read by Sam Okoro's team
- Raised by: Sam Okoro
- Raised: <today>
- About: overlap-warning
- Owner: Maria Okafor
""",
}


def shape_text(kind):
    """The shape of one kind as `check --shape` prints it: a date in it is the day's (`_today`, which
    SOURCE_DATE_EPOCH fixes), so a skill that copies the line has the right date without a word about it."""
    return SHAPES[kind].replace("<today>", _today())


def _sample():
    """The helper's own made-up records, the ones `check --shape all` prints, with the requirement in the Feature,
    so every block of every face has something to show. Returns (store, the Feature)."""
    store = read_store([("work.md", SHAPE_NOTE + "\n".join(shape_text(k) for k in FIRST_FIVE))], "")
    feature = next(r for r in store["records"] if r["kind"] == "feature")
    for r in store["records"]:
        if r["kind"] == "requirement":
            r["fields"]["feature"] = {"value": feature["name"], "line": r["line"]}
    return store, feature


# ==== helper/src/house.py ===================================================
"""House: the files a brief is made from, and the one place they are read (ADR 0018, 0025).

Owns the word list (Words, load_words), the house itself (House: one reader over a folder or a pack, with the
shipped house behind it), the three profile files (hierarchy, destinations, brand) as they are read, and finding a
template. Every caller asks a House for a file by name and never learns which form it came from. Must not know:
what any template says, or how a face is built from it.
"""

SHIPPED = os.path.join(HERE, "house")  # the default house, beside the helper wherever it is installed


HOUSE_FILES = ("words.md", "hierarchy.md", "destinations.md", "brand.md")
_PACK_MARK = re.compile(r"^=== (.+?) ===\s*$")
_LINK = re.compile(r"^https?://\S+$")
APPROVE = "how to approve"  # the label a template writes as {How to approve}; the row is "How to approve: <Approval>"


class Words:
    """The word list: the house's rows first, then the shipped ones. See ADR 0018, Word list."""

    def __init__(self, texts, approval="reply"):
        """`texts` is [(file shown in findings, its text or None)], most specific first."""
        self.rows, self.plurals, self.missing = {}, {}, []
        self.file, self.last_line, self.approval = None, 0, approval
        for n, (path, text) in enumerate(texts):
            if text is None:
                continue
            lines = _LINE.findall(text)
            if n == 0:
                self.file, self.last_line = path, len(lines)
            for raw in lines:
                cells = [c.strip() for c in raw.strip().strip("|").split("|")]
                # The header row is "Word | Shown as"; a row for the word "Word" is data.
                if not raw.strip().startswith("|") or len(cells) < 2 or set(cells[0]) <= set("-: ") \
                        or (cells[0].lower() == "word" and cells[1].lower() == "shown as"):
                    continue
                key = cells[0].lower()
                self.rows.setdefault(key, (cells[1], cells[2] if len(cells) > 2 else ""))
                if len(cells) > 2 and cells[2]:
                    self.plurals.setdefault(cells[2].lower(), key)

    def show(self, word):
        """The label for a word, or the word as written, with nothing noted: for a value a house may add to."""
        return self.rows.get(word.lower(), (word,))[0]

    def get(self, word):
        """The label for a word, or the word itself (noted as missing) when no list has it.
        {How to approve} is the row for the house's way of approving (ADR 0025)."""
        if word.lower() == APPROVE:
            word = "How to approve: " + self.approval
        key = word.lower()
        if key in self.rows:
            return self.rows[key][0]
        if key in self.plurals:
            shown, more = self.rows[self.plurals[key]]
            return more or shown
        if word not in self.missing:
            self.missing.append(word)
        return word


def load_words(dirs, approval="reply"):
    """Words from words.md in each folder, most specific first."""
    texts = []
    for d in dirs:
        path = os.path.join(d, "words.md")
        try:
            texts.append((path, read_text(path)))
        except (OSError, Unreadable):
            texts.append((path, None))
    return Words(texts, approval)


class _Folder:
    """A house held as files in a folder."""
    form = "a folder"

    def __init__(self, path):
        self.path = path

    def text(self, name):
        path = self.where(name)
        return read_text(path) if os.path.isfile(path) else None

    def where(self, name):
        return os.path.join(self.path, *name.split("/"))

    def names(self):
        """Every file the folder holds, as a pack would name it."""
        out = []
        for where, _, files in sorted(os.walk(self.path)):
            out += [os.path.relpath(os.path.join(where, f), self.path).replace(os.sep, "/") for f in sorted(files)]
        return out


class _Pack:
    """A house held in one file: each file under a line `=== <name> ===`. Lines before the first are ignored."""
    form = "a pack"

    def __init__(self, path):
        self.path, self.files, self.starts, name = path, {}, {}, None
        for n, raw in enumerate(_LINE.findall(read_text(path).replace("\r\n", "\n")), 1):
            m = _PACK_MARK.match(raw.rstrip("\n"))
            if m:
                name = m.group(1)
                self.files.setdefault(name, [])
                self.starts.setdefault(name, n)
            elif name is not None:
                self.files[name].append(raw)

    def text(self, name):
        if name not in self.files:
            return None
        lines = list(self.files[name])
        while lines and not lines[-1].strip():
            lines.pop()
        return "".join(lines) + "\n" if lines else ""

    def where(self, name):
        return "%s (%s)" % (self.path, name)

    def names(self):
        return list(self.files)


class House:
    """The files a brief is made from: the house's own layer, then the shipped house behind it.

    `ref` is the house as the Work or the option wrote it (None for the shipped house). `text(name)` is the first
    layer's file of that name, so a file the house lacks is the shipped one whole; the word list alone is read
    row by row, and templates are found file by file."""

    def __init__(self, ref=None, own=None, work=None):
        self.ref, self.own, self.work = ref, own, work  # `work`: the Work whose `### Destinations` lie over the house's (ADR 0038)
        self.layers = ([own] if own else []) + [_Folder(SHIPPED)]

    def places(self):
        """The destinations this Work sends to: the house's, with the Work's own parent page over its sign-off brief."""
        return places(self.work, self)

    def text(self, name):
        for layer in self.layers:
            got = layer.text(name)
            if got is not None:
                return got
        return None

    def where(self, name):
        return next((l.where(name) for l in self.layers if l.text(name) is not None), name)

    def words(self):
        return Words([(l.where("words.md"), l.text("words.md")) for l in self.layers], approval_of(self))

    def templates(self, face, own_only=False):
        """{file name: where it is shown} of every template of this face, the most specific layer winning."""
        found = {}
        layers = ([self.own] if self.own else []) if own_only else self.layers
        for layer in reversed(layers):
            for name in layer.names():
                if name.startswith("templates/") and "/" not in name[10:] and face["templates"].match(name[10:]):
                    found[name[10:]] = layer.where(name)
        return found

    def template(self, face, name):
        return self.text("templates/" + name)

    def own_files(self):
        """The files the house holds itself that ba reads, in the order a person would list them."""
        if not self.own:
            return []
        names = self.own.names()
        known = [n for n in HOUSE_FILES if n in names]
        faces = list(FACES.values())
        mine = [(i, n) for n in names if n.startswith("templates/") and "/" not in n[10:]
                for i, f in enumerate(faces) if f["templates"].match(n[10:])]
        return known + [n for _, n in sorted(mine)]

    def line(self):
        if not self.own:
            return "the shipped house"
        return "%s (its own: %s; the rest are the shipped house)" % (self.ref, ", ".join(self.own_files()) or "nothing")


def _open(path):
    """The house at a path: a folder, a pack, or None when there is no such file or folder."""
    if os.path.isdir(path):
        return _Folder(path)
    return _Pack(path) if os.path.isfile(path) else None


def _house(folder, work, option):
    """The House a brief is made from. Returns (house, problems, error); `error` is a sentence when the --house
    option names nothing."""
    if option:
        own = _open(os.path.abspath(option))
        if own is None:
            return None, [], "--house names '%s', and there is no such folder. Give the folder that holds words.md " \
                             "and templates/, or the file that holds them as a pack." % option
        return House(os.path.abspath(option), own, work), [], None
    ref = value(work, "house")
    if not ref:
        return House(work=work), [], None
    line = work["fields"]["house"]["line"]
    if _LINK.match(ref):
        path = os.path.join(folder, "house.md")
        if os.path.isfile(path):
            return House(ref, _Pack(path), work), [], None
        return House(work=work), [_problem(
            "bad-value", work, line, key="House", value=ref, allowed=[],
            why="This is a link to a page, and house.md, the page as fetched, is not beside work.md, so the shipped house "
                "is used.",
            says="Leave line %d as it is. Fetch that page and write its code block to house.md beside work.md, as "
                 "references/home.md says (A house kept on a page)." % line)], None
    path = ref if os.path.isabs(ref) else os.path.join(folder, ref)
    own = _open(path)
    if own is not None:
        return House(ref, own, work), [], None
    return House(work=work), [_problem(
        "bad-value", work, line, key="House", value=ref, allowed=[],
        why="There is no folder or file of that name here, so the shipped house is used.",
        write="- House: <the house: a folder or a pack file, as a path from this folder, or the link of the page it is kept on>")], None


def _form_names(face, house, own):
    """The forms a face's templates come in, in the order of their file names; the house's own unnamed one is
    shown as `own`. None for a face that has no forms."""
    if not face["forms"]:
        return None
    return [re.sub(r"^signoff-?|\.md$", "", n) or own for n in sorted(house.templates(face))]


def _pick_template(face, house, form):
    """(file name, where it is) or (None, sentence). For a face with forms, a named form is signoff-<form>.md; with
    none named, the house's own signoff.md, else the shipped moscow form. Any other face has the one template."""
    found = house.templates(face)
    if not face["forms"]:
        name = face["template"]
    elif form:
        name = "signoff-%s.md" % re.sub(r"\s+", "-", form.strip().lower())
    else:
        name = "signoff.md" if "signoff.md" in house.templates(face, own_only=True) else face["template"]
    if name in found:
        return name, found[name]
    forms = _form_names(face, house, "(the house's own)")
    return None, face["no_template"].format(name=name, forms=", ".join(sorted(forms or ())))


# ---------------------------------------------------------------------------
# The profile files (ADR 0025): hierarchy.md and destinations.md, read from any House. Nothing is looked up and
# nothing is compared with a canonical word: a cell or a value says what it says.
# ---------------------------------------------------------------------------

LEVELS = ("work", "feature", "requirement")
SECTIONS = ("sign-off brief", "business board", "delivery board")
_KEYLINE = re.compile(r"^-\s*([^:]+?)\s*:\s*(.*?)\s*$")


def _blank_comments(text):
    return re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def given(v):
    """A value that is set: not empty and not `not set`."""
    return bool(v) and v.strip().lower() != "not set"


def read_destinations(text):
    """{"top": {key: (value, line)}, "sections": {name: {key: (value, line)}}, "headings": [(line, name)]}.
    Keys and section names are lower case; a line that is not `- Key: value` is not read."""
    out = {"top": {}, "sections": {}, "headings": []}
    here = out["top"]
    for n, raw in enumerate(_blank_comments(text).replace("\r\n", "\n").split("\n"), 1):
        line = raw.strip()
        if line.startswith("## "):
            name = line[3:].strip().lower()
            out["headings"].append((n, name))
            here = out["sections"].setdefault(name, {})
            continue
        m = _KEYLINE.match(line)
        if m:
            here.setdefault(m.group(1).lower(), (m.group(2), n))
    return out


_PAGE = re.compile(r"^(?P<path>.+?)\s*,\s*page\s+(?P<id>\d+)\s*,\s*parent\s+(?P<parent>\d+)\s*$", re.I)
_OWN = ("parent page", "parent page id", "space key", "space id", "landed")  # what a Work may say of its own page


def work_destinations(work):
    """({key: (value, line)}, [(path, page ID, parent ID, line)], [the lines of a `Page` item that is not read]) from the Work's
    `### Destinations`: its `- Key: value` items, and each `- Page: <title> / <title>, page <ID>, parent <ID>` (ADR 0038)."""
    keys, pages, bad = {}, [], []
    for item in work["destinations"] if work else []:
        m = _KEYLINE.match("- " + item["text"])
        if not m:
            continue
        key, val = m.group(1).lower(), m.group(2)
        page = _PAGE.match(val) if key == "page" else None
        if key == "page" and page:
            pages.append((page.group("path"), page.group("id"), page.group("parent"), item["line"]))
        elif key == "page":
            bad.append(item["line"])
        else:
            keys.setdefault(key, (val, item["line"]))
    return keys, pages, bad


def places(work, house):
    """read_destinations of the house, with the Work's own parent page over its `sign-off brief` section when the Work gives
    both a Parent page ID and a Space ID (ADR 0038). Approval, the arrangement lines (`<face> under`), the site and the
    boards are always the house's. `pages` are the pages recorded on the Work, and `own` says whose parent page it is."""
    dest = read_destinations(house.text("destinations.md") or "")
    keys, pages, _ = work_destinations(work)
    dest["pages"], dest["own"] = pages, False
    if given(keys.get("parent page id", ("",))[0]) and given(keys.get("space id", ("",))[0]):
        sec = dest["sections"].get("sign-off brief", {})
        kept = {k: v for k, v in sec.items() if k == "approval" or k.endswith(" under")}
        kept.update({k: v for k, v in keys.items() if k in _OWN})
        dest["sections"]["sign-off brief"], dest["own"] = kept, True
    return dest


def page_path(dest, face):
    """The titles of the pages this face sits under beneath the parent page, from the house's `<face title> under` line
    (`Requirements / Sign-off`); none when the house states no arrangement."""
    raw = dest["sections"].get("sign-off brief", {}).get(face["title"] + " under", ("",))[0]
    return [t.strip() for t in raw.split("/") if t.strip()] if given(raw) else []


def resolve_path(dest, titles):
    """[(title, path so far, page ID or '', the ID of its parent or '')] for each page of the path. A page is known when
    the Work records it, by that path, under that parent; once one is unknown, the ones below it are too (ADR 0038)."""
    parent = dest["sections"].get("sign-off brief", {}).get("parent page id", ("",))[0]
    out = []
    for i, title in enumerate(titles):
        path = " / ".join(titles[:i + 1])
        got = next((p for p in dest["pages"] if p[0].lower() == path.lower() and p[2] == parent), None) if parent else None
        out.append((title, path, got[1] if got else "", parent))
        parent = got[1] if got else ""
    return out


def section_is_set(dest, name):
    """A section is set when its Parent page ID and Space ID (the sign-off brief), or its Project key (a board), are."""
    sec = dest["sections"].get(name, {})
    need = ("parent page id", "space id") if name == "sign-off brief" else ("project key",)
    return all(given(sec.get(k, ("",))[0]) for k in need)


def landing_state(dest, name, kind):
    """(state, the Landed values, what it names, what the file now names) for one section of destinations.md. State is
    `none` with no Landed line, `proved` when the line names the parent (sign-off brief) or the project and item type
    (a board) that the files name now, else `stale` (ADR 0026). `kind` is the board's Feature item type."""
    sec = dest["sections"].get(name, {})
    get = lambda key: sec[key][0] if key in sec and given(sec[key][0]) else ""
    if not get("landed"):
        return "none", [], "", ""
    parts = [p.strip() for p in get("landed").split(",")]
    if name == "sign-off brief":
        got, now = next((p for p in parts if p.startswith("parent ")), ""), "parent " + get("parent page id")
    else:
        got, now = ", ".join(parts[1:3]), "%s, %s" % (get("project key"), kind)
    ok = got == now or (name != "sign-off brief" and not kind and parts[1:2] == [get("project key")])
    return ("proved" if ok else "stale"), parts, got, now


def read_hierarchy(text):
    """{"rows": [{"level", "business", "delivery", "line"}], "link": (type, line) or None}. The header row names
    the columns; a column that is absent is empty."""
    out, cols = {"rows": [], "link": None}, None
    for n, raw in enumerate(_blank_comments(text).replace("\r\n", "\n").split("\n"), 1):
        line = raw.strip()
        m = _KEYLINE.match(line)
        if m and m.group(1).lower() == "link":
            out["link"] = out["link"] or (m.group(2), n)
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cols is None:
                if cells and cells[0].lower() == "level":
                    cols = {c.lower(): i for i, c in enumerate(cells)}
            elif not set("".join(cells)) <= set("-: "):
                pick = lambda key: cells[cols[key]] if key in cols and cols[key] < len(cells) else ""
                out["rows"].append({"level": cells[0], "business": pick("business board"),
                                    "delivery": pick("delivery board"), "line": n})
    return out


def feature_types(house):
    """(item type on the business board, on the delivery board) for a Feature: the first Feature row, '' for none."""
    for row in read_hierarchy(house.text("hierarchy.md") or "")["rows"]:
        if row["level"].lower() == "feature":
            return row["business"], row["delivery"]
    return "", ""


def approval_of(house):
    """How a yes is given: `Approval` of a sign-off section that is set, else reply (there is then no page)."""
    dest = house.places()
    got = dest["sections"].get("sign-off brief", {}).get("approval", ("",))[0]
    return got if section_is_set(dest, "sign-off brief") and given(got) else "reply"


def goes_to(house):
    """Where the briefs go, as `status` says it."""
    dest = house.places()
    sec = dest["sections"].get
    parts, tracker = [], []
    if section_is_set(dest, "sign-off brief"):
        space = sec("sign-off brief", {}).get("space key", ("",))[0]
        parts.append("sign-off brief: page %s in %s%s" % (sec("sign-off brief")["parent page id"][0], space if given(space)
                     else "space " + sec("sign-off brief")["space id"][0], " (this Work's own)" if dest["own"] else ""))
    business, delivery = feature_types(house)
    for name, kind in (("business board", business), ("delivery board", delivery)):
        if section_is_set(dest, name):
            waits = name == "business board" and not (delivery and section_is_set(dest, "delivery board"))
            tracker.append("%s in %s%s" % (kind or "no item type", sec(name)["project key"][0],
                                           " (not used until the delivery board is set)" if waits else ""))
    if tracker:
        parts.append("tracker: " + ", ".join(tracker))
    return "; ".join(parts) or "outbox/ (no destination is set)"


# ==== helper/src/blocks.py ==================================================
"""Blocks: the tables and passages copied from the records into a brief, one method for each block kind.

_Brief builds the blocks of the sign-off brief and _HandoverBrief those of the handover brief (ADR 0018, 0022).
Every fact is copied; nothing here rewrites a sentence. Must not know: templates, slots, files or stamps. A
brief is given a store, a word list and, if its face is built for one record, that record.
"""

PRIORITY_ORDER = ("must", "should", "could", "wont")
# Mermaid reads these inside a quoted label as markup, so each is written as its entity code.
_MERMAID = {"#": "#35;", '"': "#quot;", "|": "#124;", "<": "#lt;", ">": "#gt;", "`": "#96;"}


def _esc(text):
    """Text typed in a record, made safe to put in a brief (ADR 0018): a pipe would end a table cell, angle
    brackets would be read as markup, and a leading # would start a heading. Everything else is as typed."""
    text = text.replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")
    return "\\" + text if text.startswith("#") else text


def _row(cells):
    return "| " + " | ".join(cells) + " |"


def _mermaid(text):
    return '"' + "".join(_MERMAID.get(c, c) for c in text) + '"'


class _Brief:
    """What the blocks are built from: the store, in the order ADR 0018 gives."""

    def __init__(self, store, words, record=None):
        self.store, self.L, self.words = store, words.get, words
        # What joins values inside one table cell: " / ", because Confluence shows <br> as text (ADR 0026, one text).
        self.br = " / "
        self.styles = ()  # the house's `Diagram style` lines: written into each diagram's source
        self.trace_kinds = KINDS
        recs = store["records"]
        self.work = next((r for r in recs if r["kind"] == "work"), _new_record("work", "", "work.md", 1))
        self.all = recs
        self.names = {}  # {ID or handle: the record's name}
        for r in recs:
            if r["id"]:
                self.names.setdefault(r["id"], r["name"])
        live = [r for r in recs if status_of(r) != "withdrawn"]
        rank = lambda r: PRIORITY_ORDER.index(value(r, "priority")) if value(r, "priority") in PRIORITY_ORDER else 4
        self.reqs = sorted([r for r in live if r["kind"] == "requirement"], key=rank)
        qs = [r for r in recs if r["kind"] == "question"]
        # A Question with a working answer and no answer is an assumption: listed with the assumptions.
        self.assumed = [q for q in qs if value(q, "working answer") and not value(q, "answer")]
        qs = [q for q in qs if q not in self.assumed]
        self.qs = [q for q in qs if not value(q, "answer")] + [q for q in qs if value(q, "answer")]
        self.flows = [r for r in live if r["kind"] == "flow"]

    def draft(self, rec):
        return status_of(rec) == "draft"

    def fixed(self, key, rec):
        """The label of a fixed value; a value outside the allowed ones is shown as written."""
        v = status_of(rec) if key == "status" else value(rec, key)
        return self.L(v) if v in FIXED[key] else _esc(v)

    def table(self, head, rows):
        if not rows:
            return [self.L("None recorded") + "."]
        return [_row(head), _row(["---"] * len(head))] + [_row(r) for r in rows]

    def rowtable(self, rows):
        if not rows:
            return []
        out = [_row(["**" + _esc(a) + "**", b]) for a, b in rows]
        return [out[0], _row(["---", "---"])] + out[1:]

    def example(self, ex):
        return _esc(ex["text"]) if ex["mark"] == "said" else "**%s:** %s" % (self.L("proposed"), _esc(ex["text"]))

    def people(self, depth):
        return self.rowtable([(p["role"], _esc(p["name"])) for p in self.work["people"]]) or [self.L("None recorded") + "."]

    def assumptions(self, depth):
        L = self.L
        out = ["- " + _esc(a["text"]) for a in self.work["assumptions"]]
        for q in self.assumed:
            who = "%s %s" % (L("To confirm with"), _esc(value(q, "owner"))) if value(q, "owner") else L("proposed")
            out.append("- %s (%s)" % (_esc(value(q, "working answer")), who))
        return out or [L("None recorded") + "."]

    def out_of_scope(self, depth):
        return ["- " + _esc(a["text"]) for a in self.work["out of scope"]] or [self.L("None recorded") + "."]

    def requirements(self, depth):
        L, rows = self.L, []
        for r in self.reqs:
            first = "**%s**" % _esc(r["name"]) + (" (%s)" % L("draft") if self.draft(r) else "")
            first += self.br + _esc(value(r, "statement"))
            for key in ("measure", "threshold"):
                if value(r, key):
                    first += self.br + "%s: %s" % (L(key), _esc(value(r, key)))
            rows.append([first, self.fixed("priority", r), _esc(value(r, "why")),
                         self.br.join(self.example(e) for e in r["examples"]), _esc(value(r, "priority notes"))])
        return self.table([L("Requirement"), L("Priority"), L("Why"), L("Example"), L("Notes")], rows)

    def cards(self, depth):
        L, out = self.L, []
        for r in self.reqs:
            rows = [(L("Requirement"), _esc(value(r, "statement"))), (L("Priority"), self.fixed("priority", r)),
                    (L("Status"), self.fixed("status", r))]
            rows += [(L(k), _esc(value(r, k))) for k in ("why", "measure", "threshold")]
            rows += [(L("Example"), self.example(e)) for e in r["examples"]]
            rows.append((L("Notes"), _esc(value(r, "priority notes"))))
            rows = [(a, b) for a, b in rows if b or a == L("Status")]
            out += ["#" * (depth + 1) + " " + _esc(r["name"]), ""] + self.rowtable(rows) + [""]
        return out or [L("None recorded") + "."]

    def diagram(self, flow):
        """The Mermaid text: every step once, every Go to once, labels quoted and escaped (ADR 0018)."""
        trigger, steps = value(flow, "trigger"), flow["steps"]
        ids = {}
        for i, s in enumerate(steps, 1):
            ids.setdefault(s["name"].lower(), "s%d" % i)
        out = [s for s in self.styles if s.startswith("%%{")] + ["flowchart TD"]
        out += ["    " + s for s in self.styles if not s.startswith("%%{")]
        if trigger:
            out.append("    start([%s])" % _mermaid(trigger))
        for i, s in enumerate(steps, 1):
            shape = "{%s}" if len(s["go to"]) > 1 else "[%s]" if s["go to"] else "([%s])"
            out.append("    s%d" % i + shape % _mermaid(s["name"]))
        if trigger and steps:
            out.append("    start --> s1")
        for i, s in enumerate(steps, 1):
            for g in s["go to"]:
                if g["to"].lower() in ids:
                    out.append("    s%d -->%s %s" % (i, "|%s|" % _mermaid(g["when"]) if g["when"] else "",
                                                    ids[g["to"].lower()]))
        return out

    def flow_head(self, fl, depth, in_words=False):
        """A flow's heading, overview and diagram. The diagram has its label before it (Confluence shows the source
        as code, ADR 0026) and, when `in_words`, its steps in words after it."""
        out = ["#" * (depth + 1) + " " + _esc(fl["name"]) + (" (%s)" % self.L("draft") if self.draft(fl) else ""), ""]
        if value(fl, "overview"):
            out += [_esc(value(fl, "overview")), ""]
        out += [self.L("Diagram source"), ""]
        out += ["```mermaid"] + self.diagram(fl) + ["```", ""]
        if in_words:
            out += ["**%s**" % self.L("Steps in words"), ""]
            for i, s in enumerate(fl["steps"], 1):
                where = "%s: %s" % (self.L("Go to"), "; ".join(_esc(g["text"]) for g in s["go to"])) if s["go to"] else self.L("End")
                out.append("%d. **%s**. %s." % (i, _esc(s["name"]), where))
            out.append("")
        return out

    def step_block(self, fl, i, s, depth):
        """A step's heading and row-label table. The first step of a flow also shows the flow's trigger."""
        L, rows = self.L, []
        if i == 0 and value(fl, "trigger"):
            rows.append((L("Trigger"), _esc(value(fl, "trigger"))))
        rows += [(L(k), _esc(value(s, k))) for k in STEP_FIELDS if value(s, k)]
        rows.append((L("Go to"), self.br.join(_esc(g["text"]) for g in s["go to"]) or L("End")))
        return ["#" * (depth + 2) + " " + _esc(s["name"]), ""] + self.rowtable(rows) + [""]

    def flow(self, depth, steps=False):
        out = []
        for fl in self.flows:
            out += self.flow_head(fl, depth, in_words=not steps)
            if steps:
                for i, s in enumerate(fl["steps"]):
                    out += self.step_block(fl, i, s, depth)
        return out

    def flow_with_steps(self, depth):
        return self.flow(depth, True)

    def question_cell(self, q):
        """The question, then on lines of their own its Context and the names of what it is About (never IDs)."""
        cell = _esc(q["name"])
        if value(q, "context"):
            cell += self.br + "%s: %s" % (self.L("Context"), _esc(value(q, "context")))
        names = [self.names[ref] for ref in q["about"] if ref in self.names]
        if names:
            cell += self.br + "%s: %s" % (self.L("About"), ", ".join(_esc(n) for n in names))
        return cell

    def questions(self, depth):
        L = self.L
        return self.table([L("Question"), L("Raised by"), L("Answer"), L("Answered by")],
                          [[self.question_cell(q), _esc(value(q, "raised by")),
                            _esc(value(q, "answer")) if value(q, "answer") else "**%s**" % L("Open"),
                            _esc(value(q, "answered by"))] for q in self.qs])

    def counts(self, depth):
        L = self.L
        open_q = sum(1 for q in self.qs if not value(q, "answer"))
        draft = sum(1 for r in self.reqs + self.flows if self.draft(r))
        proposed = sum(1 for r in self.reqs for e in r["examples"] if e["mark"] == "proposed")
        return [_row([L("Still open"), L("Count")]), _row(["---", "---"]),
                _row([L("Open questions"), str(open_q)]), _row([L("Draft records"), str(draft)]),
                _row([L("Proposed examples"), str(proposed)]), _row([L("Assumptions awaiting owner"), str(len(self.assumed))])]

    def approval(self, depth):
        L = self.L
        role = {}
        for p in self.work["people"]:
            role.setdefault(p["name"].lower(), p["role"])
        names = [n.strip() for n in value(self.work, "approvers").split(",") if n.strip()]
        version, said = version_of(self.store), {}
        for a in self.work["approvals"]:
            said[a["name"].lower()] = a  # the last one written is the one that counts
        rows = []
        for n in names:
            a = said.get(n.lower())
            here = a and approval_stands(self.store, a)  # an answer that no longer stands is not an answer to this one (ADR 0038)
            rows.append([_esc(n), _esc(role.get(n.lower(), "")), L(a["decision"]) if here else "",
                         _esc(a["date"]) if here else ""])
        return self.table([L("Approver"), L("Role"), L("Decision"), L("Date")], rows)

    def changes(self, depth):
        """What changed since the approval, in words (ADR 0034): one sentence and a table, the old wording beside the new,
        for the baseline that some approver approved, or nothing when there is none or nothing differs. No ID appears."""
        L, show = self.L, self.words.show
        base, approvals, found = changes_for(self.store)
        if not found:
            return []

        def cell(key, how_text):
            how, text = how_text
            if how == "confirm":
                return "**%s:** %s" % (L("proposed"), _esc(text))
            if how == "open":
                return "**%s**" % L("Open")
            if how == "withdrawn":
                return "%s: %s" % (L("Withdrawn"), _esc(text)) if text else L("Withdrawn")
            return show(text) if key in FIXED and text in FIXED[key] else _esc(text)
        word = {"changed": L("Changed"), "added": L("Added"), "withdrawn": L("Withdrawn")}
        rows = []
        for r in found:
            what = show(r["what"]) if r["set"] == "changed" else show(label(r["rec"]["kind"]))
            rows.append([word[r["set"]], "**%s**%s%s" % (_esc(r["rec"]["name"]), self.br, _esc(what)),
                         cell(r["key"], r["was"]), cell(r["key"], r["now"])])
        count = lambda s: len({_key(r["rec"]) for r in found if r["set"] == s})
        who = "; ".join("%s, %s" % (_esc(a["name"]), _esc(a["date"])) for a in approvals)
        return ["**%s %s** (%s): %d %s, %d %s, %d %s." % (
            L("Since the approval of"), _esc(base["name"]), who, count("changed"), word["changed"].lower(), count("added"),
            word["added"].lower(), count("withdrawn"), word["withdrawn"].lower()), ""] + self.table(
                [L("Change"), L("What"), L("Was"), L("Now")], rows)

    def trace(self, depth):
        L, rows = self.L, []
        for kind in self.trace_kinds:
            for r in self.all:
                if r["kind"] != kind:
                    continue
                shown = L(label(kind)) + (" (%s)" % _esc(self.words.show(value(r, "category")))
                                          if value(r, "category") else "")
                if kind == "question":
                    status = L("Answered") if value(r, "answer") else L("Assumed") if r in self.assumed else L("Open")
                elif kind == "observed":
                    status = L(standing_of(r))
                else:
                    status = self.fixed("status", r)
                rows.append([r["id"], shown, _esc(r["name"]), _esc(value(r, "feature")), status,
                             _esc(value(r, "raised by" if kind in ("question", "observed") else "source")), _esc(value(r, "about"))])
        return self.table([L("ID"), L("Kind"), L("Name"), L("Feature"), L("Status"), L("Source"), L("About")], rows)

    def block(self, kind, depth):
        name = {"out of scope": "out_of_scope", "requirement cards": "cards", "flow with steps": "flow_with_steps"}
        return getattr(self, name.get(kind, kind))(depth)


class _HandoverBrief(_Brief):
    """The blocks of the handover brief for one Feature (ADR 0022). Everything is built for `feature`."""

    def __init__(self, store, words, feature):
        super().__init__(store, words, feature)
        self.feature = feature
        recs = self.all
        by = {}
        for r in recs:
            if r["id"]:
                by.setdefault(r["id"].lower(), r)
        rank = lambda r: PRIORITY_ORDER.index(value(r, "priority")) if value(r, "priority") in PRIORITY_ORDER else 4
        # Every requirement that names the feature, withdrawn ones too (only the trace shows those).
        self.of = [r for r in recs if r["kind"] == "requirement"
                   and any(feature_named(recs, p) is feature for p in feature_parts(r))]
        self.reqs = sorted([r for r in self.of if status_of(r) != "withdrawn"], key=rank)
        self.flows = [by[x.lower()] for x in feature["flows"] if x.lower() in by and by[x.lower()]["kind"] == "flow"]
        mine = {r["id"].lower() for r in self.of + self.flows + [feature, self.work] if r["id"]}
        self.fq = [q for q in recs if q["kind"] == "question" and (not q["about"] or {a.lower() for a in q["about"]} & mine)]
        self.listed = [i["text"].lower() for i in feature["flow steps"]]

    def block(self, kind, depth):
        if kind in ("people", "out of scope"):
            return super().block(kind, depth)
        return getattr(self, "h_" + kind.replace(" ", "_"))(depth)

    def steps_of(self, fl):
        """[(position in the flow, step)] of the feature's steps in this flow: its listed ones, or all of them."""
        return [(i, s) for i, s in enumerate(fl["steps"]) if not self.listed or s["name"].lower() in self.listed]

    def h_version(self, depth):
        L, f, work = self.L, self.feature, self.work
        origin = feature_named(self.all, _parts(value(f, "sliced from"))[0]) if _parts(value(f, "sliced from")) else None
        base = self.store.get("baseline")
        parent = _parts(value(f, "sliced from"))
        held = None
        if origin is None and base and len(parent) == 1:
            # A baseline holds only what was confirmed, so a withdrawn original is not in it: its name is in the manifest.
            held = next((x for k, x in base["names"].items() if parent[0].lower() in (k, x[1].strip().lower())), None)
        if held:
            sliced = "%s %s" % (_esc(held[0]), _esc(held[1]))
        else:
            sliced = (" ".join(x for x in (origin["id"], _esc(origin["name"])) if x) if origin else _esc(value(f, "sliced from")))
            if origin and value(origin, "tracker") and kept_original(self.store, origin):  # the item its original still has
                sliced += " (%s %s)" % (L("Tracker item"), _esc(value(origin, "tracker")))
        version, said, shown = version_of(self.store), {}, []
        for a in work["approvals"]:
            said[a["name"].lower()] = a  # the last one written is the one that counts
        for n in _parts(value(work, "approvers")):
            a = said.get(n.lower())
            if a and approval_stands(self.store, a):
                there = approved_baseline(self.store, a)  # an approval of earlier records says which baseline it was of
                shown.append("%s: %s, %s%s" % (_esc(n), L(a["decision"]), _esc(a["date"]), ", %s %s" % (
                    L("Baseline"), _esc(there["name"])) if there and _approved_version(self.store, a) != version else ""))
            else:
                shown.append("%s: %s" % (_esc(n), L("Not yet approved")))
        rows = [(L("Feature"), _esc(f["id"])), (L("Status"), self.fixed("status", f)), (L("Sliced from"), sliced),
                (L("Tracker item"), _esc(value(f, "tracker"))),
                (L("Business item"), _esc(value(f, "business item"))), (L("Work"), _esc(work["name"])),
                (L("Baseline"), "%s, frozen %s" % (_esc(base["name"]), base["date"]) if base else L("No baseline")),
                (L("Approval"), self.br.join(shown) or L("Not yet approved")), (L("Changed since approval"), self.changed_here()),
                (L("Records version"), version)]
        return self.rowtable([(a, b) for a, b in rows if b])

    def changed_here(self):
        """The `Changed since approval` cell, only when an approval is read against an earlier baseline: `None in this
        Feature`, or one line for each requirement or flow of this Feature that differs and is not grouping (ADR 0038)."""
        base, _, found = changes_for(self.store)
        if not base:
            return ""
        mine = {r["id"] for r in self.of + self.flows if r["id"]}
        lines = []
        for row in found:
            line = "%s: %s" % ({"changed": self.L("Changed"), "added": self.L("Added"), "withdrawn": self.L("Withdrawn")}[row["set"]],
                               " ".join(x for x in (row["rec"]["id"], _esc(row["rec"]["name"])) if x))
            if row["rec"]["id"] in mine and line not in lines:
                lines.append(line)
        return self.br.join(lines) or self.L("None in this Feature")

    def h_glossary(self, depth):
        L = self.L
        return self.table([L("Word"), L("Meaning")], [[_esc(g["word"]), _esc(g["meaning"])] for g in self.work["glossary"]])

    def h_actors(self, depth):
        L, seen = self.L, {}
        for fl in self.flows:
            for _, s in self.steps_of(fl):
                for who in _parts(value(s, "stakeholders")):
                    seen.setdefault(who.lower(), [who, []])[1].append(s["name"])
        return self.table([L("Who"), L("Takes part in")],
                          [[_esc(w), self.br.join(_esc(x) for x in steps)] for w, steps in seen.values()])

    def h_feature_requirements(self, depth):
        L, rows = self.L, []
        for r in self.reqs:
            name = "**%s**" % _esc(r["name"]) + (" (%s)" % L("draft") if self.draft(r) else "")
            rows.append([r["id"], name, _esc(value(r, "statement")), _esc(self.words.show(value(r, "category"))),
                         self.fixed("priority", r) if value(r, "priority") else "", _esc(value(r, "why")),
                         _esc(value(r, "priority notes"))])
        return self.table([L("ID"), L("Requirement"), L("Statement"), L("Category"), L("Priority"), L("Why"), L("Notes")], rows)

    def h_measures(self, depth):
        L = self.L
        return self.table([L("ID"), L("Measure"), L("Threshold")],
                          [[r["id"], _esc(value(r, "measure")), _esc(value(r, "threshold"))]
                           for r in self.reqs if value(r, "measure") or value(r, "threshold")])

    def h_examples(self, depth):
        L, rows = self.L, []
        for r in self.reqs:
            if not r["examples"]:
                rows.append([r["id"], "", L("None recorded"), ""])
            for n, e in enumerate(r["examples"], 1):
                rows.append([r["id"], str(n), _esc(e["text"]), L(e["mark"])])
        return self.table([L("ID"), L("No."), L("Example"), L("Standing")], rows)

    def h_feature_flow(self, depth):
        L, out = self.L, []
        for fl in self.flows:
            out += self.flow_head(fl, depth)
            mine = self.steps_of(fl)
            if self.listed and mine:
                out += ["**%s:** %s" % (L("Steps delivered here"), _esc("; ".join(s["name"] for _, s in mine))), ""]
            for i, s in mine:
                out += self.step_block(fl, i, s, depth)
        return out

    def h_decisions(self, depth):
        L = self.L
        return self.table([L("ID"), L("Question"), L("Answer"), L("Answered by"), L("About")],
                          [[q["id"], _esc(q["name"]), _esc(value(q, "answer")), _esc(value(q, "answered by")),
                            _esc(value(q, "about"))] for q in self.fq if value(q, "answer")])

    def h_other_features(self, depth):
        return ["- " + " ".join(x for x in (r["id"], _esc(r["name"])) if x) + (" (%s)" % self.L("draft") if self.draft(r) else "")
                for r in live_features(self.store) if r is not self.feature] \
            or [self.L("None recorded") + "."]

    def h_plain_assumptions(self, depth):
        return ["- " + _esc(a["text"]) for a in self.work["assumptions"]] or [self.L("None recorded") + "."]

    def h_feature_questions(self, depth):
        L, rows = self.L, []
        open_ = [q for q in self.fq if not value(q, "answer")]
        for q in [x for x in open_ if not value(x, "working answer")] + [x for x in open_ if value(x, "working answer")]:
            rows.append([q["id"], _esc(q["name"]), _esc(value(q, "about")),
                         L("Not blocking") if value(q, "working answer") else "**%s**" % L("Blocking"),
                         _esc(value(q, "working answer")), _esc(value(q, "owner") or value(q, "raised by"))])
        return self.table([L("ID"), L("Question"), L("About"), L("Standing"), L("Meanwhile"), L("Owner")], rows)

    def h_observed(self, depth):
        """What the present system was seen to do and what the business has said of it, for this feature (ADR 0035): the
        Observed records, not withdrawn, whose `About` names the Feature, one of its requirements or one of its Flows.
        Unconfirmed first, then the rest. `Seen in` is left out: the brief carries no repository detail."""
        L, by = self.L, {}
        mine = {x["id"].lower() for x in [self.feature] + self.reqs + self.flows if x["id"]}
        found = [r for r in self.all if r["kind"] == "observed" and standing_of(r) != "withdrawn" and {a.lower() for a in r["about"]} & mine]
        reqs = {x["id"].lower(): x for x in self.all if x["kind"] == "requirement" and x["id"]}
        rows = []
        for r in sorted(found, key=lambda r: standing_of(r) != "unconfirmed"):
            standing = standing_of(r)
            named = value(r, "requirement")
            there = reqs.get(named.lower()) or next((x for x in self.all if x["kind"] == "requirement"
                                                     and x["name"].strip().lower() == named.strip().lower()), None)
            shown = L(standing) if standing != "unconfirmed" else "**%s**" % L(standing)
            if named and standing in ("intended", "defect"):
                shown += ": " + _esc((there or {}).get("id") or named)
            rows.append([r["id"], "**%s**%s%s" % (_esc(r["name"]), self.br, _esc(value(r, "behaviour"))), shown,
                         _esc(value(r, "verdict by") or value(r, "owner") or value(r, "raised by"))])
        return self.table([L("ID"), L("Behaviour"), L("Standing"), L("Owner")], rows) if rows else []

    def h_left_to_engineering(self, depth):
        return ["- %s (%s)" % (_esc(i["text"]), r["id"] or _esc(r["name"])) for r in self.reqs for i in r["left to engineering"]] \
            or [self.L("None recorded") + "."]

    def h_feature_trace(self, depth):
        L, rows = self.L, []

        def row(r, kind, status, source):
            rows.append([r["id"], kind, _esc(r["name"]), status, _esc(source)])
        row(self.work, L("Work"), self.fixed("status", self.work), "")
        row(self.feature, L("Feature"), self.fixed("status", self.feature), "")
        for r in self.of:
            kind = L("Requirement") + (" (%s)" % _esc(self.words.show(value(r, "category"))) if value(r, "category") else "")
            row(r, kind, self.fixed("status", r), value(r, "source"))
        for q in self.fq:
            row(q, L("Question"), L("Answered") if value(q, "answer") else L("Assumed") if value(q, "working answer") else L("Open"),
                value(q, "raised by"))
        for fl in self.flows:
            row(fl, L("Flow"), self.fixed("status", fl), value(fl, "source"))
        return self.table([L("ID"), L("Kind"), L("Name"), L("Status"), L("Source")], rows)


class _ScopeBrief(_Brief):
    """The blocks of the Scope brief (ADR 0029). Six are the sign-off brief's; five are its own. None reads the
    size: a block with nothing to show prints nothing, and a section whose blocks all print nothing is left out. Its trace
    has no Observed record: nobody agrees the scope by agreeing what the present system does (ADR 0038)."""

    def __init__(self, store, words, record=None):
        super().__init__(store, words, record)
        self.trace_kinds = tuple(k for k in KINDS if k != "observed")

    def block(self, kind, depth):
        if kind in SCOPE_NEW:
            return getattr(self, "s_" + kind.replace(" ", "_"))(depth)
        return super().block(kind, depth)

    def mark(self, rec):
        """` (Draft)` after a draft record's name, else nothing."""
        return " (%s)" % self.L("draft") if self.draft(rec) else ""

    def live_features(self):
        return live_features(self.store)

    def s_top_requirements(self, depth):
        L = self.L
        rows = [["**%s**%s%s%s" % (_esc(r["name"]), self.mark(r), self.br, _esc(value(r, "statement"))),
                 self.fixed("priority", r), _esc(value(r, "why"))]
                for r in self.reqs if value(r, "category") == "business"]
        return self.table([L("Requirement"), L("Priority"), L("Why")], rows)

    def s_features(self, depth):
        L = self.L
        rows = [["**%s**%s" % (_esc(f["name"]), self.mark(f)), _esc(value(f, "intent")), str(len(_feature_reqs(self.store, f)))]
                for f in self.live_features()]
        return self.table([L("Feature"), L("Intent"), L("Requirements")], rows)

    def s_feature_map(self, depth):
        L, live, out = self.L, self.live_features(), []
        if not any(f["flows"] for f in live):
            return []
        for fl in self.flows:
            rows = []
            for s in fl["steps"]:
                on = [_esc(f["name"]) + self.mark(f) for f in live
                      if fl["id"] and fl["id"].lower() in [x.lower() for x in f["flows"]]
                      and (not f["flow steps"] or s["name"].lower() in [i["text"].lower() for i in f["flow steps"]])]
                rows.append([_esc(s["name"]), self.br.join(on) or L("None recorded")])
            out += ["#" * (depth + 1) + " " + _esc(fl["name"]), ""] + self.table([L("Step"), L("Feature")], rows) + [""]
        return out[:-1]

    def s_stakeholders(self, depth):
        rows = []
        for item in self.work["stakeholders"]:
            who, _, rest = item["text"].partition(":")
            say, _, needs = rest.partition(",")
            rows.append([_esc(who.strip()), _esc(say.strip()), _esc(needs.strip())])
        return self.table([self.L("Stakeholder"), self.L("Say"), self.L("Needs")], rows) if rows else []

    def s_tolerances(self, depth):
        return ["- " + _esc(t["text"]) for t in self.work["tolerances"]]


class _DeliveryBrief(_Brief):
    """The blocks of the Delivery plan (ADR 0031): two are the sign-off brief's, five are its own, drawn from the
    figures forecast_for works out. Nothing here works out a date."""

    def __init__(self, store, words, record=None):
        super().__init__(store, words, record)
        self.fc = forecast_for(store)

    def block(self, kind, depth):
        if kind in DELIVERY_NEW:
            return getattr(self, "d_" + kind.replace(" ", "_"))(depth) if self.fc["ok"] else []
        return super().block(kind, depth)

    def range(self, row):
        """One date when the fastest and the slowest pace end in the same week, as one velocity figure always does."""
        return show_date(row["early"]) if row["early"] == row["late"] else "%s to %s" % (show_date(row["early"]), show_date(row["late"]))

    def against(self, key):
        return self.L({"earlier": "Earlier than the forecast", "within": "Within the forecast", "later": "Later than the forecast"}[key])

    def name_of(self, row):
        return _esc(row["feature"]["name"]) + (" (%s)" % self.L("draft") if self.draft(row["feature"]) else "")

    def d_forecast_summary(self, depth):
        fc, L, rows = self.fc, self.L, self.fc["rows"]
        out = [(L("Forecast finish"), self.range({"early": rows[-1]["early"], "late": rows[-1]["late"]}))]
        if fc["read"]:
            out += [(L("Features finished"), "%d of %d" % (fc["finished"], len(rows))),
                    (L("Pace date"), "%s (%s)" % (show_date(fc["last"][0]), self.against(fc["last"][1])) if fc["last"] else L("Too early to say")),
                    (L("Actuals read"), show_date(fc["read"]) + (", " + _esc(fc["read_rest"]) if fc["read_rest"] else ""))]
        return self.rowtable(out)

    def standing(self, row):
        L = self.L
        if row["finished"]:
            return "%s %s (%s)" % (L("Finished"), show_date(row["finished"]), self.against(row["against"]))
        got = ["%s %s" % (L("Started"), show_date(row["started"]))] if row["started"] else []
        got += ["%d of %d %s" % (row["items"][0], row["items"][1], L("items done"))] if row["items"] else []
        return ", ".join(got) or L("Not started")

    def d_forecast(self, depth):
        L, fc = self.L, self.fc
        rows = [[self.name_of(r), self.range(r), self.standing(r),
                 show_date(r["pace"]) if r["pace"] else L("Too early to say") if fc["read"] and not r["finished"] and not fc["pace"] else ""]
                for r in fc["rows"]]
        return self.table([L("Feature"), L("Forecast finish"), L("Standing"), L("Pace date")], rows)

    def d_timeline(self, depth):
        fc, L = self.fc, self.L
        clean = lambda text: text.replace(":", ",").replace(";", ",").replace("#", "")
        out = ["```mermaid"] + [s for s in self.styles if s.startswith("%%{")] + ["gantt", "    dateFormat YYYY-MM-DD", "    axisFormat %d %b", "    section " + L("Forecast")]
        before = fc["start"]
        for i, r in enumerate(fc["rows"], 1):
            out.append("    %s :f%d, %s, %s" % (clean(r["feature"]["name"]), i, before, r["late"]))
            before = r["early"]
        done = []
        for i, r in enumerate(fc["rows"], 1):
            name = clean(r["feature"]["name"])
            if r["finished"] and r["started"]:
                done.append("    %s :done, a%d, %s, %s" % (name, i, r["started"], r["finished"]))
            elif r["finished"]:
                done.append("    %s :milestone, a%d, %s, 0d" % (name, i, r["finished"]))
            elif r["started"] and fc["read"]:
                done.append("    %s :active, a%d, %s, %s" % (name, i, r["started"], fc["read"]))
        if fc["read"] and done:
            out += ["    section " + L("Delivered")] + done
        return [L("Diagram source"), ""] + out + ["```"]

    def d_delivery_basis(self, depth):
        fc, L = self.fc, self.L
        out = [(L("Start"), show_date(fc["start"])), (L("Period"), "%d %s" % (fc["weeks"], L("week") if fc["weeks"] == 1 else L("weeks"))),
               (L("Velocity"), "%s %s %s" % (fc["velocity"], L("Feature") if fc["low"] == fc["high"] == 1 else L("Features"), L("a period")))]
        if fc["shown_pace"]:
            out.append((L("Pace so far"), "%s %s %s, over %d days" % (fc["shown_pace"], L("Features"), L("a period"), fc["days"])))
        elif fc["read"]:
            out.append((L("Pace so far"), L("Too early to say")))
        out.append((L("Order"), self.br.join("%d. %s" % (i, _esc(r["feature"]["name"])) for i, r in enumerate(fc["rows"], 1))))
        return self.rowtable(out)

    def d_feature_items(self, depth):
        L = self.L
        return self.table([L("ID"), L("Feature"), L("Status"), L("Tracker item")],
                          [[r["feature"]["id"], _esc(r["feature"]["name"]), self.fixed("status", r["feature"]),
                            _esc(value(r["feature"], "tracker"))] for r in self.fc["rows"]])


# ==== helper/src/faces.py ===================================================
"""Faces: what a brief is made of, and how a template and the records make its skeleton (ADR 0018, 0022).

Owns the face descriptors (FACES), the template reader (_expand) and build_face. A face is data: its name, template,
output file, the record it is built for, its lints and the jobs, blocks and values its template may use. A new
face is a new descriptor. Must not know: where a brief is written, how it is checked, or which command makes it.
"""

JOBS = ("ask", "change", "scope", "rules", "flow", "open", "wait", "approve", "trace")
BLOCKS = ("people", "assumptions", "out of scope", "requirements", "requirement cards", "flow",
          "flow with steps", "questions", "counts", "approval", "changes", "trace")
# The handover brief (ADR 0022, 0035): twelve jobs, fourteen block kinds of its own beside `people` and `out of scope`.
HANDOVER_JOBS = ("version", "intent", "words", "actors", "rules", "examples", "flow", "scope", "open", "yours", "ask", "trace")
HANDOVER_BLOCKS = ("version", "glossary", "actors", "feature requirements", "measures", "examples", "feature flow",
                   "decisions", "other features", "plain assumptions", "feature questions", "left to engineering",
                   "feature trace", "observed", "people", "out of scope")
# The Scope brief (ADR 0029): nine jobs, five block kinds of its own beside six the sign-off brief has.
SCOPE_JOBS = ("goal", "needs", "features", "scope", "people", "limits", "open", "agree", "trace")
SCOPE_NEW = ("top requirements", "features", "feature map", "stakeholders", "tolerances")
SCOPE_BLOCKS = ("people", "assumptions", "out of scope", "questions", "counts", "trace") + SCOPE_NEW
# The Delivery plan (ADR 0031): six jobs, five block kinds of its own beside `questions` and `assumptions`.
DELIVERY_JOBS = ("answer", "features", "timeline", "basis", "risk", "trace")
DELIVERY_NEW = ("forecast summary", "forecast", "timeline", "delivery basis", "feature items")
DELIVERY_BLOCKS = ("questions", "assumptions") + DELIVERY_NEW
WORK_VALUES = ("name", "goal", "tracker")
FEATURE_VALUES = ("name", "intent", "tracker")
# A brief that is more than a quarter over its aim of 3,000 tokens (four characters to a token) is too large to hand over.
HANDOVER_MAX_CHARS = 15000

def _delivery_needs(store):
    """None when the Delivery plan can be made, else the sentence that says why not and which line to add (ADR 0031)."""
    fc = forecast_for(store)
    if fc["ok"]:
        return None
    if not any(r["kind"] == "feature" and status_of(r) != "withdrawn" for r in store["records"]):
        return ("a forecast counts Features, and there is no Feature record that is not withdrawn, so nothing was written. "
                "Fix: write one (see the shape: %s --shape feature), or slice the requirements, then run: %s bundle delivery%s"
                % (CHECK, BA, FOLDER))
    said = {i["key"]: i for i in fc["issues"] if i["section"] == "delivery"}
    why = []
    for key, form in (("Start", START_FORM), ("Velocity", VELOCITY_FORM)):
        if form not in fc["needs"]:
            continue
        why.append("Line %d says '%s', which it cannot read. Change it to: %s" % (said[key]["line"], said[key]["value"], form)
                   if key in said else "There is no '%s' line under '### Delivery' on the Work. Add under it: %s" % (key, form))
    return "the forecast cannot be worked out, so nothing was written. %s Then run: %s bundle delivery%s" % (" ".join(why), BA, FOLDER)


# The faces ba makes (ADR 0027). A face is data; bundle, check and status go through it and never ask which face
# it is. A third face is a new entry here, a class of blocks in blocks.py if it needs its own, and nothing else.
#
#   name           what `ba bundle <name>` is given; title, what a person calls it; word, the row of the word list that
#                  names it (the title of the page it is sent as)
#   brief          the class in blocks.py that builds its blocks
#   for            the kind of record it is made for ("feature"), or None when it is made for the whole work
#   usage          the command as a person types it, after `python3 ba.py`, and target, what follows it to name the
#                  record it is made for (a folder may follow that)
#   file           where it is written in the workspace; {id} is the ID of the record it is made for
#   on_disk        matches the file names in faces/ that are this face; group 1 is the ID when it is made for a record
#   template       the template's file name; with `forms`, a named form is signoff-<form>.md and this is the default
#   templates      matches the file names of its templates in templates/
#   forms          True when a template may be chosen by form (--form, the Work's Sign-off form line)
#   jobs, blocks   the {job: ...} and {block: ...} words its template may use
#   values         what a template may carry: {"work": names, "feature": names} for {work: ...} and {feature: ...}
#   lints          names of the extra checks `check` makes on it, from LINTS in facecheck.py
#   needs          a function from a store to None, or the sentence that says why the face cannot be made (it is then not
#                  written and bundle exits 2); with `baselines` False, it is made from the working records only
#   apart          the block kinds built from a section the records version leaves out, so a change there does not change
#                  the version: a brief that differs only inside them is behind, and `check` says to make it again
#   max_chars      the size past which it is too large to hand over, or None
#   ids_why        what check says when a passage names a record by its ID
#   form_hint      what check adds when the brief has no stamp; no_template, no_template_fix and
#                  missing_template_fix word the findings about a template that is not there
FACES = {
    "signoff": {
        "name": "signoff", "title": "sign-off brief", "word": "Sign-off brief",
        "apart": (), "needs": None, "baselines": True, "brief": _Brief, "for": None, "usage": "bundle signoff", "target": "",
        "file": "faces/signoff.md", "on_disk": re.compile(r"^signoff\.md$"),
        "template": "signoff-moscow.md", "templates": re.compile(r"^signoff(-.+)?\.md$"), "forms": True,
        "jobs": JOBS, "blocks": BLOCKS, "values": {"work": WORK_VALUES},
        "lints": (), "max_chars": None,
        "ids_why": "Record IDs belong in the trace table at the end and nowhere else.",
        "form_hint": " The form is the Work's 'Sign-off form' line, else moscow; add --form <name> for another.",
        "no_template": "There is no template '{name}' in the house or the shipped templates. The forms there are: {forms}.",
        "no_template_fix": "run it with --form <one of those>{line}",
        "missing_template_fix": "Run: {bundle} --form <one of: {forms}>   It makes the brief again, carries the passages "
                                "you wrote into it, and keeps a copy of this one in backup/.",
    },
    "handover": {
        "name": "handover", "title": "handover brief", "word": "Handover brief",
        "apart": (), "needs": None, "baselines": True, "brief": _HandoverBrief, "for": "feature", "usage": "bundle handover",
        "target": " <feature>",
        "file": "faces/handover-{id}.md", "on_disk": re.compile(r"^handover-(.+)\.md$"),
        "template": "handover.md", "templates": re.compile(r"^handover\.md$"), "forms": False,
        "jobs": HANDOVER_JOBS, "blocks": HANDOVER_BLOCKS,
        "values": {"work": WORK_VALUES, "feature": FEATURE_VALUES},
        "lints": ("size",), "max_chars": HANDOVER_MAX_CHARS,
        "ids_why": "Record IDs belong in the tables ba makes from the records. A passage names a record by its name.",
        "form_hint": "",
        "no_template": "there is no template '{name}' in the house or the shipped house.",
        "no_template_fix": "add it to the house's templates/ folder.",
        "missing_template_fix": "Add a template with that name to the house's templates/ folder, or make the brief "
                                "again with the shipped house: {again}",
    },
    "scope": {
        "name": "scope", "title": "scope brief", "word": "Scope brief",
        "apart": (), "needs": None, "baselines": True, "brief": _ScopeBrief, "for": None,
        "usage": "bundle scope", "target": "",
        "file": "faces/scope.md", "on_disk": re.compile(r"^scope\.md$"),
        "template": "scope.md", "templates": re.compile(r"^scope\.md$"), "forms": False,
        "jobs": SCOPE_JOBS, "blocks": SCOPE_BLOCKS, "values": {"work": WORK_VALUES},
        "lints": (), "max_chars": None,
        "ids_why": "Record IDs belong in the trace table at the end and nowhere else.",
        "form_hint": "",
        "no_template": "there is no template '{name}' in the house or the shipped house.",
        "no_template_fix": "add it to the house's templates/ folder.",
        "missing_template_fix": "Add a template with that name to the house's templates/ folder, or make the brief "
                                "again with the shipped house: {again}",
    },
    "delivery": {
        "name": "delivery", "title": "delivery plan", "word": "Delivery plan", "needs": _delivery_needs, "baselines": False,
        "apart": ("forecast summary", "forecast", "timeline", "delivery basis", "feature items"),
        "brief": _DeliveryBrief, "for": None, "usage": "bundle delivery", "target": "",
        "file": "faces/delivery.md", "on_disk": re.compile(r"^delivery\.md$"),
        "template": "delivery.md", "templates": re.compile(r"^delivery\.md$"), "forms": False,
        "jobs": DELIVERY_JOBS, "blocks": DELIVERY_BLOCKS, "values": {"work": WORK_VALUES},
        "lints": ("dates",), "max_chars": None,
        "ids_why": "Record IDs belong in the trace table at the end and nowhere else.",
        "form_hint": "",
        "no_template": "there is no template '{name}' in the house or the shipped house.",
        "no_template_fix": "add it to the house's templates/ folder.",
        "missing_template_fix": "Add a template with that name to the house's templates/ folder, or make the brief "
                                "again with the shipped house: {again}",
    },
}


def face_file(face, record=None):
    """Where a face is written in the workspace, relative to it."""
    return face["file"].format(id=record["id"] if record is not None else "")


def shown_values(record, names):
    """The values a template may carry from a record, made safe to put in a brief."""
    return {k: _esc(record["name"] if k == "name" else value(record, k)) for k in names}


_DIRECTIVE = re.compile(r"^\{(job|omit|block):\s*(.*?)\s*\}$")
_SLOT = re.compile(r"^>\s*\{slot:\s*up to (\d+) words,\s*from (.+?)\s*\}$")
_WORK_REF = re.compile(r"\{work:\s*(\w+)\s*\}")
_LABEL_REF = re.compile(r"\{([^{}:]+)\}")
# How far over a slot's stated figure a passage may run before check says so (ADR 0018): a quarter.
# The writer is a language model, which cannot count words exactly; the figure in the slot is its target.
SLOT_OVER = (5, 4)
# Both at once, so a brace inside a value carried from the Work is never read as a label.
_FEATURE_REF = re.compile(r"\{feature:\s*(\w+)\s*\}")
_REF = re.compile(_WORK_REF.pattern + "|" + _FEATURE_REF.pattern + "|" + _LABEL_REF.pattern)
# A brief names what it was made from: the working records' version, or a baseline and the version it froze.
_STAMP = re.compile(r"^Made from (?:records version (?P<v>[0-9a-f]{8})|baseline (?P<b>\S+) \(records version (?P<bv>[0-9a-f]{8})\)), "
                    r"template (?P<t>.+?), (?P<n>\d+) findings?\.(?: Waived at freezing: (?P<w>.*))?$")
_ID_IN_TEXT = re.compile(r"\b(?:W|R|Q|F|FE|OB)-\d+\b")


def _expand(brief, face, record, words, template, here):
    """Read the template line by line. Returns (items, slots, sections, problems, omitted).

    items     [(text, where it came from)]: the face before it is tidied. Where from is a slot number,
              or "fixed" (the template's own text), "work" (a line with a value from the Work), "block" or
              "approval" (the approval block, which changes when an approval is recorded)
    slots     [{section, cap, header}]
    sections  [{line, heading, job}]: the '## ' sections, in order
    omitted   {job: (the reason, '' when none is given; its line; the text of the directive)}: the jobs left out

    A section with a block and nothing to show in any of them, and no slot, is left out, heading included
    (ADR 0018). Trace and approval are never empty.
    """
    problems, items, slots, sections, depth, i, omitted = [], [], [], [], 1, 0, {}
    work = shown_values(brief.work, face["values"]["work"])
    feature = shown_values(record, face["values"][face["for"]]) if record is not None else None
    feature_names = face["values"].get("feature")
    tpl = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), template, flags=re.S).split("\n")

    def bad(n, key, val, allowed, write, why=None):
        problems.append(_problem("bad-value", here, n, key=key, value=val, allowed=list(allowed),
                                 why=why or "It takes one of: %s." % ", ".join(allowed), write=write))

    while i < len(tpl):
        n, raw = i + 1, tpl[i].rstrip()
        line = raw.strip()
        i += 1
        d = _DIRECTIVE.match(line)
        if d:
            kind, arg = d.group(1), d.group(2)
            if kind == "job":
                if arg not in face["jobs"]:
                    bad(n, "job", arg, face["jobs"], "{job: <one of %s>}" % ", ".join(face["jobs"]))
                if sections:
                    sections[-1]["job"] = arg
            elif kind == "omit":
                tag, _, rest = arg.partition(",")
                tag, because = tag.strip(), re.match(r"^because\s+(\S.*)$", rest.strip())
                omitted.setdefault(tag, (because.group(1) if because else "", n, arg))
                if tag not in face["jobs"]:
                    bad(n, "job", tag, face["jobs"], "{omit: <one of %s>, because <reason>}" % ", ".join(face["jobs"]))
            elif arg.lower() not in face["blocks"]:
                bad(n, "block", arg, face["blocks"], "{block: <one of %s>}" % ", ".join(face["blocks"]))
            else:
                shown = brief.block(arg.lower(), depth)
                if sections:
                    sections[-1]["kinds"].append(arg.lower())
                tag = "approval" if arg.lower() == "approval" else "apart" if arg.lower() in face["apart"] else "block"
                items += [("", "block")] + [(t, tag) for t in shown] + [("", "block")]
                if sections:
                    sections[-1]["blocks"] += 1
                    sections[-1]["shown"] += 1 if shown else 0
            continue
        if line.startswith("> {slot:"):
            slots.append({"section": sections[-1] if sections else {"job": None, "heading": ""}, "cap": None,
                          "header": line, "line": n})
            m = _SLOT.match(line)
            if m:
                slots[-1]["cap"] = int(m.group(1))
            else:
                problems.append(_problem(
                    "bad-value", here, n, key="Slot", value=line, allowed=[],
                    why="A slot says how many words it takes and what it draws on.",
                    write="> {slot: up to <number> words, from <the records it draws on>}"))
            items.append((raw, len(slots) - 1))
            if sections:
                sections[-1]["slots"] += 1
            while i < len(tpl) and tpl[i].lstrip().startswith(">"):
                items.append((tpl[i].rstrip(), len(slots) - 1))
                i += 1
            slots[-1]["last"] = i
            continue
        if not raw.startswith("> "):
            keys = [k.lower() for k in _WORK_REF.findall(raw)]
            fkeys = [k.lower() for k in _FEATURE_REF.findall(raw)]
            for key in keys:
                if key not in face["values"]["work"]:
                    bad(n, "work", key, face["values"]["work"], "{work: <one of %s>}" % ", ".join(face["values"]["work"]))
            for key in fkeys:
                if feature_names is None:
                    bad(n, "feature", key, (), "the line without {feature: %s}" % key,
                        why="A {feature: ...} value belongs to the handover brief, which is made for one Feature.")
                elif key not in feature_names:
                    bad(n, "feature", key, feature_names, "{feature: <one of %s>}" % ", ".join(feature_names))
            if any(key in work and not work[key] for key in keys) or \
                    any(feature and key in feature and not feature[key] for key in fkeys):
                continue  # a line about a value the Work or the Feature does not have is left out
            origin = "work" if keys or fkeys else "fixed"
            raw = _REF.sub(lambda m: work.get(m.group(1).lower(), "") if m.group(1)
                           else (feature or {}).get(m.group(2).lower(), "") if m.group(2) else words.get(m.group(3)), raw)
            h = re.match(r"^(#+) ", raw)
            if h:
                depth = len(h.group(1))
                if depth == 2:
                    sections.append({"line": n, "heading": raw.strip(), "job": None, "start": len(items),
                                     "blocks": 0, "shown": 0, "slots": 0, "kinds": []})
        else:
            origin = "fixed"
        items.append((raw.rstrip(), origin))
    for k in range(len(sections) - 1, -1, -1):  # from the back, so the positions of the others hold
        sec = sections[k]
        if sec["blocks"] and not sec["shown"] and not sec["slots"]:
            end = sections[k + 1]["start"] if k + 1 < len(sections) else len(items)
            del items[sec["start"]:end]
    _slot_neighbours(items, slots, here, problems)
    return items, slots, sections, problems, omitted


def _slot_neighbours(items, slots, here, problems):
    """A filled passage is found again between the fixed lines either side of its slot (ADR 0018). So straight
    before a slot is a line of fixed text (a line holding a value from the Work or the Feature may sit between),
    and straight after it is a line of fixed text; never a block or another slot (ADR 0022)."""
    for idx, slot in enumerate(slots):
        at = [k for k, (_, tag) in enumerate(items) if tag == idx]
        if not at:
            continue
        before = next(((x, tag) for x, tag in reversed(items[:at[0]]) if x.strip() and tag != "work"), None)
        after = next(((x, tag) for x, tag in items[at[-1] + 1:] if x.strip()), None)
        for where, found, line in (("before", before, slot["line"]), ("after", after, slot.get("last", slot["line"]))):
            if found is not None and found[1] != "fixed":
                problems.append(_problem(
                    "missing", here, line, what="line of fixed text straight %s the slot under '%s', so a passage written "
                    "there cannot be found again when the brief is made again" % (where, slot["section"]["heading"] or "the top"),
                    key="line", at="%s line %d" % ("after" if where == "after" else "before", line),
                    add="a line of plain text that holds no value and no block, for example 'As the business recorded it:'"))


def _tidy(items, stamp):
    """The items and the stamp as lines: trailing spaces gone, blank runs squeezed, no blank at either end.
    Returns [(text, where it came from)]."""
    out = []
    for text, tag in items + [("", "fixed"), ("---", "fixed"), ("", "fixed"), (stamp, "stamp")]:
        text = text.rstrip()
        if text == "" and (not out or out[-1][0] == ""):
            continue
        out.append((text, tag))
    while out and out[-1][0] == "":
        out.pop()
    return out


def _place_slots(out, slots):
    """Fill in where each slot is in the tidied lines, and cut the fixed pieces between them.
    Returns (lines, pieces, where each line came from)."""
    lines = [t for t, _ in out]
    pieces, pos = [], 0
    for idx, slot in enumerate(slots):
        at = [k for k, (_, tag) in enumerate(out) if tag == idx]
        slot["start"], slot["end"], slot["job"], slot["heading"] = at[0], at[-1] + 1, slot["section"]["job"], \
            slot["section"]["heading"]
        del slot["section"]
        pieces.append(lines[pos:slot["start"]])
        pos = slot["end"]
    pieces.append(lines[pos:])
    return lines, pieces, [tag for _, tag in out]


def build_face(store, template, template_file, words, where=None, feature=None, face="signoff", house=None):
    """The skeleton of a face. Returns a dict:

    text      the face, ready to write
    lines     the same, without line endings
    slots     [{job, heading, cap, header, start, end}]: where each slot is in `lines` (0-based, end exclusive)
    pieces    the fixed text between the slots, one list of lines each (blank lines included)
    kinds     where each line of `lines` came from: a slot number, "fixed", "work", "block", "approval", "apart" or "stamp"
    trace     the heading line of the section whose job is trace, or ''
    problems  findings about the template or the word list, each stating its fix
    coverage  {done: the jobs some section does, omitted: {job: (reason, line, text)}, first: the line of the first
              section, carries: {job: {kinds: its block kinds, slots: how many slots}}}; `check --adopt` judges it, a
              face never does (ADR 0018)
    `template_file` is the template's name as the stamp gives it; `where` is the path shown in findings.
    `feature` is the record the face is made for, if any; `face` its descriptor, or its name (a face is found by
    its name: ADR 0029).
    The face is always the form that is sent (ADR 0026, one text): the diagram label, the steps in words, " / "
    between the values in a cell. With a `house`: its brand lines (logo or name and header first, footer above the
    rule and stamp so the stamp stays last) and its `Diagram style` lines in each diagram's source.
    """
    where = where or template_file
    here = {"file": where}
    face = FACES[face] if isinstance(face, str) else face
    brief = face["brief"](store, words, feature)
    top, foot = [], []
    if house is not None:
        brief.styles = tuple(_diagram_styles(house))
        top, foot = _brand_lines(house)
    items, slots, sections, problems, omitted = _expand(brief, face, feature, words, template, here)
    for s in sections:
        if s["job"] is None:
            problems.append(_problem(
                "missing", here, s["line"], what="job line under the heading '%s'" % s["heading"], key="job",
                at="after line %d" % s["line"], add="{job: <one of %s>}" % ", ".join(face["jobs"])))
    for w in words.missing:
        problems.append(_problem(
            "missing", {"file": words.file or "words.md"}, words.last_line, what="row for the word '%s' in the word list. "
            "The brief shows the word as written" % w, key=w,
            at="after line %d" % words.last_line, add="| %s | <what readers should see> |  |" % w))
    base = store.get("baseline")
    count = base["findings"] if base else len([p for p in _findings(store) if p["level"] == "finding"])
    stamp = ("Made from baseline %s (records version %s), template %s, %d findings.%s" % (
        base["name"], base["version"], template_file, count, " Waived at freezing: " + base["waiver"] if base["waiver"] else "")
        if base else "Made from records version %s, template %s, %d findings." % (version_of(store), template_file, count))
    items = [(t, "fixed") for t in top] + items + [(t, "fixed") for t in foot]
    lines, pieces, kinds = _place_slots(_tidy(items, stamp), slots)
    trace = next((s["heading"] for s in sections if s["job"] == "trace"), "")
    at = next((k for k, tag in enumerate(kinds) if tag in ("approval", "apart")), 0)
    heading = next((t for t in reversed(lines[:at]) if t.startswith("#")), "")
    return {"text": "\n".join(lines) + "\n", "lines": lines, "slots": slots, "pieces": pieces, "kinds": kinds, "trace": trace,
            "approval heading": heading,
            "coverage": {"done": [j for j in face["jobs"] if any(x["job"] == j for x in sections)], "omitted": omitted,
                         "carries": {j: {"kinds": [k for x in sections if x["job"] == j for k in x["kinds"]],
                                         "slots": sum(x["slots"] for x in sections if x["job"] == j),
                                         "line": next((x["line"] for x in sections if x["job"] == j), 1)} for j in face["jobs"]},
                         "first": sections[0]["line"] if sections else 1},
            "problems": problems, "version": version_of(store), "count": count, "stamp": stamp}


def _texts(lines):
    """[(line number, text)] for the lines that are not blank, trailing spaces gone."""
    return [(n, t.rstrip()) for n, t in enumerate(lines, 1) if t.strip()]


# ==== helper/src/facecheck.py ===============================================
"""Face check: how `check` reads a brief already written, against the records and its template (ADR 0018).

Owns the stamp comparison, fixed-text matching, slot checks and the lints a descriptor names. Advice only.
Must not know: how a brief is written to disk (bundle) or how a skeleton is built beyond calling build_face.
"""

def _first_difference(piece, region, floor, after_slot=False):
    """(line number, what is there, what to write) for where `region` departs from `piece`.

    `after_slot`: the region opens with the text of a filled slot, which is the writer's and is never
    the line to change."""
    ops = difflib.SequenceMatcher(None, piece, [t for _, t in region], autojunk=False).get_opcodes()
    add = "'%s' on a line of its own, then the line that is there now"
    for tag, i1, i2, j1, j2 in ops:
        if tag == "replace" and after_slot and j1 == 0:
            # The piece's first line was changed or deleted. If changed, it is the last of these lines,
            # recognisably the same line; anything else here is slot text, and the line goes in after it.
            n, there = region[max(j1, j2 - (i2 - i1))]
            same = difflib.SequenceMatcher(None, piece[i1], there).ratio() >= 0.5 or (
                piece[i1].startswith("#") and there.startswith("#"))
            if same:
                return n, there, piece[i1]
            if j2 < len(region):
                return region[j2][0], region[j2][1], add % piece[i1]
            return region[-1][0], region[-1][1], "the line that is there now, then '%s' on a line of its own" % piece[i1]
        if tag in ("replace", "delete"):
            n = region[j1][0] if j1 < len(region) else (region[-1][0] if region else floor)
            there = region[j1][1] if j1 < len(region) else ""
            if tag == "delete" or j1 >= len(region):
                return n, there, add % piece[i1] if there else piece[i1]
            return n, there, piece[i1]
    for tag, i1, i2, j1, j2 in ops:
        if tag == "insert" and 0 < i1 < len(piece):
            return region[j1][0], region[j1][1], "nothing: delete the line, it is not in the template"
    n = region[0][0] if region else floor
    return n, region[0][1] if region else "", piece[0]


def _match_pieces(pieces, face):
    """Find the fixed pieces in order. Returns (contents, failure): the text of each slot as
    [(line number, text)], or None and the (piece, region, whether a slot comes before it) that did not match."""
    P = [[t.rstrip() for t in p if t.strip()] for p in pieces]
    texts = [t for _, t in face]
    contents, pos = [], 0  # contents: [{"lines": [(n, text)], "after": last line of the piece before}]
    for k, piece in enumerate(P):
        last = k == len(P) - 1
        if k == 0:
            at = 0 if texts[:len(piece)] == piece else None
        elif last:
            at = len(texts) - len(piece) if len(texts) - len(piece) >= pos and texts[len(texts) - len(piece):] == piece else None
        else:
            at = next((x for x in range(pos, len(texts) - len(piece) + 1) if texts[x:x + len(piece)] == piece), None)
        if at is None:
            return None, (piece, face[pos:], k > 0)
        if k:
            contents.append({"lines": face[pos:at], "after": face[pos - 1][0] if pos else 0})
        pos = at + len(piece)
    return contents, None


def _only_apart_differs(skeleton, face):
    """True when the brief matches the skeleton everywhere but inside the blocks built from a section the records
    version leaves out (the approval block, the forecast's blocks): an approval was recorded, or actuals were read, (or
    the table edited) after the brief was made. Each block is cut out like a slot and the pieces either side of it
    are looked for in order."""
    pieces, cur, cut = [], [], False
    for text, kind in zip(skeleton["lines"], skeleton["kinds"]):
        hole = kind in ("approval", "apart") or isinstance(kind, int)
        if hole and not cut:
            pieces.append(cur)
            cur = []
        elif not hole:
            cur.append(text)
        cut = hole
    pieces.append(cur)
    if "approval" not in skeleton["kinds"] and "apart" not in skeleton["kinds"]:
        return False
    return _match_pieces(pieces, face)[0] is not None


def _made_before_where_it_lives(store, house, kind, name, record, face):
    """True when the brief matches what the records give with the lines that say where a record lives (LIVES_AT:
    a tracker item, a business item) left out: the item was recorded after the brief was made, and the brief shows
    it. Such a line leaves the records version alone (ADR 0011), so the stamp cannot say it; the fix is to make the
    brief again, never to edit its table by hand."""
    # The lines stay, so the records version and the stamp stay the same; their values are blank, so the brief shows none.
    leave = lambda r: dict(r, fields={k: dict(v, value="") if k in LIVES_AT.get(r["kind"], ()) else v for k, v in r["fields"].items()})
    work = next((r for r in store["records"] if r["kind"] == "work"), None)
    for who in ([record], [work], [record, work]):  # the Feature's lines, the Work's, or both, were written after
        who = [r for r in who if r is not None]
        plain = dict(store, records=[leave(r) if any(r is w for w in who) else r for r in store["records"]])
        mine = plain["records"][store["records"].index(record)] if record is not None else None
        skeleton = build_face(plain, house.template(kind, name).replace("\r\n", "\n"), name, house.words(), feature=mine, face=kind, house=house)
        if _match_pieces(skeleton["pieces"], face)[0] is not None:
            return True
    return False


def _made_before_an_approval(store, house, kind, name, record, face):
    """True when the brief matches what the records give with fewer of the Work's approvals recorded. The `changes`
    block depends on which baseline each approver approved, and an approval is outside the records version, so one
    recorded after the brief was made leaves the stamp alone and the block behind. Only a block that is as it was
    for an earlier set of approvals is behind; an edit is not."""
    work = next((r for r in store["records"] if r["kind"] == "work"), None)
    if "changes" not in kind["blocks"] or not work:
        return False
    for k in range(len(work["approvals"]) - 1, -1, -1):
        earlier = dict(work, approvals=work["approvals"][:k])
        plain = dict(store, records=[earlier if r is work else r for r in store["records"]])
        skeleton = build_face(plain, house.template(kind, name).replace("\r\n", "\n"), name, house.words(),
                              feature=record, face=kind, house=house)
        if _match_pieces(skeleton["pieces"], face)[0] is not None:
            return True
    return False


def _face_findings(store, option=None):
    # The briefs ba writes are the ones it checks: a file in faces/ that a descriptor in FACES names, and for a face
    # made for a record, whose record exists. Any other file in faces/ is the person's own.
    folder = store["folder"]
    if not folder:
        return []
    faces = os.path.join(folder, "faces")
    names = sorted(os.listdir(faces)) if os.path.isdir(faces) else []
    mine = []
    for kind in FACES.values():
        for name in names:
            m = kind["on_disk"].match(name)
            if not m or not os.path.isfile(os.path.join(faces, name)):
                continue
            record = next((r for r in store["records"] if r["kind"] == kind["for"] and r["id"]
                           and r["id"].lower() == m.group(1).lower()), None)
            if kind["for"] is None or record is not None:
                mine.append(("faces/" + name, kind, record))
    if not mine:
        return []
    work = next((r for r in store["records"] if r["kind"] == "work"), _new_record("work", "", "work.md", 1))
    house, _, _ = _house(folder, work, option)
    found = []
    for rel, kind, record in mine:
        found += _check_face(store, rel, read_text(os.path.join(folder, *rel.split("/"))), house or House(), option,
                             kind, record)
    return found


def _check_face(store, rel, text, house, option, kind, record=None):
    """Check one brief against the records. `kind` is its descriptor in FACES; `record` the record it is made
    for, if it is made for one."""
    lines, here, found = _LINE.findall(text), {"file": rel}, []
    target = record["id"] if record is not None else None
    again = lambda name, bname="": _face_cmd(kind, target, option, bname, name)
    face = _texts(lines)
    m = _STAMP.match(face[-1][1]) if face else None
    for n, t in face:
        if t.startswith("> {slot:"):
            heading = next((h for hn, h in reversed([x for x in face if x[0] < n]) if h.startswith("## ")), "the top")
            end = n
            while end < len(lines) and lines[end].lstrip().startswith(">"):
                end += 1
            found.append(_problem(
                "missing", here, n, what="text for the slot under '%s'" % heading, key="slot", at="in place of lines %d to %d "
                "(the slot and the quoted lines under it)" % (n, end),
                add="the passage the quoted lines ask for, then run: %s%s" % (CHECK, FOLDER)))
    if not m:
        return found + [_problem(
            "not-read", here, len(lines) or 1,
            what="There is no stamp line ('Made from records version ...') at the end of this brief, so it cannot be "
                 "compared with the records.",
            how="Run: %s   It makes the brief again with its stamp, carries the passages you wrote into it, and keeps "
                "a copy of this one in backup/.%s" % (again(""), kind["form_hint"]))]
    version, name = m.group("v") or m.group("bv"), m.group("t")
    bname = m.group("b") or ""
    if bname:
        base, why = _read_baseline(store, bname)
        if base is None:
            return found + [_problem(
                "not-read", here, face[-1][0],
                what="The stamp names baseline '%s', which is not in baselines/, so the brief cannot be compared with it." % bname,
                how="Make the brief from the working records instead: %s" % _face_cmd(kind, target, option, "", name))]
        store = base
        if record is not None:
            record = next((r for r in store["records"] if r["kind"] == record["kind"] and r["id"] == record["id"]), None)
            if record is None:
                return found + [_problem(
                    "not-read", here, face[-1][0],
                    what="Baseline '%s' does not hold this Feature, so the brief cannot be compared with it." % bname,
                    how="Make the brief from the working records instead, or from a baseline that holds it: %s"
                        % _face_cmd(kind, kind["on_disk"].match(os.path.basename(rel)).group(1), option))]
    if version != version_of(store):
        return [_problem(
            "stale", here, face[-1][0], old=version, new=version_of(store),
            what="The records changed since this brief was made",
            how="Run: %s   It makes a fresh brief, carries the passages you wrote into it, and keeps a copy of "
                "this one in backup/. Read each passage again against the changed records." % again(name, bname))]
    path = house.templates(kind).get(name)
    if not path:
        forms = ", ".join(_form_names(kind, house, "own") or ())
        return found + [_problem(
            "not-read", here, face[-1][0],
            what="The stamp names the template '%s' and the house has no template with that name, so the fixed text "
                 "cannot be compared.%s" % (name, "" if option else " (If the brief was made with --house <folder>, "
                 "check it the same way: %s --house <folder>.)" % (CHECK + FOLDER)),
            how=kind["missing_template_fix"].format(bundle=_face_cmd(kind, target, option), forms=forms,
                                                    again=again(name)))]
    skeleton = build_face(store, house.template(kind, name).replace("\r\n", "\n"), name, house.words(), where=path, feature=record, face=kind, house=house)
    contents, failure = _match_pieces(skeleton["pieces"], face)
    if failure and "apart" in skeleton["kinds"] and _only_apart_differs(skeleton, face):
        at = next((n for n, t in face if t == skeleton["approval heading"]), face[-1][0])
        found.append(_problem(
            "stale", here, at,
            what="The forecast in this %s is behind the Work's '### Delivery' and '### Actuals', or was changed by hand" % kind["title"],
            how="The forecast is ba's to write, from those two sections; do not edit it in the brief. Run: %s   It writes the "
                "forecast again and carries the passage you wrote into it. Read the passage again against the new dates."
                % again(name, bname)))
    elif failure and _only_apart_differs(skeleton, face):
        at = next((n for n, t in face if t == skeleton["approval heading"]), face[-1][0])
        found.append(_problem(
            "stale", here, at,
            what="The approval table in this brief is behind the Work's '### Approvals', or was changed by hand",
            how="The table is ba's to write, from the items under '### Approvals' on the Work; do not edit it in the "
                "brief. Run: %s   It writes the table again and carries the passages you wrote into it. (An approver's "
                "answer is recorded on the Work: - <name>: approved, <date>, records version %s, \"<their words>\")"
                % (again(name, bname), version)))
    elif failure and _made_before_where_it_lives(store, house, kind, name, record, face):
        found.append(_problem(
            "stale", here, face[-1][0],
            what="A tracker item was recorded after this brief was made, and the brief shows it",
            how="Run: %s   It writes the brief again with the item and carries the passages you wrote into it. Do not edit "
                "the table by hand." % again(name, bname)))
    elif failure and _made_before_an_approval(store, house, kind, name, record, face):
        found.append(_problem(
            "stale", here, face[-1][0],
            what="An approval was recorded after this brief was made, so what it says changed since the approval is behind",
            how="Run: %s   It writes the brief again with the changes as they stand and carries the passages you wrote "
                "into it. Do not edit that table by hand." % again(name, bname)))
    elif failure:
        piece, region, after_slot = failure
        n, there, write = _first_difference(piece, region, face[0][0] if face else 1, after_slot)
        found.append(_problem(
            "bad-value", here, n, key="Fixed text", value=there[:60] + ("..." if len(there) > 60 else ""), allowed=[],
            why="This part comes from the records and the template and is not edited by hand. "
                "(To start again, run %s; the passages you wrote are carried over.)" % again(name, bname),
            write=write))
    else:
        for slot, got in zip(skeleton["slots"], contents):
            content = got["lines"]
            if any(t.startswith("> {slot:") for _, t in content):
                continue  # still empty: reported above
            if not content:
                found.append(_problem(
                    "missing", here, got["after"] + 1, what="text for the slot under '%s'" % slot["heading"], key="slot",
                    at="after line %d" % got["after"], add="up to %s words. Then run: %s%s" % (slot["cap"], CHECK, FOLDER)))
                continue
            words = len(" ".join(re.sub(r"^\s*>\s?", "", t) for _, t in content).split())
            if slot["cap"] and words * SLOT_OVER[1] > slot["cap"] * SLOT_OVER[0]:
                found.append(_problem(
                    "bad-value", here, content[0][0], key="Slot", value="%d words" % words, allowed=[],
                    why="The slot under '%s' aims for %d words, and this is more than a quarter over."
                        % (slot["heading"], slot["cap"]),
                    write="the same passage in about %d words" % slot["cap"],
                    where="line %d" % content[0][0] if content[-1][0] == content[0][0]
                    else "lines %d to %d" % (content[0][0], content[-1][0])))
    for lint in kind["lints"]:
        found += LINTS[lint](kind, record, text, here, skeleton, None if failure else contents)
    inside = set(skeleton["lines"])
    limit = next((k for k, t in enumerate(lines) if skeleton["trace"] and t.strip() == skeleton["trace"]), len(lines))
    for n, raw in enumerate(lines[:limit], 1):
        ids = _ID_IN_TEXT.findall(raw)
        if ids and raw.rstrip() not in inside:
            found.append(_problem(
                "bad-value", here, n, key="ID", value=", ".join(ids), allowed=[],
                why=kind["ids_why"],
                write="the same sentence without %s (name the record by its name)" % ", ".join(ids)))
    return found


def _lint_size(kind, record, text, here, *_):
    """A brief past the face's size is too large to hand over as one piece."""
    size = len(text.replace("\r\n", "\n"))
    if size <= kind["max_chars"]:
        return []
    return [_problem(
        "bad-value", here, 1, key="Size", value="%d characters, about %d tokens" % (size, size // 4), allowed=[],
        why="A handover brief aims for 1,500 to 3,000 tokens (four characters to a token), and this is more than a "
            "quarter over. It is too large for engineers to specify as one piece, and cutting text would cut what "
            "the business said.", fixfile=record["file"], where="the Feature records and their requirements",
        write="%s '%s' replaced by its parts: write each part as a new Feature record with '- Sliced from: %s', "
              "point each requirement's '- Feature:' line at the part it belongs to, set '- Status: withdrawn' on %s, "
              "then make a brief for each part with: %s bundle handover <the part's ID>%s"
              % (record["id"], record["name"], record["id"], record["id"], BA, FOLDER))]


_DATE_IN_TEXT = re.compile(r"\b(?:(\d{1,2}) (%s) (\d{4})|(\d{4})-(\d{2})-(\d{2}))\b" % "|".join(MONTHS))


def _dates_in(text):
    """[(the date as written, the date)] for each `<day> <month name> <year>` and `YYYY-MM-DD` in the text. A day that
    is not on the calendar is left out. It compares figures, as the ID lint does, and reads no wording."""
    out = []
    for m in _DATE_IN_TEXT.finditer(text):
        try:
            day = (datetime.date(int(m.group(3)), MONTHS.index(m.group(2)) + 1, int(m.group(1))) if m.group(1) else
                   datetime.date(int(m.group(4)), int(m.group(5)), int(m.group(6))))
        except ValueError:
            continue
        out.append((m.group(0), day))
    return out


def _lint_dates(kind, record, text, here, skeleton, contents):
    """A date in a passage that is in none of the helper's lines of the plan was worked out by the writer: the dates are
    the helper's (ADR 0031). Needs the passages found, so it says nothing when the fixed text did not match."""
    if contents is None:
        return []
    plan = {day for line, tag in zip(skeleton["lines"], skeleton["kinds"]) if not isinstance(tag, int) for _, day in _dates_in(line)}
    return [_problem(
        "bad-value", here, n, key="Date", value=shown, allowed=[],
        why="This date is in none of the tables of the plan. The dates are worked out by ba, and a passage copies one of them.",
        write="the same sentence with a date from the tables above, or without the date")
        for got in contents for n, t in got["lines"] if not t.startswith("> {slot:") for shown, day in _dates_in(t) if day not in plan]


# The checks a descriptor may name in its `lints`: each takes (descriptor, record, text, where, skeleton, the passages
# found or None) and returns findings.
LINTS = {"size": _lint_size, "dates": _lint_dates}


def _face_cmd(kind, target, option, baseline="", template_name=""):
    """The command that makes a brief again, as this run was started: `kind` is its descriptor, `target` the ID of
    the record it is made for, `template_name` the template it was made from (a form is read from it)."""
    form = re.match(r"^signoff-(.+)\.md$", template_name or "") if kind["forms"] else None
    return (BA + " " + kind["usage"] + (" " + target if target else "") + FOLDER + (" --form %s" % form.group(1) if form else "") +
            (" --house %s" % shlex.quote(option) if option else "") + (" --baseline %s" % baseline if baseline else ""))


# ==== helper/src/bundle.py ==================================================
"""Bundle: the `bundle` verb. Resolve what to make, build the face, write it to faces/, carry earlier passages.

Every face goes through the same path; the descriptor says what differs. Must not know: how a template is read
(faces) or how a brief is checked (facecheck).
"""


def bundle(args):
    """`ba bundle <face> ...`: work out what the face is made from, build it, write it to faces/."""
    if not args.face:
        print("The briefs ba can make: signoff, for the approvers; scope, for the business owner; delivery, for the "
              "forecast; and handover, for the engineers, one for each Feature. Make them with: %s   or: %s bundle scope%s   "
              "or: %s bundle delivery%s   or: %s bundle handover <feature>%s" % (BUNDLE, BA, FOLDER, BA, FOLDER, BA, FOLDER))
        return 0
    if args.face == "landing":  # the test landing of a house's places (ADR 0026): no workspace, no records
        return landing(args)
    face = FACES.get(args.face)
    if face is None:
        print("There is no brief called '%s'. The ones ba can make are signoff, scope, delivery and handover. Try: %s   or: "
              "%s bundle scope   or: %s bundle delivery   or: %s bundle handover <feature>" % (args.face, BUNDLE, BA, BA, BA),
              file=sys.stderr)
        return 2
    kept = _baseline_of_brief(args, face)
    if kept:  # sending the page is not making it again from other records: it is the page that was frozen (ADR 0034)
        args.baseline = kept
    got, code = _bundle_target(args, face)
    if got is None:
        return code
    store, folder, record, house, problems, name, path = got
    if args.outbox:
        again = "%s %s%s%s%s --outbox%s" % (BA, face["usage"], " " + record["id"] if record else "",
                                           " --baseline " + shlex.quote(args.baseline) if args.baseline else "",
                                           " --house " + shlex.quote(args.house) if args.house else "", FOLDER)
        ask = _fetch_house_first(args, store, folder, house, again)
        if ask:
            print(ask, file=sys.stderr)
            return 2
    skeleton = build_face(store, house.template(face, name).replace("\r\n", "\n"), name, house.words(), where=path,
                          feature=record, face=face, house=house)
    code = _write_face(store, folder, house, problems, name, skeleton, face_file(face, record), CHECK, show=not args.outbox)
    if kept and code == 0:
        print("Made from baseline %s, as the brief in faces/ was." % kept)
    return send(args, got, face, again) if args.outbox and code == 0 else code


def _baseline_of_brief(args, face):
    """With --outbox and no --baseline: the baseline the brief in faces/ was made from, by its stamp, when that baseline
    is still in baselines/; else ''. Plain `bundle` still makes a brief from the working records (ADR 0013)."""
    if not args.outbox or args.baseline or not face["baselines"]:
        return ""
    folder = find_workspace(args.folder)
    if folder is None:
        return ""
    rel = face_file(face)
    if face["for"]:
        found = feature_named(read_workspace(folder)["records"], args.feature) if args.feature else None
        if found is None or not found["id"]:
            return ""
        rel = face_file(face, found)
    how, m = _stamp_of({"folder": folder}, rel)
    name = m.group("b") if how == "stamped" else ""
    return name if name and _manifest(folder, name) else ""


def _bundle_target(args, face):
    """Resolve what `bundle` needs for this face. Returns (store, folder, the record it is made for or None, the house,
    house problems, template name, template path) and 0, or None and an exit code after printing why it cannot
    go on."""
    command = "%s %s" % (BA, face["usage"])
    folder = find_workspace(args.folder)
    if folder is None:
        where, misplaced = _no_workspace(args.folder, command)
        print(misplaced or "No work.md %s, so there is nothing to make a brief from. Fix: create work.md with a "
              "Work record (%s --shape work), or give the folder: %s%s <folder>" % (where, CHECK, command, face["target"]),
              file=sys.stderr)
        return None, 2
    live = read_workspace(folder)
    work = next((r for r in live["records"] if r["kind"] == "work"), _new_record("work", "", "work.md", 1))
    house, problems, error = _house(folder, work, args.house)
    if error:
        print("ba bundle: " + error, file=sys.stderr)
        return None, 2
    if args.baseline and not face["baselines"]:
        print("ba bundle: the %s is made from the working records: a baseline does not hold the Delivery and Actuals "
              "sections. Fix: leave out --baseline." % face["title"], file=sys.stderr)
        return None, 2
    store, record, code = MADE_FROM[face["for"]](args, live, folder)
    if store is None:
        return None, code
    why = face["needs"](store) if face["needs"] else None
    if why:
        print("ba bundle: " + why, file=sys.stderr)
        return None, 2
    form = (args.form or value(work, "sign-off form")) if face["forms"] else ""
    name, path = _pick_template(face, house, form)
    if name is None:
        line = (", or change line %d of work.md to '- Sign-off form: <one of those>'"
                % work["fields"]["sign-off form"]["line"]) if not args.form and form else ""
        print("ba bundle: %s Fix: %s" % (path, face["no_template_fix"].format(line=line)), file=sys.stderr)
        return None, 2
    return (store, folder, record, house, problems, name, path), 0


def _whole_work(args, live, folder):
    """What a face made for the whole work is made from: the records, or the baseline --baseline names.
    Returns (store, None, 0), or (None, None, an exit code) after printing why not."""
    if not args.baseline:
        return live, None, 0
    store, why = _read_baseline(live, args.baseline)
    if store is None:
        print("ba bundle: " + why, file=sys.stderr)
        return None, None, 2
    return store, None, 0


def _heading_of(slot):
    return "'%s'" % (slot["heading"].lstrip("#").strip() or "the top")


def _carry(skeleton, old_text):
    """Find the passages written into the slots of an earlier brief, so they can go into this skeleton.

    Each slot is matched by its position among the template's slots. Its place in the earlier brief is found
    the way `check` finds fixed pieces: the fixed lines on either side of the slot are looked for, in order.
    A line that holds a value from the Work (the goal) sits between them and is skipped; anything built
    from the records there would make the place uncertain, and then the slot is left out.
    Returns {slot number: [lines of the passage]} for the slots found filled."""
    raw = _LINE.findall(old_text)
    old = _texts(raw)
    texts = [t for _, t in old]
    end = len(old) - 1 if old and _STAMP.match(old[-1][1]) else len(old)
    sk = [(t, k) for t, k in zip(skeleton["lines"], skeleton["kinds"]) if t and k != "stamp"]
    spans = []  # for each slot, the first and one past the last of its lines in sk
    for idx in range(len(skeleton["slots"])):
        at = [i for i, (_, k) in enumerate(sk) if k == idx]
        spans.append((at[0], at[-1] + 1))
    found, pos = {}, 0
    for idx, (a, b) in enumerate(spans):
        floor = spans[idx - 1][1] if idx else 0
        ceiling = spans[idx + 1][0] if idx + 1 < len(spans) else len(sk)
        left = next((i for i in range(a - 1, floor - 1, -1) if sk[i][1] == "fixed"), None)
        right = next((i for i in range(b, ceiling) if sk[i][1] == "fixed"), None)
        before = sk[(left + 1 if left is not None else floor):a]
        after = sk[b:right if right is not None else ceiling]
        if (left is None and idx) or (right is None and idx + 1 < len(spans)) or after \
                or any(k != "work" for _, k in before):
            continue
        li = -1
        if left is not None:
            li = next((x for x in range(pos, end) if texts[x] == sk[left][0]), None)
            if li is None:
                continue
        ri = end
        if right is not None:
            ri = next((x for x in range(li + 1, end) if texts[x] == sk[right][0]), None)
            if ri is None:
                continue
        pos = ri
        region = old[li + 1 + len(before):ri]
        if region and not any(t.startswith("> {slot:") for _, t in region):
            found[idx] = [x.rstrip() for x in raw[region[0][0] - 1:region[-1][0]]]
    return found


def _fill(skeleton, passages):
    """The text of the face with each carried passage in place of its slot."""
    lines = list(skeleton["lines"])
    for idx in sorted(passages, reverse=True):
        slot = skeleton["slots"][idx]
        lines[slot["start"]:slot["end"]] = passages[idx]
    return "\n".join(lines) + "\n"


def _earlier_brief(target):
    """The text of the brief already in faces/, or None when there is none or it is not UTF-8."""
    if not os.path.isfile(target):
        return None
    try:
        return read_text(target)
    except Unreadable:
        return None


def _write_face(store, folder, house, problems, name, skeleton, rel, check_cmd, show=True):
    """Write a brief to faces/, carrying the passages of an earlier one, and say what was done."""
    problems += skeleton["problems"]
    target = os.path.join(folder, *rel.split("/"))
    earlier = _earlier_brief(target)
    carried = _carry(skeleton, earlier.replace("\r\n", "\n")) if earlier is not None else {}
    text = _fill(skeleton, carried) if carried else skeleton["text"]
    kept = same = ""
    if os.path.isfile(target) and _bytes(target) != text.encode("utf-8"):
        kept = "A copy of the brief it replaced is in %s/%s." % (_backup_and_write(folder, {rel: text}), rel)
    elif not os.path.isfile(target):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    else:
        same = "%s was already up to date with the records." % rel
    out = ["Workspace: " + folder, same or "Wrote %s from the template %s (%s)." % (
        rel, name, "house: " + house.own.path if house.own else "shipped house")]
    if kept:
        out.append(kept)
    out += _carried_lines(skeleton, carried, earlier is not None, same)
    base = store.get("baseline")
    if base:
        out.insert(1, "Made from baseline %s, frozen %s, not from the working records." % (base["name"], base["date"]))
    if base and skeleton["count"]:
        out.append("The baseline was frozen with %d finding(s)%s." % (
            skeleton["count"], "; the waiver is on its stamp" if base["waiver"] else ""))
    elif skeleton["count"]:
        out.append("The records have %d finding(s); the brief carries them as written. %s%s lists them." % (
            skeleton["count"], CHECK, FOLDER))
    unread = [p for p in _findings(store) if p.get("key") == "Actuals"] if rel == face_file(FACES["delivery"]) else []
    if unread:  # what an Actuals line says is not in the plan, and its feature shows as not started: say so
        out += ["", "An Actuals line could not be read, so the plan leaves it out and shows that feature as not started:"] + _show(unread)
    if problems:
        out += ["", "The template or word list needs attention:"] + _show(problems)
    left = len(skeleton["slots"]) - len(carried)
    out += ["", "Next: fill the %d slot(s) in %s. Each starts '> {slot:' and the quoted lines under it say what to "
            "write. Then run: %s%s" % (left, rel, check_cmd, FOLDER)]
    if show:
        print("\n".join(out))
    return 0


def _one_feature(args, live, folder):
    """What a face made for one Feature is made from: the Feature the command names, in the records or in the
    baseline --baseline names. Returns (store, the Feature, 0), or (None, None, an exit code) after printing why
    not (a list of the Features, with code 0, when none is named)."""
    features = [r for r in live["records"] if r["kind"] == "feature"]
    given = args.feature
    cmd = "%s bundle handover <feature>%s   (the feature's ID, handle or name)" % (BA, FOLDER)
    if not features:
        if given:
            print("ba bundle: there is no Feature record, so there is no Feature '%s'. Fix: write one (see the shape: "
                  "%s --shape feature), then run: %s" % (given, CHECK, cmd), file=sys.stderr)
            return None, None, 2
        print("Workspace: %s\nThere are no Feature records yet, so there is no handover brief to make. See the shape: "
              "%s --shape feature" % (folder, CHECK))
        return None, None, 0
    if not given:
        print("\n".join(["Workspace: " + folder, "Features, and the handover brief of each:"] + _feature_list(live) +
                         ["", "Make one with: " + cmd]))
        return None, None, 0
    f = feature_named(live["records"], given)
    same = [r for r in features if status_of(r) != "withdrawn" and r["name"].strip().lower() == given.strip().lower()]
    if f is not None and len(same) > 1 and (f["id"] or "").lower() != given.strip().lower():
        ids = [r["id"] for r in same if r["id"]]
        print("ba bundle: Two Features are named '%s'%s. ba will not choose between them. Fix: %s" % (
            f["name"], ": " + " and ".join(ids) if len(ids) == len(same) else "",
            "run it again with the ID of the one you mean: %s bundle handover %s%s" % (BA, ids[0], FOLDER) if ids else
            "rename one, or run %s --fix to give each an ID" % (CHECK + FOLDER)), file=sys.stderr)
        return None, None, 2
    if f is None:
        print("ba bundle: There is no Feature '%s'. The Features are:\n%s\nFix: run it again with the ID, handle or "
              "name of one of them." % (given, "\n".join(_feature_list(live))), file=sys.stderr)
        return None, None, 2
    store = live
    if args.baseline:
        store, why = _read_baseline(live, args.baseline)
        if store is None:
            print("ba bundle: " + why, file=sys.stderr)
            return None, None, 2
        held = next((r for r in store["records"] if r["kind"] == "feature" and f["id"] and r["id"] == f["id"]), None)
        if held is None:
            parent = feature_named(live["records"], _parts(value(f, "sliced from"))[0]) if _parts(value(f, "sliced from")) else None
            inside = parent is not None and any(r["kind"] == "feature" and r["id"] == parent["id"] for r in store["records"])
            print("ba bundle: %s is not in baseline %s.%s Fix: freeze a new baseline (%s) and get it approved, or leave "
                  "out --baseline to make the brief from the working records." % (
                      " ".join(x for x in (f["id"], f["name"]) if x), args.baseline,
                      " It was sliced from %s, which is." % " ".join(x for x in (parent["id"], parent["name"]) if x) if inside else "",
                      _baseline_cmd(_next_name(folder, args.baseline))), file=sys.stderr)
            return None, None, 2
        f = held
    if kept_original(store, f):
        print("ba bundle: %s was sliced into: %s. Each has a brief of its own. Fix: make the brief of one of them." % (
            " ".join(x for x in (f["id"], f["name"]) if x),
            "; ".join(" ".join(x for x in (p["id"], p["name"]) if x) for p in _parts_of(store, f))), file=sys.stderr)
        return None, None, 2
    if status_of(f) == "withdrawn":
        parts = _parts_of(store, f)
        print("ba bundle: %s is withdrawn.%s Fix: make the brief of %s." % (
            " ".join(x for x in (f["id"], f["name"]) if x),
            " It was sliced into: %s." % "; ".join(" ".join(x for x in (p["id"], p["name"]) if x) for p in parts) if parts else "",
            "one of them" if parts else "another Feature: " + cmd), file=sys.stderr)
        return None, None, 2
    if not f["id"]:
        print("ba bundle: Feature '%s' has no ID, and a brief is named by it. Fix: run %s   It gives every record "
              "an ID and writes a backup first." % (f["name"], _fixcmd()), file=sys.stderr)
        return None, None, 2
    if not _feature_reqs(store, f):
        live = live_features(store)
        loose = _loose(store)
        print("ba bundle: %s has no requirements, so there is no brief to write, and nothing was written. Fix: add "
              "'- Feature: %s' to a requirement that belongs in it%s, then run: %s" % (
                  " ".join(x for x in (f["id"], f["name"]) if x), _feature_shown(f, live),
                  " (for example one that is in no feature: %s)" % ", ".join("'%s'" % r["name"] for r in loose[:4])
                  + (", and %d more" % (len(loose) - 4) if len(loose) > 4 else "") if loose else "",
                  "%s bundle handover %s%s" % (BA, f["id"], FOLDER)), file=sys.stderr)
        return None, None, 2
    return store, f, 0


# What each kind of face is made from (the `for` of its descriptor): a function that returns (store, record, code).
MADE_FROM = {None: _whole_work, "feature": _one_feature}


def _feature_list(store):
    """One line a Feature: what it is, and where its handover brief stands."""
    out = []
    for f in store["records"]:
        if f["kind"] != "feature":
            continue
        ref = " ".join(x for x in (f["id"], f["name"]) if x)
        if status_of(f) == "withdrawn":
            parts = _parts_of(store, f)
            out.append("  %s (withdrawn): no brief%s" % (ref, "; sliced into " + ", ".join(
                p["id"] or p["name"] for p in parts) if parts else ""))
            continue
        if kept_original(store, f):
            out.append("  %s (%s): no brief; kept, sliced into %s" % (ref, status_of(f), ", ".join(p["id"] or p["name"] for p in _parts_of(store, f))))
            continue
        state, rel = _handover_state(store, f)
        stands = {"none": "no brief yet" if f["id"] else "no ID yet, so no brief: run %s --fix" % CHECK,
                  "older": "%s, older than the records" % rel, "current": "%s, up to date" % rel,
                  "unknown": "%s, with no stamp" % rel}[state]
        out.append("  %s (%s): %s" % (ref, status_of(f), stands))
    return out


def _carried_lines(skeleton, carried, had_earlier, same):
    """What bundle says about the passages of an earlier brief."""
    if not had_earlier or not skeleton["slots"]:
        return []
    out = []
    if carried and not same:
        out.append("Carried over from the earlier brief: %s. They were written for the earlier records, so "
                   "re-read each one against the records as they are now." % ", ".join(
                       _heading_of(skeleton["slots"][i]) for i in sorted(carried)))
    missed = [_heading_of(s) for i, s in enumerate(skeleton["slots"]) if i not in carried]
    if missed and not same:
        out.append("Not carried over: %s (nothing was written there, or its place in the earlier brief could "
                   "not be found; the earlier brief is in backup/)." % ", ".join(missed))
    return out


# ==== helper/src/outbox.py ==================================================
"""Outbox: what is sent, where it went, and the files and note that prepare a sending (ADR 0026).

Owns the reading of `### Published` (the last sending of each face, whether it is current), the copy of a brief
that is sent (brand lines, diagram label, steps in words), the tracker items' body, and the note that says where
each goes. The helper never sends: it writes outbox/ and prints a note, and the skill carries the file to the place
the note names. Must not know: how a brief is built (faces, blocks) beyond asking for it with the copy's changes, or
which tools carry it.
"""


def last_sent(work):
    """{face: the last `### Published` item of that face}: the last one written is the current one."""
    out = {}
    for item in work["published"] if work else []:
        out[item["face"].lower()] = item
    return out


def sent_is_current(store, item):
    """True when the sending was made from the records as they are now: its records version is this one, or its
    baseline froze this version."""
    kind, _, name = item["from"].partition(" ")
    if kind.lower() == "baseline":
        m = _manifest(store["folder"], name.strip())
        return bool(m) and m["records version"] == version_of(store)
    return item["from"].split()[-1].lower() == version_of(store)


def sent_what(item):
    """`page 4512, version 3` or `item KD-140`."""
    return "page %s, version %s" % (item["page"], item["version"]) if item["page"] else "item " + item["item"]


def _brand(house):
    """{organisation, logo, header, footer}: what brand.md sets, '' for what it leaves out or says `not set`."""
    top = read_destinations(house.text("brand.md") or "")["top"]
    return {k: (top[k][0] if k in top and given(top[k][0]) else "") for k in ("organisation", "logo", "header", "footer")}


def _diagram_styles(house):
    """The `- Diagram style: <one line of Mermaid>` lines of brand.md, in order (ADR 0038). `not set` and empty ones are left out.
    Nothing here reads or checks the Mermaid."""
    found = [m.group(1) for m in (re.match(r"^-\s*Diagram style\s*:\s*(.*?)\s*$", l.strip(), re.I)
                                  for l in _blank_comments(house.text("brand.md") or "").replace("\r\n", "\n").split("\n")) if m]
    return [x for x in found if given(x)]


def _brand_lines(house):
    """([lines above the brief], [lines below it]): the logo (or the name in bold) first, the header under it, and
    the footer last. A house that sets none adds nothing (ADR 0025)."""
    brand = _brand(house)
    top = ["![%s](%s)" % (brand["organisation"], brand["logo"]) if brand["logo"] else
           "**%s**" % brand["organisation"] if brand["organisation"] else ""]
    top += [brand["header"]] if brand["header"] else []
    return [y for x in top if x for y in (x, "")], (["", brand["footer"]] if brand["footer"] else [])


DIAGRAM_CREATE = ("Diagram: sent as its source. To show the picture, paste the source into the page's diagram tool and republish; "
                  "quote that page version when you record a yes.")
DIAGRAM_UPDATE = "Diagram: this update replaces the whole page, a picture drawn on it included. Draw it again from the source afterwards."


def _fetch_house_first(args, store, folder, house, again):
    """The sentence that asks for a house kept on a page to be fetched, or None when it is not needed."""
    work = next((r for r in store["records"] if r["kind"] == "work"), None)
    ref = value(work, "house") if work else ""
    if args.house or not _LINK.match(ref) or os.path.isfile(os.path.join(folder, "house.md")):
        return None
    return ("Fetch the house first: %s\nThe page body is one fenced code block. Write the text between its first and last "
            "fence lines to house.md beside work.md, character for character, and never save to the page.\n"
            "Then run this command again: %s" % (ref, again))


def _space(dest):
    sec = dest["sections"].get("sign-off brief", {})
    got = lambda k: sec[k][0] if k in sec and given(sec[k][0]) else ""
    return "space %s (space ID %s)" % (got("space key"), got("space id")) if got("space key") else "space ID " + got("space id")


def _where_page(dest, under=None):
    """`page 4410 in space CHG (space ID 65540), <link>`, or, for the last page of an arrangement already recorded,
    `page 4502 (Requirements / Sign-off) in space CHG (space ID 65540)`; `under` is (that page ID, its path)."""
    sec = dest["sections"].get("sign-off brief", {})
    got = lambda k: sec[k][0] if k in sec and given(sec[k][0]) else ""
    if under:
        return "page %s (%s) in %s" % (under[0], under[1], _space(dest))
    return "page %s in %s%s" % (got("parent page id"), _space(dest), ", " + got("parent page") if got("parent page") else "")


def _create_under(dest, face):
    """([lines that make the pages the brief sits under], the `Create under:` line): flat
    under the parent page unless the house states an arrangement for the face; the pages the Work does not yet record are
    to be found or created, in order, and each ID is recorded so it is never looked up again (ADR 0038)."""
    titles = page_path(dest, face)
    if not titles:
        return [], "Create under: " + _where_page(dest)
    pages = resolve_path(dest, titles)
    need = [p for p in pages if not p[2]]
    if not need:
        return [], "Create under: " + _where_page(dest, (pages[-1][2], pages[-1][1]))
    first = pages[len(pages) - len(need)]
    steps = ["Pages the brief goes under, to find or create first, in order. They hold no brief (find the page with that title "
             "directly under its parent; if there is none, create it with an empty body):"]
    lines = []
    for n, (title, path, _, parent) in enumerate(need, 1):
        steps.append('  %d. "%s", directly under %s' % (n, title, "page " + parent if parent else "the page made in %d" % (n - 1)))
        above = " / ".join(path.split(" / ")[:-1])
        lines.append("- Page: %s, page <page ID>, parent %s" % (path, parent or "<page ID of %s>" % above))
    record = ['Then add under "### Destinations" at the end of the Work record in work.md (make the heading if it is missing), '
              "filling each <page ID> from the reply:"] + lines
    return steps + record, ('Create under: the page "%s" made or found above, in %s. The brief is one more new page, beneath it, with the '
                             "Title above." % (titles[-1], _space(dest)))


def _made_line(store, skeleton, empty):
    base = store.get("baseline")
    return "Made: %s, from %s, %s, %s" % (
        _today(), "baseline " + base["name"] if base else "records version " + skeleton["version"],
        _plural(skeleton["count"], "finding"), _plural(empty, "empty slot"))


def _approval_line(house):
    if approval_of(house) != "page comment":
        return []
    return ["Approval: a yes may be a comment on the page. When the person says an approver answered there, read the page's "
            "comments and take the approver's name, date and own words from them. A yes said in a session or forwarded by email "
            "is recorded the same way."]


def _then_add(lines, fill):
    return ["Then add under \"### Published\" at the end of the Work record in work.md (above its next \"## \" line; make the "
            "heading if it is missing), filling %s from the reply:" % fill] + lines


def _page_note(face, store, live_work, house, rel, skeleton, empty, title):
    """The note for a brief that is a Confluence page (the sign-off brief, the Scope brief, the Delivery plan): a page
    to make, a page to update, or nothing to send to (ADR 0026, 0029, 0031). The three go under the parent the house
    stores for the sign-off brief, and each is recorded under its own name."""
    dest, key = house.places(), face["name"]
    before = last_sent(live_work).get(key)
    out = ["Note for: " + rel, _made_line(store, skeleton, empty)]
    base = store.get("baseline")
    kept = "baseline " + base["name"] if base else "records version " + skeleton["version"]
    if before is None and not section_is_set(dest, "sign-off brief"):
        return out + ["Send as: nothing yet. This house has no place for the %s." % face["title"],
                      "Hand to the person: %s and this note." % rel, "To set a place: run the adopt-house skill."]
    out += ["Send as: a Confluence page", "Title: " + title]
    if before:
        out += ["Update: page %s, %s (last sent %s as version %s)" % (before["page"], before["link"], before["date"], before["version"]),
                "First get the page: the update needs its latest snapshot token, and it replaces the whole body."]
        line, fill = "- %s: page %s, version <version>, %s, %s, %s" % (key, before["page"], _today(), kept, before["link"]), "<version>"
    else:
        steps, under = _create_under(dest, face)
        out += steps + [under]
        line, fill = "- %s: page <page ID>, version <version>, %s, %s, <link>" % (key, _today(), kept), "<page ID>, <version> and <link>"
    return out + ["Body: the whole text of %s, as written" % rel] + (_approval_line(house) if key == "signoff" else []) + _then_add([line], fill)


def _boards(house):
    """[(line key, item type, project key, which)] for the boards in play for a Feature: the delivery board first,
    then the business board. A board is in play when its section is set and the hierarchy gives a Feature type for it;
    the item types and projects come from those two files and nowhere else (ADR 0026)."""
    dest = house.places()
    business, delivery = feature_types(house)
    out = []
    for key, kind, board, which in (("tracker", delivery, "delivery board", "Delivery"), ("business item", business, "business board", "Business")):
        if kind and section_is_set(dest, board) and (key == "tracker" or out):
            out.append((key, kind, dest["sections"][board]["project key"][0], which))
    return out


def _handover_note(face, store, live_work, house, rel, skeleton, empty, feature, again):
    """(the note's lines, the business item's body or None) for a Feature's handover brief: one of the four states
    of ADR 0026, by what the house stores and what the Feature says."""
    out, base = ["Note for: " + rel, _made_line(store, skeleton, empty)], store.get("baseline")
    kept = "baseline " + base["name"] if base else "records version " + skeleton["version"]
    boards, who = _boards(house), feature["id"]
    tracker, business = value(feature, "tracker"), value(feature, "business item")
    if not boards:
        if not tracker:
            return out + ["Send as: nothing yet. This house has no place for the %s." % face["title"],
                          "Hand to the person: %s and this note." % rel, "To set a place: run the adopt-house skill."], None
        return out + ["Send as: a Jira item",
                      "Update: item %s, body: the whole text of %s" % (tracker, rel)] + _then_add(
            ["- handover %s: item %s, %s, %s, <link>" % (who, tracker, _today(), kept)], "<link>"), None
    have = {"tracker": tracker, "business item": business}
    need = [b for b in boards if not have[b[0]]]
    title = feature["name"]
    if need:
        out += ["Send as: " + ("Jira items" if len(need) > 1 else "a Jira item")]
        out += ['Create: an item of type %s in project %s, title "%s", body "Brief to follow."' % (kind, project, title)
                for _, kind, project, _ in need]
        lines = ["- %s: <%s>" % ({"tracker": "Tracker", "business item": "Business item"}[key], "key of the " + kind if len(boards) > 1 else "key")
                 for key, kind, _, _ in need]
        out += ["Then add to the Feature in work.md, among its own lines above its first \"###\" heading, filling %s from the reply:"
                % ("the key" if len(need) == 1 else "each key")] + lines
        out += ["Then run this command again: " + again]
        return out, None
    out += ["Send as: " + ("Jira items" if len(boards) > 1 else "a Jira item"),
            "Update: item %s, body: the whole text of %s" % (tracker, rel)]
    body = None
    if len(boards) > 1:
        out += ["Update: item %s, body: the whole text of outbox/business-%s.md" % (business, who)]
        link = read_hierarchy(house.text("hierarchy.md") or "")["link"]
        if link:
            out += ['Link: type "%s", from %s to %s. If your tools cannot link items, skip this: each body names the other.'
                    % (link[0], tracker, business)]
        body = _business_body(store, live_work, house, feature)
    lines = ["- handover %s: item %s, %s, %s, <link>" % (who, tracker, _today(), kept)]
    if body is not None:
        lines.append("- business %s: item %s, %s, %s, <link>" % (who, business, _today(), kept))
    return out + _then_add(lines, "each <link>" if len(lines) > 1 else "<link>"), body


def _business_body(store, live_work, house, feature):
    """The business item's body: four lines at most and no requirement, built with no template (ADR 0026)."""
    words, work = house.words(), next((r for r in store["records"] if r["kind"] == "work"), None)
    sent = last_sent(live_work).get("signoff")
    parts = [("Intent", value(feature, "intent")), ("Goal", value(work, "goal") if work else ""),
             ("Requirements and sign-off", sent["link"] if sent else ""), ("Delivery item", value(feature, "tracker"))]
    return "\n\n".join("%s: %s" % (words.get(k), _esc(v)) for k, v in parts if v) + "\n"


def send(args, got, face, again):
    """`bundle <face> --outbox`, after the brief is made: write the copy to send and the note, and print the note."""
    store, folder, record, house, _, name, path = got
    rel = face_file(face, record)
    words = house.words()
    with open(os.path.join(folder, *rel.split("/")), "rb") as f:
        sent = f.read()  # the brief in faces/ is the copy: one text (ADR 0026)
    final = sent.decode("utf-8").replace("\r\n", "\n")
    sk = build_face(store, house.template(face, name).replace("\r\n", "\n"), name, words, where=path, feature=record,
                    face=face, house=house)
    carried = _carry(sk, final)
    lines = final.rstrip("\n").split("\n")
    live = read_workspace(folder)
    work = next((r for r in live["records"] if r["kind"] == "work"), None)
    empty = len(sk["slots"]) - len(carried)
    copy = os.path.join("outbox", os.path.basename(rel))
    files = {copy: sent}
    if record is None:
        name_of_work = next((r["name"] for r in store["records"] if r["kind"] == "work"), "")
        note = _page_note(face, store, work, house, copy, sk, empty, "%s: %s" % (name_of_work, words.get(face["word"])))
        if "```mermaid" in lines and "Send as: a Confluence page" in note:  # what the page will do to a picture drawn on it by hand (ADR 0038)
            note.append(DIAGRAM_UPDATE if any(l.startswith("Update: page") for l in note) else DIAGRAM_CREATE)
    else:
        note, business = _handover_note(face, store, work, house, copy, sk, empty, record, again)
        if business is not None:
            files["outbox/business-%s.md" % record["id"]] = business
    files[copy[:-3] + ".note.md"] = "\n".join(note) + "\n"
    os.makedirs(os.path.join(folder, "outbox"), exist_ok=True)
    for rel_name, text in files.items():
        with open(os.path.join(folder, rel_name), "wb") as f:
            f.write(text if isinstance(text, bytes) else text.encode("utf-8"))
    print(files[copy[:-3] + ".note.md"], end="")
    return 0


# ---------------------------------------------------------------------------
# The test landing (ADR 0026): the helper's made-up records, made through the house, for the person to see
# on their own site before a place is trusted.
# ---------------------------------------------------------------------------

LANDING_LINE = "Landing test from the BA skills. Made-up content, safe to delete."
_LANDINGS = (("sign-off brief", "Sign-off brief", "signoff"), ("delivery board", "Delivery board", "handover"),
             ("business board", "Business board", "business"))


def _landing_bodies(house, store, feature):
    """{name: text} of the three test bodies through this house, each opening with the landing line."""
    words, out = house.words(), {}
    for key, face in ((k, FACES[k]) for k in ("signoff", "handover")):
        form = _pick_template(face, house, "")[0]
        sk = build_face(store, house.template(face, form).replace("\r\n", "\n"), form, words, where=house.where("templates/" + form),
                        feature=feature if face["for"] else None, face=face, house=house)
        filled = {i: ["A passage written for this brief goes here (landing test)."] for i in range(len(sk["slots"]))}
        out[key] = [LANDING_LINE, ""] + _fill(sk, filled).rstrip("\n").split("\n")
    out["business"] = [LANDING_LINE, "", _business_body(store, None, house, feature).rstrip("\n")]
    return {k: "\n".join(v) + "\n" for k, v in out.items()}


def landing(args):
    """`ba bundle landing --house <house>`: write the test bodies of the sections not yet proved, and print the note."""
    if not args.house:
        print("ba bundle: landing needs --house <the house>: the folder, or the file that holds it as a pack, whose places "
              "are to be tested. Fix: %s bundle landing --house house.md" % BA, file=sys.stderr)
        return 2
    own = _open(os.path.abspath(args.house))
    if own is None:
        print("ba bundle: --house names '%s', and there is no such folder or file. Give the house: a folder that holds "
              "words.md and templates/, or the file that holds them as a pack." % args.house, file=sys.stderr)
        return 2
    where = find_workspace(args.folder)  # a Work here may name its own parent page (ADR 0038)
    work = next((r for r in read_workspace(where)["records"] if r["kind"] == "work"), None) if where else None
    house = House(os.path.abspath(args.house), own, work)
    store, feature = _sample()
    dest, types = house.places(), dict(zip(("business board", "delivery board"), feature_types(house)))
    sec = dest["sections"]
    proved, unset, todo = [], [], []
    for name, shown, key in _LANDINGS:
        if not section_is_set(dest, name) or (name != "sign-off brief" and not types[name]):
            unset.append(name)
        elif landing_state(dest, name, types.get(name))[0] == "proved":
            proved.append(name)
        else:
            todo.append((name, shown, key))
    out = ["Landing test: made-up content, safe to delete. Sections already proved are left out."]
    if proved:
        out.append("Already proved, left out: %s." % ", ".join(proved))
    if unset:
        out.append("Not set, so not landed: %s." % ", ".join(unset))
    if not todo:
        out.append("Nothing to land: every section that is set is proved.")
        print("\n".join(out))
        return 0
    bodies, words, files = _landing_bodies(house, store, feature), house.words(), {}
    got = lambda name, k: sec[name][k][0]
    for n, (name, shown, key) in enumerate(todo, 1):
        rel = "outbox/landing-%s.md" % key
        files[rel] = bodies[key]
        title = "%s (landing test, safe to delete)" % (words.get("Sign-off brief") if key == "signoff" else feature["name"])
        out += ["", "Landing %d: %s" % (n, name)]
        if key == "signoff":
            out += ["Title: " + title, "Create under: " + _where_page(dest), "Body: the whole text of %s, as written" % rel]
            fill, line = "<page ID> and <link>", "- Landed: %s, parent %s, test page <page ID>, <link>" % (_today(), got(name, "parent page id"))
        else:
            out += ['Create: an item of type %s in project %s, title "%s", body: the whole text of %s' % (types[name], got(name, "project key"), title, rel)]
            fill, line = "<key> and <link>", "- Landed: %s, %s, %s, test item <key>, <link>" % (_today(), got(name, "project key"), types[name])
        kept = 'destinations.md' if own.form != "a pack" else 'the "=== destinations.md ===" part of %s' % os.path.basename(own.path)
        verb, old = ("write", "in place of the Landed line there, ") if "landed" in sec[name] else ("add", "")
        if key == "signoff" and dest["own"]:  # the Work's own page: the proof is written on the Work, not in the house
            out += ['Then, once the person says yes, %s under "### Destinations" at the end of the Work record in work.md, %sfilling %s '
                    "from the reply:" % (verb, old, fill), line]
            continue
        out += ["Then, once the person says yes, %s under \"## %s\" in %s, %sfilling %s from the reply:" % (verb, shown, kept, old, fill), line]
    files["outbox/landing.note.md"] = "\n".join(out) + "\n"
    folder = os.path.abspath(args.folder or ".")
    os.makedirs(os.path.join(folder, "outbox"), exist_ok=True)
    for rel, text in files.items():
        with open(os.path.join(folder, rel), "w", encoding="utf-8", newline="") as f:
            f.write(text)
    print(files["outbox/landing.note.md"], end="")
    return 0


# ==== helper/src/fix.py =====================================================
"""Fix: `check --fix`, which gives records IDs after a backup and changes nothing else (ADR 0011).

Owns the plan (_plan_ids), applying it to the lines of the files, and the backup. Must not know: findings or briefs.
"""

def _highest_numbers(store):
    """The highest number held for each ID letter, in the records and in baselines/ if it exists."""
    top = {}
    def note(rid):
        m = re.match(r"^([A-Z]{1,2})-(\d+)$", rid or "")
        if m:
            top[m.group(1)] = max(top.get(m.group(1), 0), int(m.group(2)))
    for r in store["records"]:
        note(r["id"])
    base = os.path.join(store["folder"], "baselines")
    for where, _, names in os.walk(base):
        for name in names:
            if name.endswith(".md"):
                try:
                    with open(os.path.join(where, name), encoding="utf-8", newline="") as f:
                        for r in read_store([(name, f.read())])["records"]:
                            note(r["id"])
                except (OSError, UnicodeDecodeError):
                    pass
    return top


def _set_value(raw, key, new):
    """`raw` (a line with its ending) with the value of its `key` line replaced; None if it is not that line."""
    body = raw.rstrip("\r\n")
    m = re.match(r"(?i)^((?:\ufeff|\s)*(?:[-*+]\s+)?(?:\*\*)?%s(?:\*\*)?\s*:(?:\*\*)?)(\s*)(.*?)(\s*)$" % re.escape(key), body)
    if not m:
        return None
    return m.group(1) + (m.group(2) or " ") + new + m.group(4) + raw[len(body):]


def _plan_ids(store):
    """What --fix would do: ({file: {line: new text}}, {file: {after line: new line}}, [what changed])."""
    skip = _ambiguous_ids(store)
    top = _highest_numbers(store)
    todo = [r for r in store["records"] if id(r) not in skip and not _ASSIGNED.match(r["id"])]
    replace, insert, notes, new_ids = {}, {}, [], {}
    for r in todo:
        letter = ID_LETTER[r["kind"]]
        top[letter] = top.get(letter, 0) + 1
        rid = "%s-%d" % (letter, top[letter])
        if r["id"]:
            new_ids[r["id"]] = rid
        lines = store["files"][r["file"]]
        where = "%s '%s'" % (label(r["kind"]), r["name"])
        line = r["fields"]["id"]["line"] if "id" in r["fields"] else r["empty"].get("id")
        edited = _set_value(lines[line - 1], "ID", rid) if line else None
        if edited is not None:
            replace.setdefault(r["file"], {})[line] = edited
            notes.append("%s line %d: ID '%s' -> %s (%s)" % (r["file"], line, r["id"], rid, where)
                         if r["id"] else "%s line %d: ID line filled in: %s (%s)" % (r["file"], line, rid, where))
        else:
            eol = re.search(r"(\r\n|\r|\n)$", lines[r["line"] - 1])
            eol = eol.group(1) if eol else "\n"
            # Where a person would write it: the first field, after the blank line under the heading if there is one.
            at = r["line"]
            while at < len(lines) and not lines[at].strip():
                at += 1
            alone = at >= len(lines) or lines[at].lstrip().startswith("#")  # no field follows: keep a blank line after
            if at == r["line"] or at >= len(lines):
                at, alone = r["line"], False
            insert.setdefault(r["file"], {})[at] = ("- ID: %s%s" % (rid, eol if alone else ""), eol)
            notes.append("%s after line %d: added '- ID: %s' (%s)" % (r["file"], at, rid, where))
    # A handle is rewritten wherever a record is named by it: About, a Feature line, Sliced from, Flow. A name is not.
    new_low = {k.lower(): v for k, v in new_ids.items()}
    for r in store["records"]:
        for key in ("about", "feature", "sliced from", "flow"):
            field = r["fields"].get(key)
            if not field or not any(x.lower() in new_low for x in _parts(field["value"])):
                continue
            lines = store["files"][r["file"]]
            new = re.sub(r"[^,]+", lambda m: m.group(0).replace(m.group(0).strip(), new_low.get(m.group(0).strip().lower(), m.group(0).strip()), 1)
                         if m.group(0).strip() else m.group(0), field["value"])
            edited = _set_value(lines[field["line"] - 1], label(key), new)
            if edited is not None:
                replace.setdefault(r["file"], {})[field["line"]] = edited
                notes.append("%s line %d: %s '%s' -> '%s'" % (r["file"], field["line"], label(key), field["value"], new))
    return replace, insert, notes


def _apply(store, replace, insert):
    """The new text of every file that changes: {file: text}."""
    out = {}
    for file in sorted(set(replace) | set(insert)):
        result = []
        lines = store["files"][file]
        for n, raw in enumerate(lines, 1):
            raw = replace.get(file, {}).get(n, raw)
            if n in insert.get(file, {}):
                text, eol = insert[file][n]
                last = n == len(lines) and not re.search(r"[\r\n]$", raw)
                result.append(raw if not last else raw + eol)
                result.append(text if last else text + eol)
            else:
                result.append(raw)
        out[file] = "".join(result)
    return out


def _backup_and_write(folder, changed):
    """Copy each file that will change into backup/<timestamp>/, then write the new text."""
    stamp, n = time.strftime("%Y%m%d-%H%M%S"), 1
    while True:
        dest = os.path.join(folder, "backup", stamp if n == 1 else "%s-%d" % (stamp, n))
        try:
            os.makedirs(dest)
            break
        except FileExistsError:
            n += 1
    for file in changed:
        target = os.path.join(dest, file)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(os.path.join(folder, file), target)
    for file, text in changed.items():
        with open(os.path.join(folder, file), "w", encoding="utf-8", newline="") as f:
            f.write(text)
    return "backup/" + os.path.basename(dest)


# ==== helper/src/check.py ===================================================
"""Check: the findings worked out from the records, and the `check` verb that reports them (ADR 0019).

Owns _findings (the one place a new kind of finding joins), coverage of features, and the report. Findings on
briefs come from facecheck and are added here. Exit code 0 whatever is found.
"""

def _findings(store, freezing=None):
    """Every problem to show, in file and line order. The place for new kinds of finding to join. `freezing` is the name of
    the baseline `ba baseline` is about to make: an approval written ahead of it names a baseline that will exist (ADR 0038)."""
    found = list(store["problems"])
    skip = _ambiguous_ids(store)
    settled = [r for r in store["records"] if not _ASSIGNED.match(r["id"]) and id(r) not in skip and (
        value(r, "answer") if r["kind"] == "question" else status_of(r) == "confirmed")]
    if settled:
        found.append(_problem("no-id", {"file": settled[0]["file"]}, settled[0]["line"], count=len(settled),
                              first=settled[0]["line"]))
    found += _coverage(store)
    found += _empty_features(store)
    work = next((r for r in store["records"] if r["kind"] == "work"), None)
    if work and store["folder"] and value(work, "house"):
        found += _house(store["folder"], work, None)[1]
    if work:
        found += _destination_findings(work)
        found += _unknown_baselines(store, work, freezing)
        found += _earlier_approvals(store, work)
        found += _forecast_findings(store, work)
    order = {file: i for i, file in enumerate(store["files"])}
    found.sort(key=lambda p: (order.get(p["file"], 0), p["line"], p["level"] != "finding"))
    return found


def _feature_shown(f, live=()):
    """A feature as a fix message names it: by name, or by ID when the name could not be read back as this
    feature: it holds a comma, or another of the `live` features has the same name."""
    same = [x for x in live if x is not f and x["name"].strip().lower() == f["name"].strip().lower()]
    return f["name"] if "," not in f["name"] and not same else f["id"] or f["name"]


def _feature_gap(store, req):
    """None when the requirement is in a Feature, or is deliberately in none (`- Feature: none`); else (the part that fails, its line, the Feature it names or None).
    A requirement is in a Feature when it has a `Feature` line and every part names a Feature that is not withdrawn.
    With no line at all the part is ''."""
    field = req["fields"].get("feature")
    if not field:
        return "", req["empty"].get("feature"), None
    if left_out_of_features(req) is not None:
        return None  # deliberately in no feature: nothing to say
    for part in _parts(field["value"]):
        f = feature_named(store["records"], part)
        if f is None or status_of(f) == "withdrawn" or kept_original(store, f):
            return part, field["line"], f
    return None


def _coverage(store):
    """Once the workspace holds one Feature that is not withdrawn, each requirement to deliver is in one
    (ADR 0024); each that is not is `missing`. Before that nothing is said: a small job needs no features."""
    recs = store["records"]
    live = live_features(store)
    if not live:
        return []
    add = "- Feature: <one or more of %s, separated by commas>" % ", ".join("'%s'" % _feature_shown(f, live) for f in live)
    out = []
    for r in _loose(store):
        part, line, f = _feature_gap(store, r)
        if not part and "feature" not in r["fields"]:
            if line is None:
                last = max([x["line"] for x in r["fields"].values()] + list(r["empty"].values()) + [r["line"]])
                what, at = "'Feature' line on this requirement, and it is one to deliver", "after line %d" % last
            else:
                what, at = "'Feature' line on this requirement, and it is one to deliver", "in place of line %d" % line
        elif f is None:
            what = "Feature for this requirement: line %d names '%s', which is not a Feature record" % (line, part)
            at = "in place of line %d" % line
        else:
            parts = ["%s '%s'" % (x["id"], x["name"]) if x["id"] else "'%s'" % x["name"]
                     for x in recs if x["kind"] == "feature" and x is not f
                     and feature_named(recs, " ".join(_parts(value(x, "sliced from"))[:1])) is f]
            into = (parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]) if parts else ""
            what = ("Feature for this requirement: line %d names '%s', which was sliced into %s" % (line, part, into)
                    if kept_original(store, f) else "Feature for this requirement: line %d names '%s', which is withdrawn%s" % (
                        line, part, ". It was sliced into " + into if into else ""))
            at = "in place of line %d" % line
        out.append(_problem("missing", r, r["line"], what=what, key="Feature", at=at, add=add))
    return out


def _loose(store):
    """The requirements to deliver that are in no Feature and not deliberately so: what coverage reports."""
    return [r for r in to_deliver(store) if _feature_gap(store, r) is not None]


def _empty_features(store):
    """One note for each Feature that is not withdrawn and has no requirement naming it. Information only: a
    Feature may be written before the requirements that belong in it."""
    live = live_features(store)
    loose = _loose(store)
    out = []
    for f in live:
        if _feature_reqs(store, f):
            continue
        name = _feature_shown(f, live)
        if loose:
            r = loose[0]
            file = r["file"]
            after = max([x["line"] for x in r["fields"].values()] + list(r["empty"].values()) + [r["line"]])
            which = "a requirement that belongs in it (one in no feature: '%s')" % r["name"]
            add = "- Feature: " + name
        else:
            file, after = f["file"], f["end"]
            which = "a requirement that belongs in it"
            add = "a Requirement record with the line '- Feature: %s' (see the shape: %s --shape requirement)" % (name, CHECK)
        out.append(_problem("not-given", f, f["line"], key="Requirement in this feature", unknown=which,
                            fixfile=file, after=after, add=add))
    return out


def _destination_findings(work):
    """The Work's `### Destinations` that cannot be used (ADR 0038): a Parent page ID without its Space ID or the reverse (`missing`,
    with the line to add), and a `Landed` or `Page` item that cannot be read (`bad-value`, with the line in its form)."""
    keys, _, bad = work_destinations(work)
    if not work["destinations"]:
        return []
    out, last = [], max(x["line"] for x in work["destinations"])
    for have, need, shown, form in (("parent page id", "space id", "Space ID", "- Space ID: <the number Confluence gives the space>"),
                                    ("space id", "parent page id", "Parent page ID", "- Parent page ID: <the number Confluence gives the page>")):
        if given(keys.get(have, ("",))[0]) and not given(keys.get(need, ("",))[0]):
            out.append(_problem("missing", work, work["destinations span"][0], what="'%s' line under '### Destinations'" % shown,
                                key=shown, at="after line %d" % last, add=form))
    for key, shown, what in (("parent page id", "Parent page ID", "page"), ("space id", "Space ID", "space")):
        val, line = keys.get(key, ("", 0))
        if given(val) and not val.isdigit():  # as `check --adopt` says of a house's
            out.append(_problem("bad-value", work, line, key=shown, value=val, allowed=[],
                                why="It is the number Confluence gives the %s." % what, write="- %s: <the number>" % shown))
    landed = keys.get("landed")
    if landed and given(landed[0]) and not re.search(r"\b(parent \d+|[A-Z][A-Z0-9]*, [^,]+, test item)", landed[0]):
        out.append(_problem("bad-value", work, landed[1], key="Landed", value=landed[0], allowed=[],
                            why="It says what a test landing proved, in the form the adopt-house skill's note gives.",
                            write="- Landed: <date>, parent <page ID>, test page <page ID>, <link>"))
    for line in bad:
        text = next(x["text"] for x in work["destinations"] if x["line"] == line)
        out.append(_problem("bad-value", work, line, key="Page", value=text.partition(":")[2].strip(), allowed=[],
                            why="A page is written with its path, its ID and the ID of the page it is under.",
                            write="- Page: <title> / <title>, page <page ID>, parent <page ID>"))
    return out


def _unknown_baselines(store, work, freezing=None):
    """An approval that names a baseline that is not in baselines/ is `bad-value`, with the names there are (ADR 0034),
    unless it names the one being frozen now."""
    if not store["folder"]:
        return []
    have = [b["name"] for b in _baselines(store["folder"])]
    out = []
    for a in work["approvals"]:
        if a["baseline"] and a["baseline"] != freezing and _manifest(store["folder"], a["baseline"]) is None:
            fix = ("change line %d to end: baseline <one of: %s> (or records version <8 characters> from the brief's last line)"
                   % (a["line"], ", ".join(have)) if have else
                   "change line %d to end: records version <8 characters> from the brief's last line, or freeze the "
                   "records first with %s" % (a["line"], _baseline_cmd(_next_name(store["folder"], "v1"))))
            out.append(_problem("bad-value", work, a["line"], key="baseline", value=a["baseline"], allowed=have,
                                why="There is no baseline of that name.", says="In %s, %s." % (work["file"], fix)))
    return out


def _earlier_approvals(store, work):
    """One note for each approver whose last answer was to records that have changed since."""
    version, last = version_of(store), {}
    for a in work["approvals"]:
        last[a["name"].lower()] = a
    out = []
    for a in sorted(last.values(), key=lambda a: a["line"]):
        if a["baseline"] and store["folder"] and _manifest(store["folder"], a["baseline"]) is None:
            continue  # `bad-value` says so
        if not approval_stands(store, a):
            said = "approved" if a["decision"] == "approved" else "asked for changes to"
            then = {"versions": " (baseline %s then, records version %s now)" % (a["baseline"], version)} if a["baseline"] else {}
            out.append(_problem(
                "stale", work, a["line"], old=a["version"], new=version, **then,
                what="%s %s an earlier version of the records" % (a["name"], said),
                how="That answer holds for the records as they were. Whether the changes go back to %s is your call; status "
                    "says what has changed. If they approve these records, add after line %d: - %s: <approved or changes "
                    "asked>, <date>, records version %s, \"<their words>\"" % (a["name"], a["line"], a["name"], version)))
    return out


def _forecast_findings(store, work):
    """The lines of `### Delivery` and `### Actuals` that cannot be read, each with the line in its form, and the lines
    those sections lack (ADR 0031). A Work with neither section is not asked about a forecast."""
    if not (work["delivery span"] or work["actuals span"]):
        return []
    fc, out = forecast_for(store), []
    for i in fc["issues"]:
        out.append(_problem("bad-value", work, i["line"], key=i["key"], value=i["value"], allowed=[], why=i["why"], write=i["write"]))
    for section, keys in (("delivery", (("start", "Start", "the start date", START_FORM), ("velocity", "Velocity", "the velocity", VELOCITY_FORM))),
                          ("actuals", (("read", "Read", "the day the actuals were read", READ_FORM),))):
        if not work[section + " span"]:
            continue
        after = max([x["line"] for x in work[section]] + [work[section + " span"][0]])
        out += [_problem("not-given", work, after, key=label_, after=after, unknown=unknown, add=form)
                for key, label_, unknown, form in keys if key in fc["missing"]]
    return out


def _ambiguous_ids(store):
    """Records whose ID cannot be trusted: used twice, or the wrong letter, or not an ID at all."""
    counts = {}
    for r in store["records"]:
        if r["id"]:
            counts[r["id"]] = counts.get(r["id"], 0) + 1
    bad = set()
    for r in store["records"]:
        m = _ASSIGNED.match(r["id"])
        if r["id"] and (counts[r["id"]] > 1 or (m and m.group(1) != ID_LETTER[r["kind"]])
                        or not (m or _HANDLE.match(r["id"]))):
            bad.add(id(r))
    return bad


def _listing(store):
    """One line a record, in reading order: kind, ID or handle, where it stands, name. What the workspace
    holds, so a reader of check need not open the files to learn it."""
    first = next(iter(store["files"]), "work.md")
    out = []
    for r in store["records"]:
        if r["kind"] == "question":
            stands = "answered" if value(r, "answer") else "assumed" if value(r, "working answer") else "open"
        elif r["kind"] == "observed":
            stands = standing_of(r)
        else:
            stands = status_of(r)
        out.append("  %s%s (%s): %s%s" % (label(r["kind"]), " " + r["id"] if r["id"] else ", no ID", stands, r["name"],
                                          "" if r["file"] == first else " [%s]" % r["file"]))
    return out


def _report(store, faces=()):
    """The plain-text report: grouped by file, every finding ending with its fix, a summary last.
    `faces` are the findings on the files in faces/, listed after the records' files."""
    shown = [k for k in KINDS if k not in ("feature", "observed") or any(r["kind"] == k for r in store["records"])]
    out = ["Records: " + ", ".join("%s %d" % (label(k), len([r for r in store["records"] if r["kind"] == k]))
                                   for k in shown)]
    out += _listing(store)
    found = _findings(store) + sorted(faces, key=lambda p: (p["file"], p["line"]))
    for file in list(store["files"]) + sorted({p["file"] for p in faces}):
        mine = [p for p in found if p["file"] == file]
        if mine:
            out += ["", file]
        for p in mine:
            here = "line %d" % p["line"] + (", %s '%s'" % (label(p["kind"]), p["name"]) if p["kind"] else "")
            out += ["  %s: %s: %s" % (here, p["level"], p["message"]), "    Fix: " + p["fix"]]
    nf = len([p for p in found if p["level"] == "finding"])
    ni = len(found) - nf
    if nf > 1:
        out += ["", "Line numbers are as the files are now. After a fix that adds or deletes a line, run check "
                "again before the next fix."]
    out += ["", "Summary: %d finding%s, %d information." % (nf, "" if nf == 1 else "s", ni)]
    return out


def check(args):
    kinds = ", ".join(KINDS)
    if args.adopt:
        return adopt(args.adopt)
    if args.shape is not None:
        if not args.shape:
            print("A filled-in record of each kind. Copy its shape.")
            for kind in KINDS:
                print("  %s --shape %s" % (CHECK, kind))
            print("  %s --shape all    (all five, in one call)" % CHECK)
            return 0
        kind = args.shape.lower()
        if kind == "all":
            sys.stdout.write(SHAPE_NOTE + "\n".join(shape_text(k) for k in FIRST_FIVE))
            return 0
        if kind not in SHAPES:
            print("There is no '%s' record. The kinds are: %s, or all. Try: %s --shape all"
                  % (args.shape, kinds, CHECK), file=sys.stderr)
            return 2
        sys.stdout.write(SHAPE_NOTE + shape_text(kind))
        return 0
    folder = find_workspace(args.folder)
    if folder is None:
        where, misplaced = _no_workspace(args.folder, CHECK)
        print(misplaced or "No work.md %s, so there is nothing to check yet. A workspace is a folder holding "
              "work.md. To start one, create work.md with a Work record: "
              "%s --shape work" % (where, CHECK))
        return 0
    store = read_workspace(folder)
    print("Workspace: " + folder)
    if args.fix:
        replace, insert, notes = _plan_ids(store)
        if not notes:
            print("Nothing to fix: every record that can have an ID has one.")
        else:
            changed = _apply(store, replace, insert)
            where = _backup_and_write(folder, changed)
            print("Backup of %s written to %s/" % (", ".join(sorted(changed)), where))
            print("Changed (line numbers are as they were before the change):")
            for note in notes:
                print("  " + note)
            print("Nothing else was changed. Checking again:")
            store = read_workspace(folder)
    print("\n".join(_report(store, _face_findings(store, args.house))))
    return 0


# ==== helper/src/adopt.py ===================================================
"""Adopt: `ba check --adopt <house>`, the checks made once when a house is adopted (ADR 0025).

Owns the report of a house (what it holds, what each template covers, where its briefs go) and every finding
about it, in the catalogue's kinds. It needs no workspace and writes nothing. Must not know: how a brief is
checked against records (facecheck), or how destinations are landed (the adopt-house skill).
"""

_LEVEL_NAMES = ("Work", "Feature", "Requirement")
_APPROVALS = ("reply", "page comment")
_GOES = (("sign-off brief", "Sign-off brief"), ("business board", "Business board"), ("delivery board", "Delivery board"))


def _lost_what_a_job_carries(face, cov, store, feature, words, here):
    """A job whose section carries a block or a slot in a shipped template of this face and carries neither here is
    `missing`, naming the job and what it lost. Structural: block kinds and the number of slots, never wording, so a
    house may reword every heading and every slot instruction (ADR 0025)."""
    kept, lost = cov["carries"], {}
    for name in House().templates(face):
        shipped = House().text("templates/" + name).replace("\r\n", "\n")
        theirs = build_face(store, shipped, name, words, feature=feature if face["for"] else None, face=face)["coverage"]["carries"]
        for job, c in theirs.items():
            if c["kinds"] or c["slots"]:  # the first shipped form that carries something: two forms' blocks are either-or
                lost.setdefault(job, {"kinds": list(c["kinds"]), "slots": c["slots"], "name": name})
    out = []
    for job in face["jobs"]:
        have, was = kept.get(job, {"kinds": [], "slots": 0, "line": 1}), lost.get(job)
        if job in cov["done"] and was and (was["kinds"] or was["slots"]) and not (have["kinds"] or have["slots"]):
            what = ["{block: %s}" % k for k in was["kinds"]] + (["a slot (> {slot: up to <number> words, from <what it draws on>})"] if was["slots"] else [])
            out.append(_problem(
                "missing", here, have.get("line", cov["first"]), what="block or slot under the job '%s' in this template. The shipped template %s has %s there"
                % (job, was["name"], " and ".join(what)), key="job", at="under the heading of the job '%s'" % job, add=" and ".join(what)))
    return out


def _template_checks(house, name, store, feature, words):
    """(the line that says what the template covers, its findings) for one template of the house."""
    face = next(f for f in FACES.values() if f["templates"].match(name))
    where = house.where("templates/" + name)
    sk = build_face(store, house.text("templates/" + name).replace("\r\n", "\n"), name, words, where=where,
                    feature=feature if face["for"] else None, face=face)
    cov, here = sk["coverage"], {"file": where}
    found = list(sk["problems"])
    left = {j: v for j, v in cov["omitted"].items() if j in face["jobs"]}
    for job in face["jobs"]:
        if job not in cov["done"] and job not in left:
            found.append(_problem(
                "missing", here, cov["first"], what="section for the job '%s' in this template" % job, key="job",
                at="under a section of this template", add="{job: %s}   To leave the job out instead, add before the first "
                "'## ' heading: {omit: %s, because <reason>}" % (job, job)))
    for job, (reason, line, text) in sorted(left.items(), key=lambda x: x[1][1]):
        if not reason:
            found.append(_problem("bad-value", here, line, key="omit", value="{%s: %s}" % ("omit", text), allowed=[],
                                  why="A job left out says why.", write="{omit: %s, because <reason>}" % job))
    found += _lost_what_a_job_carries(face, cov, store, feature, words, here)
    stands = "%d of %d jobs done" % (len(cov["done"]), len(face["jobs"]))
    if left:
        stands += ". Left out: " + ", ".join("%s (%s)" % (j, v[0] or "no reason given") for j, v in left.items())
    undone = [j for j in face["jobs"] if j not in cov["done"] and j not in left]
    if undone:
        stands += ". Not covered: " + ", ".join(undone)
    return "  templates/%s, %s: %s" % (name, face["title"], stands), found


def _hierarchy_checks(house):
    """(the Hierarchy lines, the findings) for hierarchy.md and the sections of destinations.md it must agree with."""
    text = house.text("hierarchy.md") or ""
    hier, here, found, lines = read_hierarchy(text), {"file": house.where("hierarchy.md")}, [], []
    dest = read_destinations(house.text("destinations.md") or "")
    seen = {}
    for row in hier["rows"]:
        level = row["level"].lower()
        if level not in LEVELS:
            found.append(_problem("bad-value", here, row["line"], key="Level", value=row["level"], allowed=list(_LEVEL_NAMES),
                                  why="A level is Work, Feature or Requirement.",
                                  write="one of %s in the first cell" % ", ".join(_LEVEL_NAMES)))
        elif level in seen:
            a, b = seen[level], row["line"]
            found.append(_problem(
                "ambiguous", here, b, what="Two rows of this table are for the level '%s' (lines %d and %d)." % (row["level"], a, b),
                one="keep line %d and delete line %d." % (a, b), two="keep line %d and delete line %d." % (b, a),
                check="%s --adopt <this house>" % CHECK))
        else:
            seen[level] = row["line"]
    feature = next((r for r in hier["rows"] if r["level"].lower() == "feature"), None)
    if feature and not feature["delivery"] and (section_is_set(dest, "delivery board") or feature["business"]):
        found.append(_problem("missing", here, feature["line"], what="item type for a Feature on the delivery board", key="cell",
                              at="in the Delivery board cell of line %d" % feature["line"],
                              add="the item type as the tracker names it. A house with one board uses the Delivery board column"))
    if feature and feature["business"] and feature["delivery"] and not hier["link"]:
        found.append(_problem("missing", here, feature["line"], what="'Link' line in this file, and a Feature is on two boards",
                              key="Link", at="after line %d" % (feature["line"] + 1), add="- Link: <the link type's name in the tracker>"))
    if "hierarchy.md" in house.own_files():  # a level with an item type goes nowhere until its board has a project (ADR 0038)
        for row in hier["rows"]:
            for board, cell in (("business", row["business"]), ("delivery", row["delivery"])):
                if cell and row["level"].lower() in LEVELS and not section_is_set(dest, board + " board"):
                    found.append(_problem(
                        "not-given", here, row["line"], key="Project key of the %s board, where %s is %s" % (
                            board, row["level"], _article(cell)),
                        after=row["line"], unknown="the project", add="- Project key: <the key>",
                        says="Items of this level go nowhere until the board has a project: add '- Project key: <the key>' under "
                             "'## %s board' in destinations.md." % board.title()))
    for row in hier["rows"]:
        if row["level"].lower() in LEVELS:
            on = ["%s on the %s board" % (t, b) for t, b in ((row["business"], "business"), (row["delivery"], "delivery")) if t]
            if on:
                link = ", linked as '%s'" % hier["link"][0] if hier["link"] and len(on) == 2 and row["level"].lower() == "feature" else ""
                lines.append("  %s: %s%s" % (row["level"].title(), ", ".join(on), link))
    return lines or ["  no item type is set"], found


def _article(word):
    return ("an " if word[:1].lower() in "aeiou" else "a ") + word


def _destination_checks(house):
    """(the Goes to lines, the findings) for destinations.md."""
    dest, here = read_destinations(house.text("destinations.md") or ""), {"file": house.where("destinations.md")}
    business, delivery = feature_types(house)
    types = {"business board": business, "delivery board": delivery}
    found, lines = [], []
    if "destinations.md" not in house.own_files():
        # The shipped file stands in, and it is not the person's to edit: one line about this house, not one a key.
        found.append(_problem("not-given", {"file": house.own.path if house.own.form == "a pack" else os.path.join(house.own.path, "destinations.md")}, 1, key="destinations.md",
                              says="Briefs go to outbox/ until this house has one. To set where they go, run the adopt-house skill."))
        return ["  %s: not set" % shown for _, shown in _GOES], found
    heading = {name: n for n, name in dest["headings"]}
    for name, shown in _GOES:
        sec = dest["sections"].get(name, {})
        get = lambda key: (sec.get(key, ("", 0))[0] if given(sec.get(key, ("",))[0]) else "")
        at = lambda key: sec[key][1] if key in sec else heading.get(name, 1)
        keys = ("Space ID", "Parent page ID") if name == "sign-off brief" else ("Project key",)
        for key in keys:
            if not get(key.lower()):
                found.append(_problem("not-given", here, at(key.lower()), key=key,
                                      says="Briefs go to outbox/ until it is. To set it, run the adopt-house skill."))
            elif name == "sign-off brief" and not get(key.lower()).isdigit():
                found.append(_problem("bad-value", here, at(key.lower()), key=key, value=get(key.lower()), allowed=[],
                                      why="It is the number Confluence gives the %s." % ("space" if key == "Space ID" else "page"),
                                      write="- %s: <the number>" % key))
        approval = get("approval")
        if name == "sign-off brief" and approval and approval not in _APPROVALS:
            found.append(_problem("bad-value", here, at("approval"), key="Approval", value=approval, allowed=list(_APPROVALS),
                                  why="It takes one of: %s." % ", ".join(_APPROVALS), write="- Approval: reply"))
        if not section_is_set(dest, name):
            lines.append("  %s: not set" % shown)
            continue
        state, landed, got, now = landing_state(dest, name, types.get(name))
        if name == "sign-off brief":
            where = "under page %s in space %s" % (get("parent page id"), get("space key") or get("space id"))
            tail = ". Approval: " + (approval or "reply")  # said after the proof
        else:
            where, tail = "project " + get("project key"), ""
        if state == "none":
            proof = "Not proved by a test landing"
            found.append(_problem("stale", here, heading.get(name, 1), what="The %s section is set and no test landing is recorded" % shown,
                                  how="Not proved by a test landing. Run the adopt-house skill to land again."))
        elif state == "stale":
            found.append(_problem(
                "stale", here, at("landed"), what="The Landed line of the %s section names %s, and the house now names %s" % (
                    shown, got or "nothing it can read", now),
                how="Not proved by a test landing. Run the adopt-house skill to land again."))
            proof = "Not proved by a test landing"
        else:
            proof = "Proved by a test landing, %s" % landed[0] if name == "sign-off brief" else \
                "Proved %s with %s" % (landed[0], _article(landed[2]) if len(landed) > 2 else "a test item")
        lines.append("  %s: %s. %s%s" % (shown, where, proof, tail))
    return lines, found


def _brand_line(house):
    top = read_destinations(house.text("brand.md") or "")["top"]
    got = lambda key: top.get(key, ("",))[0] if given(top.get(key, ("",))[0]) else ""
    parts = [w for w, k in (("logo", "logo"), ("header", "header"), ("footer", "footer")) if got(k)]
    styles = len(_diagram_styles(house))
    more = "; %s" % _plural(styles, "diagram style line") if styles else ""  # counted, never checked
    if not parts and not got("organisation"):
        return "Brand: nothing set" + more
    shown = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1] if parts else "nothing else"
    return "Brand: %s; %s set%s" % (got("organisation") or "no organisation named", shown, more)


def _unread(house):
    """Findings for what the house holds that ba never reads: a template named for none of the forms; in a pack,
    any section that is not a house file."""
    found, forms = [], "signoff.md, signoff-<form>.md, scope.md, delivery.md and handover.md"
    here = {"file": house.own.path}
    for name in house.own.names() if house.own else []:
        if name in HOUSE_FILES:
            continue
        inside = name.startswith("templates/") and "/" not in name[10:]
        if inside and any(f["templates"].match(name[10:]) for f in FACES.values()):
            continue
        if inside or house.own.form == "a pack":
            line = house.own.starts.get(name, 1) if house.own.form == "a pack" else 1
            found.append(_problem(
                "not-read", {"file": house.own.where(name) if inside and house.own.form != "a pack" else house.own.path}, line,
                what="%s is not read by ba." % name,
                how=("The templates ba reads are named %s. Rename it, or delete it." % forms) if inside else
                    "The files ba reads are words.md, hierarchy.md, destinations.md, brand.md and templates/%s. "
                    "Rename the section, or delete it." % forms.replace(" and ", " or ")))
    return found


def _words_line(house):
    text = house.own.text("words.md") if house.own else None
    return "words.md (%d rows)" % len(Words([("", text)]).rows) if text is not None else None


def adopt(path):
    """`ba check --adopt <house>`: print what the house holds and what is wrong with it. Exit 0 whatever is found, 2
    when the path is neither a folder nor a file."""
    own = _open(os.path.abspath(path))
    if own is None:
        print("ba check: --adopt names '%s', and there is no such folder or file. Give the house: a folder that holds "
              "words.md and templates/, or a file that holds them as a pack." % path, file=sys.stderr)
        return 2
    house = House(os.path.abspath(path), own)
    store, feature = _sample()
    words = house.words()
    mine = house.own_files()
    lacking = [n for n in HOUSE_FILES if n not in mine] + [
        "templates/" + n for f in FACES.values() if not house.templates(f, own_only=True) for n in House().templates(f)]
    shown = [(_words_line(house) if n == "words.md" else n) for n in mine]
    out = ["House: %s (%s)" % (path, own.form), "Its own: " + (", ".join(shown) or "nothing"),
           "From the shipped house: " + (", ".join(lacking) or "nothing"), "Templates:"]
    found = []
    for n in mine:
        if n.startswith("templates/"):
            line, more = _template_checks(house, n[10:], store, feature, words)
            out.append(line)
            found += more
    if not any(n.startswith("templates/") for n in mine):
        out.append("  none of its own: the shipped templates are used")
    lines, more = _hierarchy_checks(house)
    out += ["Hierarchy:"] + lines
    found += more
    lines, more = _destination_checks(house)
    out += ["Goes to:"] + lines + [_brand_line(house)]
    found += more + _unread(house)
    for w in words.missing:
        found.append(_problem("missing", {"file": words.file or house.where("words.md")}, words.last_line,
                              what="row for the word '%s' in the word list. The brief shows the word as written" % w, key=w,
                              at="after line %d" % words.last_line, add="| %s | <what readers should see> |  |" % w))
    seen = []
    for p in found:
        if p["file"] not in seen:
            seen.append(p["file"])
    for file in seen:
        out += ["", file]
        for p in (x for x in found if x["file"] == file):
            out += ["  line %d: %s: %s" % (p["line"], p["level"], p["message"]), "    Fix: " + p["fix"]]
    nf = len([p for p in found if p["level"] == "finding"])
    out += ["", "Summary: %d finding%s, %d information." % (nf, "" if nf == 1 else "s", len(found) - nf)]
    print("\n".join(out))
    return 0


# ==== helper/src/baseline.py ================================================
"""Baseline: the records version, fingerprints, and the `baseline` verb (ADR 0013).

Owns version_of, the canonical form of a record, baselines/ on disk, and what changed since one. Must not know:
how a brief is laid out. A brief asks this module for a baseline's store and version, nothing more.
"""

# Lines that say where or when, not what is true: left out of the records version, of a baseline's copy
# and of its fingerprints (ADRs 0011, 0013, 0033, 0038). A brief made from a baseline shows them as they are now. Who owes an
# answer, when it was raised and when it was asked are not what was signed off.
LIVES_AT = {"work": ("tracker", "home"), "feature": ("tracker", "business item"), "question": ("raised", "asked", "owner")}


def version_of(store):
    """The first 8 hex characters of the SHA-256 of the record files' bytes in store order, CRLF read as LF,
    leaving out what does not say what was agreed (ADR 0011, "What the records version leaves out", is the one list):
    the Work's sections in LEFT_OUT, so recording an approval or a sending, or reading actuals, does not make a brief
    stale; the lines that say where a thing lives or who owes what (LIVES_AT); the Work's lines about how its briefs
    look (PRESENTATION), so naming a form or a house after a yes does not unsettle it; and every Observed record: what
    the present system does is evidence, and no approver signs it off (ADR 0038).
    A store read from a baseline has the version the baseline froze, not a hash of its own copy."""
    if store.get("baseline"):
        return store["baseline"]["version"]
    skip = {}  # {file: {line numbers the version leaves out}}: the ### Approvals section and the LIVES_AT lines (ADR 0011)
    for r in store["records"]:
        if r["kind"] == "observed":
            gap = r["line"]  # the blank lines above it too, so a new Observed record adds nothing to the file's bytes
            while gap > 1 and not store["files"][r["file"]][gap - 2].strip():
                gap -= 1
            skip.setdefault(r["file"], set()).update(range(gap, r["end"] + 1))
        for span in (r[k + " span"] for k in LEFT_OUT):
            if span:
                skip.setdefault(r["file"], set()).update(range(span[0], span[1] + 1))
        for key in LIVES_AT.get(r["kind"], ()) + (PRESENTATION if r["kind"] == "work" else ()):
            if key in r["fields"]:
                skip.setdefault(r["file"], set()).add(r["fields"][key]["line"])
    data = "".join("".join(t for n, t in enumerate(lines, 1) if n not in skip.get(file, ()))
                   for file, lines in store["files"].items()).replace("\r\n", "\n")
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Baselines (ADR 0013): a frozen copy of the records as approved, and what a brief or an approval cites.
# ---------------------------------------------------------------------------

BASELINES = "baselines"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# Lines on the Work about where it lives and how its briefs look, not about what was agreed.
PRESENTATION = ("house", "home", "sign-off form")


def _today():
    """The date as a baseline records it. SOURCE_DATE_EPOCH, when set, fixes it, so golden files hold still."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    return time.strftime("%Y-%m-%d", time.gmtime(int(epoch)) if epoch and epoch.isdigit() else time.localtime())


def _plain(text):
    return " ".join(text.split())


def _canonical(rec):
    """A record as a baseline keeps it: one fixed form whatever the line endings, blank lines, bullets, key case,
    field order or spacing it was typed with. Only what ba reads is kept; unread lines and the Work's
    approvals (which are answers to a baseline, not part of it) are left out."""
    out = ["## %s: %s" % (label(rec["kind"]), _plain(rec["name"])), ""]
    for key in FIELDS[rec["kind"]]:
        if key in rec["fields"] and not (rec["kind"] == "work" and key in PRESENTATION) \
                and key not in LIVES_AT.get(rec["kind"], ()):
            out.append("- %s: %s" % (label(key), _plain(rec["fields"][key]["value"])))
    lists = (("Examples", ["- %s: %s" % (e["mark"], _plain(e["text"])) for e in rec["examples"]]),
             ("People", ["- %s: %s" % (_plain(x["role"]), _plain(x["name"])) for x in rec["people"]]),
             ("Assumptions", ["- " + _plain(x["text"]) for x in rec["assumptions"]]),
             ("Out of scope", ["- " + _plain(x["text"]) for x in rec["out of scope"]]),
             ("Stakeholders", ["- " + _plain(x["text"]) for x in rec["stakeholders"]]),
             ("Tolerances", ["- " + _plain(x["text"]) for x in rec["tolerances"]]),
             ("Glossary", ["- %s: %s" % (_plain(x["word"]), _plain(x["meaning"])) for x in rec["glossary"]]),
             ("Left to engineering", ["- " + _plain(x["text"]) for x in rec["left to engineering"]]),
             ("Flow steps", ["- " + _plain(x["text"]) for x in rec["flow steps"]]))
    for title, items in lists:
        if items:
            out += ["", "### " + title, ""] + items
    for step in rec["steps"]:
        out += ["", "### Step: " + _plain(step["name"]), ""]
        out += ["- %s: %s" % (label(k), _plain(step["fields"][k]["value"])) for k in STEP_FIELDS if k in step["fields"]]
        out += ["- Go to: " + _plain(g["text"]) for g in step["go to"]]
    return "\n".join(out) + "\n"


def _in_scope(rec):
    """A baseline is the records as approved: the Work and the questions (which have no status), and the
    requirements and flows the BA has confirmed. Drafts and withdrawn records are left out."""
    return rec["kind"] in ("work", "question") or (rec["kind"] != "observed" and status_of(rec) == "confirmed")


def _key(rec):
    return rec["id"] or "%s:%s" % (rec["kind"], rec["name"])


def _fingerprints(store):
    """{ID: (fingerprint, record)} for the records a baseline would hold."""
    return {_key(r): (hashlib.sha256(_canonical(r).encode("utf-8")).hexdigest()[:12], r)
            for r in store["records"] if _in_scope(r)}


def _overall(fps):
    return hashlib.sha256("\n".join(sorted("%s %s" % (k, v[0]) for k, v in fps.items())).encode("utf-8")).hexdigest()[:12]


def _manifest(folder, name):
    """The manifest of baselines/<name>/ as a dict, or None when there is no such baseline."""
    if not folder or not _NAME.match(name):
        return None
    try:
        text = read_text(os.path.join(folder, BASELINES, name, "manifest.txt"))
    except (OSError, Unreadable):
        return None
    m = {"name": name, "records": {}, "left out": [], "waiver": "", "number": "0"}
    for line in text.splitlines():
        r = re.match(r"^- (\S+) ([0-9a-f]{12}) (\w+): (.*)$", line)
        if r:
            m["records"][r.group(1)] = (r.group(2), r.group(3), r.group(4))
        elif line.startswith("Left out: "):
            m["left out"].append(line[len("Left out: "):])
        elif ":" in line and not line.startswith("-"):
            k, _, v = line.partition(":")
            m[k.strip().lower()] = v.strip()
    m["findings"] = int((re.match(r"\d+", m.get("check at freezing", "")) or [0])[0]) if m.get("check at freezing") else 0
    return m if "records version" in m else None


def _baselines(folder):
    """The manifests in baselines/, oldest first."""
    base = os.path.join(folder, BASELINES)
    found = [_manifest(folder, n) for n in sorted(os.listdir(base))] if os.path.isdir(base) else []
    return sorted((m for m in found if m), key=lambda m: (int(m["number"]) if m["number"].isdigit() else 0, m["name"]))


def _baseline_cmd(name):
    return BA + " baseline " + name + FOLDER


def _read_baseline(live, name):
    """(a store read from baselines/<name>/, None), or (None, why not). The store carries "baseline": its name,
    date, records version, findings at freezing and waiver; the Work's approvals are the live Work's,
    because an approval is an answer to a baseline and is written after it."""
    folder = live["folder"]
    m = _manifest(folder, name)
    if m is None:
        have = [b["name"] for b in _baselines(folder)]
        return None, "There is no baseline '%s' in baselines/. %s" % (
            name, "The ones there are: %s." % ", ".join(have) if have else
            "None has been frozen yet. Freeze one with: " + _baseline_cmd(_next_name(folder, "v1")))
    store = read_store([("work.md", read_text(os.path.join(folder, BASELINES, name, "records.md")))], folder)
    names = {k.lower(): (k, v[2]) for k, v in m["records"].items()}  # (ID, name) of each record, as frozen
    for held in m["left out"]:
        left = re.match(r"^(\S+) \w+ \w+: (.*)$", held)
        if left:
            names.setdefault(left.group(1).lower(), (left.group(1), left.group(2)))
    store["baseline"] = {"name": name, "date": m.get("date", ""), "version": m["records version"],
                         "findings": m["findings"], "waiver": m["waiver"], "names": names}
    work = next((r for r in store["records"] if r["kind"] == "work"), None)
    now = next((r for r in live["records"] if r["kind"] == "work"), None)
    if work and now:
        work["approvals"] = now["approvals"]
    # Where a record lives is read from the working records too: a tracker item is often known only after freezing.
    for rec in store["records"]:
        mine = next((r for r in live["records"] if r["kind"] == rec["kind"] and (r is now or (r["id"] and r["id"] == rec["id"]))), None)
        for key in LIVES_AT.get(rec["kind"], ()):
            rec["fields"].pop(key, None)
            if mine and key in mine["fields"]:
                rec["fields"][key] = dict(mine["fields"][key])
    return store, None


def _approved_version(store, a):
    """The records version an approval was given to: the one it names, or the one its baseline froze ('' if
    there is no such baseline)."""
    if not a["baseline"]:
        return a["version"]
    m = _manifest(store["folder"], a["baseline"])
    return m["records version"] if m else ""


def approved_baseline(store, a):
    """The baseline an approval was given to (ADR 0034): the one the item names (None when there is no such baseline),
    or else the latest baseline whose manifest holds the item's records version, or None. Everything that asks which
    baseline a person approved goes through here: `status`, the `changes` block, the chasers."""
    folder = store["folder"]
    if a["baseline"]:
        return _manifest(folder, a["baseline"])
    found = [m for m in _baselines(folder) if m["records version"].lower() == a["version"].lower()] if folder else []
    return found[-1] if found else None


def last_answers(work):
    """{name, lower-case: the last item of `### Approvals` that person wrote}: the last one is the one that counts."""
    out = {}
    for a in work["approvals"] if work else []:
        out[a["name"].lower()] = a
    return out


# ---------------------------------------------------------------------------
# What changed between two copies of the records (ADR 0034): the one definition, read by `ba baseline`, `status`
# and the `changes` block of the sign-off brief, so they cannot disagree.
# ---------------------------------------------------------------------------

_MAIN = {"requirement": "statement", "flow": "overview", "feature": "intent", "work": "goal"}
_PLAIN, _CONFIRM, _OPEN, _GONE = "", "confirm", "open", "withdrawn"  # how a cell of the table is to be dressed


def _main_cell(rec):
    """The sentence that says what a record is, for a row of an added or a withdrawn record: a requirement's statement, a
    flow's overview, a feature's intent; for a question its answer, else its working answer (to confirm), else open."""
    if rec["kind"] == "question":
        if value(rec, "answer"):
            return (_PLAIN, _plain(value(rec, "answer")))
        return (_CONFIRM, _plain(value(rec, "working answer"))) if value(rec, "working answer") else (_OPEN, "")
    return (_PLAIN, _plain(value(rec, _MAIN[rec["kind"]]))) if rec["kind"] in _MAIN else (_PLAIN, "")


def _singles(rec):
    """[(what, key or None, text)] for each line of a record that says what is true."""
    skip = ("id",) + (PRESENTATION if rec["kind"] == "work" else ()) + LIVES_AT.get(rec["kind"], ())
    out = [("Name", None, _plain(rec["name"]))]
    out += [(label(k), k, _plain(value(rec, k))) for k in FIELDS[rec["kind"]] if k not in skip and value(rec, k)]
    for step in rec["steps"]:
        out += [("Step %s: %s" % (_plain(step["name"]), label(k)), None, _plain(value(step, k))) for k in STEP_FIELDS if value(step, k)]
    return out


def _lists(rec):
    """[(what, [(style, text)])] for each list of a record, in the order a baseline keeps them."""
    out = [("Example", [(_CONFIRM if e["mark"] == "proposed" else _PLAIN, _plain(e["text"])) for e in rec["examples"]])]
    for what, items in (("People", ["%s: %s" % (_plain(x["role"]), _plain(x["name"])) for x in rec["people"]]),
                        ("Assumptions", [_plain(x["text"]) for x in rec["assumptions"]]),
                        ("Out of scope", [_plain(x["text"]) for x in rec["out of scope"]]),
                        ("Stakeholders", [_plain(x["text"]) for x in rec["stakeholders"]]),
                        ("Tolerances", [_plain(x["text"]) for x in rec["tolerances"]]),
                        ("Glossary", ["%s: %s" % (_plain(x["word"]), _plain(x["meaning"])) for x in rec["glossary"]]),
                        ("Left to engineering", [_plain(x["text"]) for x in rec["left to engineering"]]),
                        ("Flow steps", [_plain(x["text"]) for x in rec["flow steps"]])):
        out.append((what, [(_PLAIN, t) for t in items]))
    out += [("Step %s: Go to" % _plain(s["name"]), [(_PLAIN, _plain(g["text"])) for g in s["go to"]]) for s in rec["steps"]]
    return out


def _differences(old, new):
    """[(what, key, was cell, now cell)] for one record held in both copies. A line that differs is one row; in a
    list the items only in the old and the items only in the new are paired in order, one row a pair."""
    rows, o, n = [], {w: (k, t) for w, k, t in _singles(old)}, {w: (k, t) for w, k, t in _singles(new)}
    for what in list(dict.fromkeys([w for w, _, _ in _singles(old)] + [w for w, _, _ in _singles(new)])):
        if o.get(what, (None, ""))[1] != n.get(what, (None, ""))[1]:
            rows.append((what, (n.get(what) or o.get(what))[0], (_PLAIN, o.get(what, (0, ""))[1]), (_PLAIN, n.get(what, (0, ""))[1])))
    lo, ln = dict(_lists(old)), dict(_lists(new))
    for what in list(dict.fromkeys([w for w, _ in _lists(old)] + [w for w, _ in _lists(new)])):
        gone = [x for x in lo.get(what, []) if x not in ln.get(what, [])]
        come = [x for x in ln.get(what, []) if x not in lo.get(what, [])]
        for i in range(max(len(gone), len(come))):
            rows.append((what, None, gone[i] if i < len(gone) else (_PLAIN, ""), come[i] if i < len(come) else (_PLAIN, "")))
    return rows


def _grouping(row):
    """A row is grouping (ADR 0038) when it is about a Feature record, or is the `Feature` line of a Requirement: how the
    deliverable is divided for handing over, which no approver signs off."""
    return row["rec"]["kind"] == "feature" or (row["rec"]["kind"] == "requirement" and row["key"] == "feature")


def changes_between(old_store, new_store, live=None):
    """What differs between two copies of the records, as rows: [{"set": "changed", "added" or "withdrawn", "rec": the
    record the row is about, "what", "key", "was", "now", "grouping"}], changed first, then added, then withdrawn, each in store
    order. A cell is (how it is dressed, its text). `old_store` is a baseline's store; `new_store` the working records
    or a later baseline's; `live` the working records, where a withdrawn record's reason is read (the records
    themselves are not in a later baseline). The records compared are the ones a baseline holds, matched by ID; lines
    that say where or when, and the Work's house, home and form, are never compared (as in a fingerprint)."""
    live = live or new_store
    now, was = {_key(r): r for r in new_store["records"] if _in_scope(r)}, {_key(r): r for r in old_store["records"] if _in_scope(r)}
    held = {r["id"]: r for r in live["records"] if r["id"]}
    fp_new, fp_old = _fingerprints(new_store), _fingerprints(old_store)
    changed, added, withdrawn = [], [], []
    for key, rec in was.items():
        if key in now:
            if fp_new[key][0] != fp_old[key][0]:
                rows = _differences(rec, now[key]) or [("Record", None, (_PLAIN, ""), (_PLAIN, ""))]
                changed += [{"set": "changed", "rec": now[key], "what": w, "key": k, "was": a, "now": b} for w, k, a, b in rows]
        elif key in held and status_of(held[key]) == "draft":  # not confirmed any more
            changed.append({"set": "changed", "rec": held[key], "what": "Status", "key": "status", "was": (_PLAIN, "confirmed"),
                            "now": (_PLAIN, "draft")})
        else:
            reason = value(held[key], "withdrawn because") if key in held else ""
            withdrawn.append({"set": "withdrawn", "rec": rec, "what": "", "key": None, "was": _main_cell(rec),
                              "now": (_GONE, _plain(reason))})
    added = [{"set": "added", "rec": r, "what": "", "key": None, "was": (_PLAIN, ""), "now": _main_cell(r)}
             for k, r in now.items() if k not in was]
    rows = changed + added + withdrawn
    for row in rows:
        row["grouping"] = _grouping(row)
    return rows


def _number_of(m):
    return int(m["number"]) if m["number"].isdigit() else 0


def approval_base(store):
    """(the baseline a change is shown against, the approvals of it), or (None, []) (ADR 0034). The base is the latest
    baseline, frozen before what the brief is made from, that some approver's last answer approves. For a brief made
    from the working records every baseline is before; for one made from baseline v2, v2 itself is not."""
    work = next((r for r in store["records"] if r["kind"] == "work"), None)
    if not work or not store["folder"]:
        return None, []
    made = _manifest(store["folder"], store["baseline"]["name"]) if store.get("baseline") else None
    got = [(approved_baseline(store, a), a) for a in last_answers(work).values() if a["decision"] == "approved"]
    got = [(m, a) for m, a in got if m and (made is None or _number_of(m) < _number_of(made))]
    if not got:
        return None, []
    top = max((m for m, _ in got), key=_number_of)
    return top, [a for m, a in got if m["name"] == top["name"]]


def changes_for(store):
    """(the base, the approvals of it, the rows) for the sign-off brief made from this store, or (None, [], [])."""
    base, approvals = approval_base(store)
    old = _read_baseline(store, base["name"])[0] if base else None
    if old is None:
        return None, [], []
    live = read_workspace(store["folder"]) if store.get("baseline") else store
    return base, approvals, [r for r in changes_between(old, store, live) if not r["grouping"]]


def _since(store, m, grouping=True):
    """(changed, added, withdrawn): 'ID name' for each working record against a baseline. With `grouping` False the rows
    that only regroup (a Feature record, a requirement's `Feature` line) are not counted (ADR 0038)."""
    old, _ = _read_baseline(store, m["name"])
    if old is None:
        return [], [], []
    shown = lambda r: " ".join(x for x in (r["id"], r["name"]) if x)
    out = ([], [], [])
    for row in changes_between(old, store):
        if row["grouping"] and not grouping:
            continue
        mine = out[("changed", "added", "withdrawn").index(row["set"])]
        if shown(row["rec"]) not in mine:
            mine.append(shown(row["rec"]))
    return out


def regrouped_since(store, m):
    """True when features were regrouped since baseline `m`: some row that is grouping."""
    old, _ = _read_baseline(store, m["name"])
    return old is not None and any(row["grouping"] for row in changes_between(old, store))


def size_moved(store, m):
    """(the size then, the size now) when the Work's size differs from baseline `m`, else None: his own example of what
    materially changes the deliverable (ADR 0038). The baseline's Work keeps the size lines."""
    old, _ = _read_baseline(store, m["name"])
    then, now = (size_of(old)[0] if old else ""), size_of(store)[0]
    return (then, now) if old is not None and then != now else None


def approval_stands(store, a):
    """True when an approval still holds for the records (ADR 0038): it is of the records version they have, or it is
    read against a baseline and nothing but grouping differs from it. An approval of a records version that no baseline
    froze cannot be compared, and stands only for that version."""
    if _approved_version(store, a) == version_of(store):
        return True
    base = approved_baseline(store, a)
    return base is not None and not any(_since(store, base, grouping=False))


def _some(items, limit=4):
    return ", ".join(items[:limit]) + (", and %d more" % (len(items) - limit) if len(items) > limit else "")


def _since_lines(store, m, grouping=True):
    """The `Since <baseline>:` lines. With `grouping` False, regrouping is not counted and is said as a fact (ADR 0038)."""
    changed, added, withdrawn = _since(store, m, grouping)
    tail = ", features regrouped" if not grouping and regrouped_since(store, m) else ""
    if not (changed or added or withdrawn):
        return ["Since %s: nothing has changed%s." % (m["name"], tail)]
    out = ["Since %s: %d changed, %d added, %d withdrawn%s." % (m["name"], len(changed), len(added), len(withdrawn), tail)]
    for word, items in (("changed", changed), ("added", added), ("withdrawn", withdrawn)):
        if items:
            out.append("  %s: %s" % (word, _some(items)))
    return out


def _next_name(folder, name):
    while os.path.exists(os.path.join(folder, BASELINES, name)):
        m = re.match(r"^(.*?)(\d+)$", name)
        name = m.group(1) + str(int(m.group(2)) + 1) if m else name + "-2"
    return name


def work_sent(store):
    """Every item of the Work's `### Published`, in the order written."""
    work = next((r for r in store["records"] if r["kind"] == "work"), None)
    return work["published"] if work else []


def _list_baselines(folder):
    store = read_workspace(folder)
    found = _baselines(folder)
    print("Workspace: " + folder)
    if not found:
        print("No baselines yet. Freeze the records as they stand with: %s" % _baseline_cmd(_next_name(folder, "v1")))
        return 0
    print("Baselines in baselines/, the last frozen is the latest:")
    for m in found:
        print("  %s  %s  %d records, %d finding%s%s%s" % (
            m["name"], m.get("date", ""), len(m["records"]), m["findings"], "" if m["findings"] == 1 else "s",
            ", waived: " + m["waiver"] if m["waiver"] else "", "  (latest)" if m is found[-1] else ""))
        sent = [i for i in work_sent(store) if i["from"].lower() == "baseline " + m["name"].lower()]
        if sent:  # a sending ties the baseline to the page version people approved (ADR 0026)
            print("    Sent from %s: %s" % (m["name"], "; ".join("%s, %s (%s)" % (i["face"], sent_what(i), i["date"]) for i in sent)))
    print("\n".join(_since_lines(store, found[-1])))
    return 0


def baseline(args):
    folder = find_workspace(args.folder)
    if folder is None:
        where, misplaced = _no_workspace(args.folder, BA + " baseline")
        message = misplaced or "No work.md %s, so there is nothing to freeze. Fix: create work.md with a Work " \
                               "record (%s --shape work), or give the folder: %s <name> <folder>" % (where, CHECK, BA + " baseline")
        print(message, file=sys.stderr if args.name else sys.stdout)
        return 2 if args.name else 0
    if not args.name:
        return _list_baselines(folder)
    name = args.name
    if not _NAME.match(name):
        print("ba baseline: '%s' is not a name a baseline can have. Use letters, digits, hyphens, dots or "
              "underscores, starting with a letter or digit, for example v1." % name, file=sys.stderr)
        return 2
    if os.path.exists(os.path.join(folder, BASELINES, name)):
        print("ba baseline: baselines/%s already exists, and a baseline is never overwritten. Nothing was changed. "
              "Fix: use the next name: %s" % (name, _baseline_cmd(_next_name(folder, name))), file=sys.stderr)
        return 2
    store = read_workspace(folder)
    found = [p for p in _findings(store, freezing=name) if p["level"] == "finding"]
    waiver = _plain(args.waive) if args.waive is not None else None
    if found and not waiver:
        why = ("A waiver needs a reason, and '--waive' was given none." if waiver == "" else
               "A baseline is the one place ba holds work back: the records have %d finding(s)." % len(found))
        print("\n".join(["ba baseline: not frozen. " + why] + _show(found) + [
            "", "Two ways forward:",
            "  1. Fix the finding(s) above, then run: " + _baseline_cmd(name),
            "  2. Freeze anyway and record why: %s --waive \"<reason>\"" % _baseline_cmd(name)]), file=sys.stderr)
        return 2
    out = ["Workspace: " + folder]
    replace, insert, notes = _plan_ids(store)
    if notes:  # IDs are what an approval cites, and a baseline holds each record under its ID
        where = _backup_and_write(folder, _apply(store, replace, insert))
        out += ["Gave IDs first, so every record can be cited. A backup of the files is in %s/." % where] + [
            "  " + n for n in notes]
        store = read_workspace(folder)
    fps = _fingerprints(store)
    left = [r for r in store["records"] if not _in_scope(r) and r["kind"] != "observed"]  # evidence nobody approves (ADR 0035)
    problems = _findings(store, freezing=name)
    nf = len([p for p in problems if p["level"] == "finding"])
    kept = [r for r in store["records"] if _in_scope(r)]
    number = max([int(m["number"]) for m in _baselines(folder) if m["number"].isdigit()] or [0]) + 1
    manifest = ["Baseline: " + name, "Number: %d" % number, "Date: " + _today(),
                "Records version: " + version_of(store), "Fingerprint: " + _overall(fps),
                "Check at freezing: %d finding%s, %d information" % (nf, "" if nf == 1 else "s", len(problems) - nf)]
    if nf and waiver:
        manifest.append("Waiver: " + waiver)
    manifest += ["", "Contents:"] + ["- %s %s %s: %s" % (_key(r), fps[_key(r)][0], r["kind"], _plain(r["name"]))
                                    for r in kept]
    manifest += ["Left out: %s %s %s: %s" % (r["id"] or "(no ID)", status_of(r), r["kind"], _plain(r["name"])) for r in left]
    target = os.path.join(folder, BASELINES, name)
    os.makedirs(target)
    for file, lines in (("records.md", ["<!-- Frozen by ba baseline. Do not edit: a baseline is never changed. -->", ""] +
                         [_canonical(r) for r in kept]), ("manifest.txt", manifest)):
        with open(os.path.join(target, file), "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(lines).rstrip("\n") + "\n")
    counts = ", ".join("%s %d" % (label(k), len([r for r in kept if r["kind"] == k])) for k in KINDS
                       if any(r["kind"] == k for r in kept))
    out.append("Froze baseline '%s': %d records (%s) in baselines/%s/." % (name, len(kept), counts, name))
    drafts = [r["name"] for r in left if status_of(r) == "draft"]
    if drafts:
        out.append("Left out because they are drafts: %s. Confirm them and freeze again to include them." % _some(drafts))
    out.append("Check at freezing: %d finding%s, %d information." % (nf, "" if nf == 1 else "s", len(problems) - nf))
    if nf and waiver:
        out.append("Waiver recorded: %s. It shows in the manifest and on every brief made from this baseline." % waiver)
    elif waiver:
        out.append("There were no findings, so no waiver was recorded.")
    out.append("Cite it: %s --baseline %s. An approval says: baseline %s" % (BUNDLE + FOLDER, name, name))
    if any(r["kind"] == "feature" for r in kept):
        out.append("For a Feature's handover brief: %s bundle handover <feature>%s --baseline %s" % (BA, FOLDER, name))
    print("\n".join(out))
    return 0


# ==== helper/src/status.py ==================================================
"""Status: the `status` verb, and the size of the work (ADR 0023). Computed from the records and the files
beside them; it writes nothing.

Owns size_of and the lines of the report with the next steps. Must not know: how a brief is made, only whether
one exists and how old it is.
"""

# ---------------------------------------------------------------------------
# Size, and status (blueprint section 7). Size is read from the Work's yes or no lines and nowhere else.
# Nothing in check or bundle reads it: the first capture is never held up by size.
# ---------------------------------------------------------------------------

def size_of(store):
    """('Small', 'Medium' or 'Large', the size lines that say yes). `Several features: yes` is Large and is named
    first; else any of the four signals at yes is Medium; else Small. An absent line is no (ADR 0032). This is the
    one place size is worked out."""
    work = next((r for r in store["records"] if r["kind"] == "work"), None)
    yes = [label(s) for s in (SEVERAL,) + SIGNALS if work and value(work, s) == "yes"]
    return ("Large" if work and value(work, SEVERAL) == "yes" else "Medium" if yes else "Small"), yes


def _plural(n, word, many=None):
    return "%d %s" % (n, word if n == 1 else many or word + "s")


def _counts_line(store, kind):
    recs = [r for r in store["records"] if r["kind"] == kind]
    if kind == "observed":
        words, order = [standing_of(r) for r in recs], ("unconfirmed", "intended", "accidental", "defect", "withdrawn")
    elif kind == "question":
        words = ["open" if not value(r, "answer") and not value(r, "working answer") else
                 "answered" if value(r, "answer") else "assumed" for r in recs]
        order = ("open", "assumed", "answered")
    else:
        words, order = [status_of(r) for r in recs], ("confirmed", "draft", "withdrawn")
    kinds = sorted(set(words), key=lambda w: order.index(w) if w in order else len(order))
    return "  %s %d: %s" % (label(kind), len(recs), ", ".join("%d %s" % (words.count(w), w) for w in kinds))


def _owes(q, assumed=False):
    """Who owes the answer to a question (ADR 0033): its `Owner`, and nobody else. The person who raised it is named
    for the analyst's sake, never as the one to ask."""
    if value(q, "owner"):
        return "owner " + value(q, "owner")
    return "no owner, raised by " + value(q, "raised by") if value(q, "raised by") and not assumed else "no owner"


# ---------------------------------------------------------------------------
# Dates and ages (ADR 0033). A date is worked with only when it is written YYYY-MM-DD and is not after today;
# anything else is kept and shown as written, with no age. A missing or odd date is never a finding.
# ---------------------------------------------------------------------------

def _age(text):
    """Whole days from a `YYYY-MM-DD` to today, or None for any other form or a date after today."""
    day, today = _date(text), _date(_today())
    return (today - day).days if day and day <= today else None


def _days(n):
    return "today" if n == 0 else _plural(n, "day")


def _age_shown(text):
    """`21 days, since 2024-03-04` for status; `since 11 March` for a date it cannot age; '' for no date."""
    text, n = text.strip(), _age(text)
    return "" if not text else ("%s, since %s" % (_days(n), text) if n is not None else "since " + text)


def _when(text, verb):
    """A chaser's date: `Open since 4 March 2024 (21 days).`, or as written with no age, or '' for no date."""
    text, n = text.strip(), _age(text)
    if not text:
        return ""
    return "%s %s (%s)." % (verb, show_date(_date(text)), _days(n)) if n is not None else "%s %s." % (verb, text)


def _ago(text):
    """`3 days ago` for a sending date it can age; '' when it cannot."""
    n = _age(text)
    return "" if n is None else "today" if n == 0 else "%s ago" % _days(n)


def _asked(q):
    """True for a Question the analyst has said they asked and that has no answer: it is waiting on a reply (ADR 0038)."""
    return q["kind"] == "question" and bool(value(q, "asked")) and not value(q, "answer")


def _open_questions(store):
    return [q for q in store["records"] if q["kind"] == "question" and not value(q, "answer") and not value(q, "working answer")
            and not _asked(q)]


def _waiting_on_reply(store):
    """The Questions asked and not yet answered, in store order."""
    return [q for q in store["records"] if _asked(q)]


def _awaiting_verdict(store):
    """The Observed records no person has given a verdict on, and that were not seen wrongly (ADR 0035)."""
    return [r for r in store["records"] if r["kind"] == "observed" and standing_of(r) == "unconfirmed"]


def _assumptions(store):
    return [q for q in store["records"] if q["kind"] == "question" and value(q, "working answer") and not value(q, "answer")
            and not _asked(q)]


def _about_names(store, q):
    names = {r["id"]: r["name"] for r in store["records"] if r["id"]}
    return [names[x] for x in q["about"] if x in names]


def held_up(store, record):
    """The names of the Features, not withdrawn, that a record's `About` line names: the Feature itself, one of its
    requirements that is not withdrawn, or one of its Flows (ADR 0033). A record about the Work alone, or about
    nothing, holds nothing up by name. The one place this is worked out."""
    about = {x.lower() for x in record["about"]}
    out = []
    for f in store["records"]:
        if f["kind"] != "feature" or status_of(f) == "withdrawn" or not about:
            continue
        mine = {x.lower() for x in [f["id"]] + f["flows"] + [r["id"] for r in _feature_reqs(store, f)] if x}
        if about & mine:
            out.append(f["name"])
    return out


def _stamp_of(store, rel):
    """How the brief at `rel` in the workspace stands: ('none', None) when there is no file, ('unreadable', None)
    when it is not UTF-8, ('unstamped', None) when it ends with no stamp, else ('stamped', the stamp's match)."""
    path = os.path.join(store["folder"], *rel.split("/"))
    if not os.path.isfile(path):
        return "none", None
    try:
        lines = _texts(_LINE.findall(read_text(path)))
    except Unreadable:
        return "unreadable", None
    m = _STAMP.match(lines[-1][1]) if lines else None
    return ("stamped", m) if m else ("unstamped", None)


def _status_face(store, face, label):
    """How a brief of the whole Work stands, as a line, or None when there is no file (ADR 0029: the Scope brief
    and the Delivery plan are shown once they exist, as the sign-off brief is)."""
    rel = face_file(face)
    how, m = _stamp_of(store, rel)
    if how == "none":
        return None
    if how == "unreadable":
        return "%s: %s, could not be read as UTF-8 text" % (label, rel)
    if how == "unstamped":
        return "%s: %s, with no stamp, so its age is not known" % (label, rel)
    if m.group("b"):
        return "%s: %s, made from baseline %s%s" % (label, rel, m.group("b"),
                                                   ", frozen with a waiver: " + m.group("w") if m.group("w") else "")
    return "%s: %s, made from the working records, %s" % (
        label, rel, "up to date" if m.group("v") == version_of(store) else "older than the records")


def _status_delivery_plan(store):
    """The Delivery plan line. The records version leaves the forecast's sections out, so a plan can be behind them with
    the version unchanged: check says so, and so does this line."""
    line = _status_face(store, FACES["delivery"], "Delivery plan")
    stale = any(p["code"] == "stale" and p["file"] == face_file(FACES["delivery"]) for p in _face_findings(store))
    return line[:-len("up to date")] + "older than the Delivery and Actuals sections" if line and stale and line.endswith("up to date") else line


def _status_delivery(store):
    """The Delivery line, once the forecast can be worked out: where it ends, and how it stands against the actuals."""
    fc = forecast_for(store)
    if not fc["ok"]:
        return []
    last = fc["rows"][-1]
    out = ["forecast finish " + (show_date(last["early"]) if last["early"] == last["late"] else
                                 "%s to %s" % (show_date(last["early"]), show_date(last["late"])))]
    if fc["read"]:
        said = {"earlier": "earlier than the forecast", "within": "within the forecast", "later": "later than the forecast"}
        out += ["%d of %d features finished" % (fc["finished"], len(fc["rows"])),
                "at the pace so far %s (%s)" % (show_date(fc["last"][0]), said[fc["last"][1]]) if fc["last"] else "too early to say a pace",
                "actuals read " + show_date(fc["read"])]
    return ["Delivery: " + "; ".join(out)]


def _status_brief(store):
    return _status_face(store, FACES["signoff"], "Brief") or "Brief: none yet. Make one: " + BUNDLE + FOLDER


def _feature_reqs(store, feature):
    """The requirements that are not withdrawn and name this Feature on their `Feature` line."""
    return [r for r in store["records"] if r["kind"] == "requirement" and status_of(r) != "withdrawn"
            and any(feature_named(store["records"], p) is feature for p in feature_parts(r))]


def _status_landed(house):
    """The Landed line: for each section that is set, the date of the test landing that proved it, or that none has."""
    dest, (business, delivery) = house.places(), feature_types(house)
    types, out = {"business board": business, "delivery board": delivery}, []
    for name in SECTIONS:
        if section_is_set(dest, name):
            state, parts, _, _ = landing_state(dest, name, types.get(name))
            out.append("%s %s" % (name, parts[0] if state == "proved" else "not proved"))
    return ["Landed: " + "; ".join(out)] if out else []


def _status_house(store, work):
    """The House and Goes to lines (ADR 0025): which house the briefs are made from, and where they go."""
    house, problems, _ = _house(store["folder"], work or _new_record("work", "", "work.md", 1), None)
    ref = value(work, "house") if work else ""
    shown = "%s (not read: see check; the shipped house is used)" % ref if problems else house.line()
    return ["House: " + shown, "Goes to: " + goes_to(house)] + _status_landed(house)


def _status_published(store, work):
    """The Published lines: the last sending of each face, and whether it was made from the records as they are."""
    sent = last_sent(work)
    if not sent:
        return []
    return ["Published:"] + ["  %s: %s, sent %s, %s: %s. %s" % (
        face, sent_what(i), i["date"], i["from"], "current" if sent_is_current(store, i) else "made from earlier records",
        i["link"]) for face, i in sent.items()]


def _status_linked(work):
    """The Linked documents line: how many documents another team keeps are named on the Work, and what each is called."""
    docs = work["linked documents"] if work else []
    return ["Linked documents: %d (%s)" % (len(docs), ", ".join(d["text"].partition(":")[0].strip() for d in docs))] if docs else []


def _status_features(store):
    """The Features lines, once a Feature record exists (ADR 0024)."""
    recs = store["records"]
    if not any(r["kind"] == "feature" for r in recs):
        return []
    live = live_features(store)
    out = ["Features: %d" % len(live)]
    out += ["  %s%s (%s): %s" % (r["id"] + " " if r["id"] else "", r["name"], status_of(r),
                                  _plural(len(_feature_reqs(store, r)), "requirement")) for r in live]
    out += ["  %s%s (%s): kept, sliced into %s%s" % (
        r["id"] + " " if r["id"] else "", r["name"], status_of(r), ", ".join(p["id"] or p["name"] for p in _parts_of(store, r)),
        "; tracker item " + value(r, "tracker") if value(r, "tracker") else "")
        for r in recs if r["kind"] == "feature" and kept_original(store, r)]
    deliver = to_deliver(store)
    loose = _loose(store) if live else []
    deliberate = [r for r in deliver if left_out_of_features(r) is not None] if live else []
    out.append("In a feature: %d of %d requirements to deliver" % (len(deliver) - len(loose) - len(deliberate), len(deliver)))
    if loose or deliberate:
        out.append("  Not in a feature: " + ", ".join(
            [r["name"] for r in loose] +
            ["%s (deliberate%s)" % (r["name"], ": " + left_out_of_features(r) if left_out_of_features(r) else "")
             for r in deliberate]))
    return out


def _status_withdrawn(store):
    """The withdrawn records and why each went (ADR 0011): its `Withdrawn because` line, or for a Feature that was
    sliced, its parts. Nothing when no record is withdrawn."""
    gone = [r for r in store["records"] if r["kind"] != "question" and status_of(r) == "withdrawn"]
    out = ["Withdrawn: %d" % len(gone)] if gone else []
    for r in gone:
        parts = _parts_of(store, r) if r["kind"] == "feature" else []
        why = value(r, "withdrawn because") or (
            "sliced into " + "; ".join(" ".join(x for x in (p["id"], p["name"]) if x) for p in parts) if parts else
            "")
        out.append("  - %s%s" % (" ".join(x for x in (r["id"], r["name"]) if x), ": " + why if why else ""))
    return out


def _handover_state(store, feature):
    """('none' | 'older' | 'current' | 'unknown', the brief's path relative to the workspace) for a feature's handover brief."""
    rel = face_file(FACES["handover"], feature)
    if not feature["id"]:
        return "none", rel
    how, m = _stamp_of(store, rel)
    if how == "none":
        return "none", rel
    if how != "stamped":
        return "unknown", rel
    return ("current" if (m.group("v") or m.group("bv")) == version_of(store) or m.group("b") else "older"), rel


def _sign_offs(store, work, waiting):
    """[(approver, the sending or None, their last answer or None)]: who owes a yes to the sign-off brief as it was
    last sent (ADR 0033). It is owed when that sending was made from the records as they are and the approver's last
    answer is not an approval of them. With nothing under `### Published` (a brief handed over by hand) it is owed when
    faces/signoff.md is stamped and current; there is then no date and no link."""
    if not work or not waiting:
        return []
    item = last_sent(work).get("signoff")
    if item and not sent_is_current(store, item):
        return []
    if not item:
        how, m = _stamp_of(store, face_file(FACES["signoff"]))
        if how != "stamped" or (m.group("v") or m.group("bv")) != version_of(store):
            return []
    last = {a["name"].lower(): a for a in work["approvals"]}
    return [(n, item, last.get(n.lower())) for n in waiting]


def _status_approvals(store, work, version):
    """(lines, names whose yes does not stand, the sign-offs owed, names to ask): one line per approver, and per anyone else
    who has answered. A yes stands when nothing but grouping differs from what it was given to (ADR 0038); a name is asked
    only when it has not answered with a yes, or its yes does not stand and a sign-off is owed."""
    last = {}
    for a in work["approvals"] if work else []:
        last[a["name"].lower()] = a
    names = [n.strip() for n in value(work, "approvers").split(",") if n.strip()] if work else []
    names += [a["name"] for k, a in last.items() if k not in [n.lower() for n in names]]
    waiting = [n for n in names if not (last.get(n.lower()) and last[n.lower()]["decision"] == "approved"
                                        and approval_stands(store, last[n.lower()]))]
    owed = _sign_offs(store, work, waiting)
    sent = {n.lower(): item for n, item, _ in owed}
    ask = [n for n in waiting if n.lower() in sent or not (last.get(n.lower()) and last[n.lower()]["decision"] == "approved")]
    lines = []
    for n in names:
        a = last.get(n.lower())
        if not a:
            line = "  %s: no answer yet" % n
        else:
            base = approved_baseline(store, a)  # a records version that a baseline froze is that baseline (ADR 0034)
            line = "  %s: %s %s, %s, %s" % (
                n, a["decision"], a["date"], "baseline " + (base["name"] if base else a["baseline"]) if base or a["baseline"]
                else "records version " + a["version"], "to the records as they are" if _approved_version(store, a) == version
                and n not in waiting else "to earlier records")
            since = _since(store, base, grouping=False) if base else ([], [], [])
            if "to earlier records" in line:
                regrouped = base is not None and regrouped_since(store, base)
                if any(since):
                    line += "; %d changed, %d added, %d withdrawn since" % tuple(len(x) for x in since)
                elif n not in waiting:
                    line += "; nothing they approved has changed since"
                line += ", features regrouped" if regrouped and (any(since) or n not in waiting) else ""
                moved = size_moved(store, base) if base else None
                line += "; the size was %s and is now %s" % moved if moved else ""
        item = sent.get(n.lower())
        if item and _ago(item["date"]):
            line += "; the brief was sent %s, %s" % (item["date"], _ago(item["date"]))
        elif item:
            line += "; the brief was sent " + item["date"]
        lines.append(line)
    return lines or ["  no approvers named"], waiting, owed, ask


# ---------------------------------------------------------------------------
# Who owes what (ADR 0033): the open items grouped by the person who owes them, for `Waiting on:` and the chasers.
# ---------------------------------------------------------------------------

def _who_owes(store, owed):
    """({person: [(kind, thing)]}, [(kind, thing)]): what each named person owes, people in order of first appearance
    (open questions, assumptions, then sign-offs; each in store order, a name matched without regard to case and shown
    as first written), and the items nobody owns."""
    people, shown, nobody = {}, {}, []

    def add(name, entry):
        name = name.strip()
        if name:
            people.setdefault(shown.setdefault(name.lower(), name), []).append(entry)
        else:
            nobody.append(entry)
    for q in _open_questions(store):
        add(value(q, "owner"), ("question", q))
    for q in _assumptions(store):
        add(value(q, "owner"), ("assumption", q))
    for r in _awaiting_verdict(store):
        add(value(r, "owner"), ("observed", r))
    for name, item, approval in owed:
        add(name, ("sign-off", (item, approval)))
    return people, nobody


_OWED_WORDS = {"question": "question", "assumption": "assumption", "observed": "observed behaviour"}


def _entry_age(kind, thing):
    """The days an owed item has waited, or None when it has no date or none that can be aged."""
    if kind == "sign-off":
        return _age(thing[0]["date"]) if thing[0] else None
    return _age(value(thing, "raised"))


def _summary(entries, oldest=True):
    """`1 question, 1 assumption, sign-off; oldest 21 days`: what is owed, and how long the oldest dated item has waited."""
    kinds = [k for k, _ in entries]
    parts = [_plural(kinds.count(k), word) for k, word in _OWED_WORDS.items() if k in kinds]
    parts += ["sign-off"] if "sign-off" in kinds else []
    ages = [n for n in (_entry_age(k, x) for k, x in entries) if n is not None]
    return ", ".join(parts) + ("; oldest " + _days(max(ages)) if oldest and ages else "")


def _waiting_on(store, people, nobody):
    """The `Waiting on:` section: one line for each person, the items nobody owns, and where the chasers are."""
    if not (people or nobody):
        return []
    out = ["Waiting on:"] + ["  %s: %s" % (n, _summary(e)) for n, e in people.items()]
    if nobody:
        out.append("  nobody named: %s. Add '- Owner: <who can answer>' to: %s" % (
            _summary(nobody, False), "; ".join(x["name"] for _, x in nobody)))
    return out + (["Chasers, one message for each person: %s status --chasers%s" % (BA, FOLDER)] if people else [])


def _chaser_item(store, n, kind, thing, house):
    """The lines of one numbered item of a chaser. Every word is the helper's: the record's own sentences, its dates
    and what it holds up, set in fixed text (ADR 0033)."""
    out = [""]
    if kind == "question":
        out.append("%d. %s" % (n, thing["name"]))
        out += ["   " + value(thing, "context")] if value(thing, "context") else []
        out += ["   " + t for t in (_when(value(thing, "raised"), "Open since"),) if t]
        up, about = held_up(store, thing), _about_names(store, thing)
        out += ["   Until it is answered, this is held up: %s." % "; ".join(up)] if up else \
               ["   It is about: %s." % "; ".join(about)] if about else []
    elif kind == "assumption":
        out += ["%d. Please confirm or correct: %s" % (n, value(thing, "working answer")), "   The question was: " + thing["name"],
                "   " + (_when(value(thing, "raised"), "We have been working on this basis since") or
                          "We are working on this basis until you say.")]
        about = _about_names(store, thing)
        out += ["   It is about: %s." % "; ".join(about)] if about else []
    elif kind == "observed":
        out += ["%d. Is this meant to happen? %s" % (n, value(thing, "behaviour")),
                "   This is what was seen to happen today. Please say which it is: intended, accidental, or a defect."]
        out += ["   " + t for t in (_when(value(thing, "raised"), "Noted"),) if t]
        bears = held_up(store, thing) or _about_names(store, thing)
        out += ["   It bears on: %s." % "; ".join(bears)] if bears else []
    else:
        item, approval = thing
        out.append("%d. Your decision on the sign-off brief%s" % (n, ": " + item["link"] if item else "."))
        out += ["   " + t for t in (_when(item["date"], "Sent") if item else "",) if t]
        if approval and approval["decision"] == "approved":
            out.append("   You approved an earlier version on %s. What has changed since is listed near the top of the "
                       "brief; only that needs your yes." % approval["date"])
        out.append("   " + house.words().get(APPROVE))
    return out


def _chasers(store, work, people, nobody):
    """`status --chasers` as lines: one message for each named person, then the items nobody owns. It is not a face:
    it has no template, no stamp and no place to go, and ba sends nothing."""
    if not (people or nobody):
        return ["Nobody named owes anything, so there is no message to send."]
    out = ["Chasers for: " + (work["name"] if work else "none yet")]
    if people:
        out.append("%s, one for each person who owes something. Copy each from the line after its '=== To' line down to "
                   "the next '===' line." % _plural(len(people), "message"))
    else:
        out.append("Nobody named owes anything, so there is no message to send.")
    house = _house(store["folder"], work or _new_record("work", "", "work.md", 1), None)[0]
    for name, entries in people.items():
        out += ["", "=== To: %s (%s) ===" % (name, _summary(entries)), "Hello %s," % name, "",
                'For "%s", %s waiting on you:' % (work["name"] if work else "this work", "this is" if len(entries) == 1 else "these are")]
        for n, (kind, thing) in enumerate(entries, 1):
            out += _chaser_item(store, n, kind, thing, house)
    if nobody:
        out += ["", "=== Nobody to ask ===", "%s no one who can answer, so no message was drafted. Add '- Owner: <name>' to:" % (
            _plural(len(nobody), "open item") + (" names" if len(nobody) == 1 else " name"))]
        out += ["  - " + x["name"] for _, x in nobody]
    out += ["", "===", "ba sends nothing and records nothing about these messages."]
    left = len(_waiting_on_reply(store))
    out += ["%s already asked %s left out." % (_plural(left, "item"), "is" if left == 1 else "are")] if left else []
    if any(k in ("question", "assumption") for _, entries in people.items() for k, _ in entries):
        out.append("If the person says a message went, add to each question in it: - Asked: " + _today())
    return out


def _next(store, work, size, latest, since, waiting, version, house=None, nobody=(), owed=()):
    """What to do next, plainly from the size. Each line names the command or the edit."""
    live = [r for r in store["records"] if r["kind"] == "requirement" and status_of(r) != "withdrawn"]
    names = lambda recs: ", ".join(r["name"] for r in recs)
    out = []
    bare = [r for r in live if not value(r, "priority")]
    if bare:
        out.append("Priority: add '- Priority: must | should | could | wont' to: %s." % names(bare))
    bare = [r for r in live if not r["examples"] and value(r, "category") != "non-functional"]
    if bare:
        out.append("Examples: add a '### Examples' section with '- said: <a case with a named person and numbers>' "
                   "to: %s." % names(bare))
    if nobody:
        names = "; ".join(q["name"] for q in nobody)
        out.append("Owner: nobody is named to answer: %s%s Add '- Owner: <who can answer>' to %s." % (
            names, "" if names[-1] in ".?!" else ".", "it" if len(nobody) == 1 else "each"))
    unwritten = [r for r in store["records"] if r["kind"] == "observed" and standing_of(r) == "intended"
                 and not value(r, "requirement")]
    if unwritten:
        out.append("Observed: %s called intended and no requirement says so. Write each as a Requirement in the business's "
                   "words, then add '- Requirement: <its ID>' to the Observed record." % "; ".join(r["name"] for r in unwritten))
    unstated = [r for r in store["records"] if r["kind"] == "observed" and standing_of(r) == "defect"
                and not value(r, "requirement")]
    if unstated:
        out.append("Observed: %s called a defect and name no requirement they depart from. Add '- Requirement: <its ID>', "
                   "or, if no required behaviour has been stated, raise a question and take the verdict off." %
                   "; ".join(r["name"] for r in unstated))
    cite = "baseline " + latest["name"] if latest and not any(since) else "records version " + version
    if not waiting and not (work and (value(work, "approvers") or work["approvals"])):
        out.append("Approval: no approvers named. Add '- Approvers: <names>' to the Work.")
    elif waiting:
        # waited on only once there is a brief of these records to answer (the answers of 24 November, Phase 4, 2)
        have = [n for n in waiting if n.lower() in [o.lower() for o in owed]]
        rest = [n for n in waiting if n not in have]
        out.append("Approval: %s. When one replies, add under '### Approvals' on the Work: "
                   "- <name>: approved, <date>, %s, \"<their words>\"" % ("; ".join(
                       x for x in ("waiting on " + ", ".join(have) if have else "", "not yet asked of " + ", ".join(rest) if rest else "") if x), cite))
        page = last_sent(work).get("signoff") if house and approval_of(house) == "page comment" else None
        if page:  # the yes is given on the page (ADR 0026): the helper says so, because no skill step does
            out.append("A yes may be a comment on the page %s: read the comments there with your Confluence tools, and "
                       "take the approver's name, the date and their own words from them. A yes said in a session or forwarded by "
                       "email is recorded the same way." % page["link"])
    out += _next_to_send(store, work, house)
    if size == "Small":
        return out
    if not live:
        out.append("In scope: no requirements yet. See the shape: %s --shape requirement" % CHECK)
    if not (work and work["out of scope"]):
        out.append("Out of scope: none listed. Add a '### Out of scope' section to the Work, one "
                   "'- <what is not included>' line each.")
    if not (work and work["glossary"]):
        out.append("Glossary: none. Add a '### Glossary' section to the Work, one '- <word>: <what the business "
                   "means by it>' line each.")
    nfr = [r for r in live if value(r, "category") == "non-functional"]
    thin = ["%s (%s)" % (r["name"], " and ".join(label(k) for k in ("measure", "threshold") if not value(r, k)))
            for r in nfr if not (value(r, "measure") and value(r, "threshold"))]
    if not nfr:
        out.append("Non-functional: none recorded. Ask about speed, volume, security and availability; add each as a "
                   "Requirement with '- Category: non-functional', '- Measure:' and '- Threshold:' lines.")
    elif thin:
        out.append("Non-functional: add '- Measure:' and '- Threshold:' lines to: %s." % ", ".join(thin))
    kept = [r for r in store["records"] if r["kind"] == "feature" and kept_original(store, r) and not value(r, "tracker")]
    out += ["Sliced: %s has parts and no tracker item. Set '- Status: withdrawn' on it; or, if work is already logged against its "
            "item, add '- Tracker: <the item>'." % " ".join(x for x in (f["id"], f["name"]) if x) for f in kept]
    current = live_features(store)
    if not current:
        if live:
            out.append("Features: none yet. Slice the requirements into Feature records, one for each group handed over "
                       "together (see the shape: %s --shape feature). Each gets a handover brief for the engineers: "
                       "%s bundle handover <feature>%s" % (CHECK, BA, FOLDER))
    else:
        loose = _loose(store)
        if loose:
            out.append("Features: name one of %s on the '- Feature:' line of: %s." % (
                ", ".join("'%s'" % _feature_shown(f, current) for f in current), ", ".join(r["name"] for r in loose)))
        for f in current:
            state, rel = _handover_state(store, f) if f["id"] and status_of(f) == "confirmed" else ("skip", "")
            if state == "none":
                out.append("Handover brief: no brief yet for %s. Make it: %s bundle handover %s%s" % (f["id"], BA, f["id"], FOLDER))
            elif state == "older":
                out.append("Handover brief: %s is older than the records. Make it again: %s bundle handover %s%s" % (
                    rel, BA, f["id"], FOLDER))
    if not latest:
        out.append("Baseline: none. Freeze the records before asking for sign-off: %s" % _baseline_cmd(_next_name(store["folder"], "v1")))
    elif any(since):
        after = _next_name(store["folder"], latest["name"])
        by = [a["name"] for a in last_answers(work).values() if a["decision"] == "approved"
              and (approved_baseline(store, a) or {}).get("name") == latest["name"]]
        n = sum(len(x) for x in since)
        count = _plural(n, "record")
        moved = size_moved(store, latest)
        if by:  # somebody said yes to the baseline that has changed since: a fact and a choice, never an instruction (ADR 0038)
            out.append("Changed since approval: %s from baseline %s, which %s approved%s. Whether this goes back for "
                       "sign-off is your call. If they have already agreed it, add under '### Approvals' on the Work: - <name>: "
                       "approved, <date>, records version %s, \"<their words>\"   To send it for sign-off, freeze: %s   Then "
                       "make the brief from it: %s --baseline %s   It lists what changed, the old wording beside the new." % (
                           count + (" differs" if n == 1 else " differ"), latest["name"], " and ".join([", ".join(by[:-1])] + by[-1:]) if len(by) > 1 else by[0],
                           "; the size was %s and is now %s" % moved if moved else "", version, _baseline_cmd(after),
                           BUNDLE + FOLDER, after))
        else:
            out.append("Baseline: %s changed since %s. Freeze again: %s" % (count, latest["name"], _baseline_cmd(after)))
    return out + (_next_large(store, work, current) if size == "Large" else [])


def _next_large(store, work, features):
    """What a large Work is asked for after what a medium one is (ADR 0032), each line only while it applies."""
    out = []
    if not (work and work["stakeholders"]):
        out.append("Stakeholders: none. Add a '### Stakeholders' section to the Work, one line each: - <name>: "
                   "<decides, consulted or told>, <what they need from this work>")
    if not (work and work["tolerances"]):
        out.append("Tolerances: none. Add a '### Tolerances' section to the Work, one line for each thing that may change "
                   "without going back to the approvers: - <what may move, and how far>")
    if not any(r["kind"] == "requirement" and status_of(r) != "withdrawn" and value(r, "category") == "transition"
               for r in store["records"]):
        out.append("Transition: no requirement says how the business gets from the old way to the new. Add one with "
                   "'- Category: transition'; if nothing is needed, write that as its statement with '- Priority: wont'.")
    out += ["Map: '%s' names no flow, so the scope brief cannot place it beside a step. Add '- Flow: <a flow>' to the "
            "Feature, and under '### Flow steps' the steps it delivers." % f["name"] for f in features if not f["flows"]]
    rel = face_file(FACES["scope"])
    how, m = _stamp_of(store, rel)
    if how == "none":
        out.append("Scope brief: none yet. Make one for the business owner to agree: %s bundle scope%s" % (BA, FOLDER))
    elif not (how == "stamped" and (m.group("b") or m.group("v") == version_of(store))):
        out.append("Scope brief: %s is older than the records. Make it again: %s bundle scope%s" % (rel, BA, FOLDER))
    if not (work and work["delivery"]):
        out.append("Forecast: none. Add a '### Delivery' section to the Work (see the shape: %s --shape work), then: "
                   "%s bundle delivery%s" % (CHECK, BA, FOLDER))
    return out


def _next_to_send(store, work, house):
    """The Next lines that say a brief is ready to send: made from the records as they are, to a place the house
    stores, and not yet sent from these records (ADR 0025)."""
    if not house or not work:
        return []
    dest, sent, out = house.places(), last_sent(work), []
    ready = lambda rel: _stamp_of(store, rel)[1] is not None and (lambda m: not m.group("b") and m.group("v") == version_of(store))(
        _stamp_of(store, rel)[1])
    behind = lambda key: not (key in sent and sent_is_current(store, sent[key]))
    sign = face_file(FACES["signoff"])
    if ready(sign) and (section_is_set(dest, "sign-off brief") or "signoff" in sent) and behind("signoff"):
        out.append("Send: the sign-off brief is ready to go to its place. Make the copy and the note: %s bundle signoff "
                   "--outbox%s" % (BA, FOLDER))
    for f in (r for r in live_features(store) if status_of(r) == "confirmed" and r["id"]):
        state, _ = _handover_state(store, f)
        if state == "current" and (_boards(house) or value(f, "tracker")) and behind(("handover " + f["id"]).lower()):
            out.append("Send: the handover brief of %s is ready to go to its place. Make the copy and the note: %s bundle "
                       "handover %s --outbox%s" % (f["id"], BA, f["id"], FOLDER))
    order = [i["face"].lower() for i in work["published"]]  # the order written is the order sent; no date is compared
    for f in (r for r in live_features(store) if status_of(r) == "confirmed" and r["id"]):
        business = ("business " + f["id"]).lower()
        if "signoff" in order and business in order and max(i for i, x in enumerate(order) if x == business) < order.index("signoff"):
            out.append("Send: the business item of %s does not link the sign-off page yet. %s bundle handover %s --outbox%s" % (
                f["id"], BA, f["id"], FOLDER))
    return out


def status_lines(store):
    """The status report as lines. Computed from the records and the files beside them; it writes nothing."""
    work = next((r for r in store["records"] if r["kind"] == "work"), None)
    recs, version = store["records"], version_of(store)
    size, yes = size_of(store)
    names = {r["id"]: r["name"] for r in recs if r["id"]}
    problems = _findings(store)
    nf = len([p for p in problems if p["level"] == "finding"])
    out = ["Workspace: " + store["folder"], "Work: " + (work["name"] if work else "none yet"),
           "Goal: " + ((value(work, "goal") if work else "") or "not given"),
           "Size: %s (%s)" % (size, "; ".join("%s: yes" % y for y in yes) if yes else "no size line says yes"),
           "Records:"] + [_counts_line(store, k) for k in KINDS if any(r["kind"] == k for r in recs)]
    out.append("Check: %s, %d information. Run: %s" % (_plural(nf, "finding"), len(problems) - nf, CHECK + FOLDER))
    out += _status_house(store, work)
    out += _status_published(store, work)
    out += _status_linked(work)
    out += _status_features(store)
    out += _status_delivery(store)
    out += _status_withdrawn(store)
    asks, assumed = _open_questions(store), _assumptions(store)

    def line(q, text, who, holds=False):
        about = _about_names(store, q)
        up = held_up(store, q) if holds else []
        extra = "; ".join(x for x in (who, _age_shown(value(q, "raised")), "about " + ", ".join(about) if about else "",
                                      "holds up " + ", ".join(up) if up else "") if x)
        return "  - %s (%s)" % (text, extra)

    out.append("Open questions: %s" % (len(asks) or "none"))
    out += [line(q, q["name"], _owes(q), True) for q in asks]
    out.append("Assumptions awaiting their owner: %s" % (len(assumed) or "none"))
    out += [line(q, value(q, "working answer"), _owes(q, True)) for q in assumed]
    waits = _waiting_on_reply(store)
    if waits:
        out.append("Asked, waiting on a reply: %d" % len(waits))
        for q in waits:
            when, _, rest = value(q, "asked").partition(",")
            ago = _ago(when.strip())
            up = held_up(store, q)
            extra = "; ".join(x for x in (_owes(q, bool(value(q, "working answer"))), ", ".join(
                x for x in ("asked " + when.strip(), ago, rest.strip()) if x), "holds up " + ", ".join(up) if up else "") if x)
            out.append("  - %s (%s)" % (q["name"], extra))
    if any(r["kind"] == "observed" for r in recs):
        waiting_verdict = _awaiting_verdict(store)
        out.append("Observed, awaiting a verdict: %s" % (len(waiting_verdict) or "none"))
        for r in waiting_verdict:
            bears = held_up(store, r)
            about = _about_names(store, r)
            extra = "; ".join(x for x in (_owes(r, True), _age_shown(value(r, "raised")), "about " + ", ".join(about) if about else "",
                                          "bears on " + ", ".join(bears) if bears else "") if x)
            out.append("  - %s: %s (%s)" % (r["name"], value(r, "behaviour"), extra))
    proposed = [(r["name"], sum(1 for e in r["examples"] if e["mark"] == "proposed")) for r in recs
                if r["kind"] == "requirement" and status_of(r) != "withdrawn"]
    proposed = [(n, c) for n, c in proposed if c]
    out.append("Examples to confirm: " + ("%d (%s)" % (sum(c for _, c in proposed), ", ".join(
        n + (" x%d" % c if c > 1 else "") for n, c in proposed)) if proposed else "none"))
    out.append(_status_brief(store))
    out += [x for x in (_status_face(store, FACES["scope"], "Scope brief"), _status_delivery_plan(store)) if x]
    found = _baselines(store["folder"])
    latest, since = (found[-1] if found else None), ([], [], [])
    if latest:
        since = _since(store, latest, grouping=False)
        lines = _since_lines(store, latest, grouping=False)
        waived = ", frozen with a waiver: " + latest["waiver"] if latest["waiver"] else ""
        out.append("Baselines: %s (latest%s). %s" % (", ".join(b["name"] for b in found), waived, lines[0]) if len(found) == 1 else
                   "Baselines: %s. %s" % (", ".join(b["name"] + (" (latest%s)" % waived if b is latest else "") for b in found), lines[0]))
        out += lines[1:]
    else:
        out.append("Baselines: none")
    shown, waiting, owed, ask = _status_approvals(store, work, version)
    out += ["Approvals:"] + shown
    people, nobody = _who_owes(store, owed)
    out += _waiting_on(store, people, nobody)
    todo = _next(store, work, size, latest, since, ask, version, _house(store["folder"], work, None)[0] if work else None,
                 [x for _, x in nobody if x["kind"] == "question"], [n for n, _, _ in owed])
    return out + ["Next:"] + (["  - " + t for t in todo] or ["  Nothing outstanding."])


def status(args):
    folder = find_workspace(args.folder)
    if folder is None:
        where, misplaced = _no_workspace(args.folder, BA + " status")
        print(misplaced or "No work.md %s, so there is no status yet. A workspace is a folder holding work.md. "
              "To start one, create work.md with a Work record: %s --shape work" % (where, CHECK))
        return 0
    store = read_workspace(folder)
    if args.chasers:
        work = next((r for r in store["records"] if r["kind"] == "work"), None)
        print("\n".join(_chasers(store, work, *_who_owes(store, _status_approvals(store, work, version_of(store))[2]))))
    else:
        print("\n".join(status_lines(store)))
    return 0


# ==== helper/src/cli.py =====================================================
"""Command line: the four verbs, argument parsing, and what a tool fault looks like.

Owns VERBS (lint counts its keys), main, and the one-line fault message. Must not know: the work any verb does.
"""

# The verb list. One table; lint counts the keys. Budget: 4 verbs.
VERBS = {
    "status": ("Show where the work stands.", "python3 <skill folder>/scripts/ba.py status"),
    "check": ("Check the records and say how to fix each finding.", "python3 <skill folder>/scripts/ba.py check"),
    "bundle": ("Make a brief from the records, with slots left to fill.",
               "python3 <skill folder>/scripts/ba.py bundle signoff"),
    "baseline": ("Freeze the approved version.", "python3 <skill folder>/scripts/ba.py baseline"),
}


def run(verb, args):
    if verb == "check":
        return check(args)
    if verb == "bundle":
        return bundle(args)
    if verb == "baseline":
        return baseline(args)
    if verb == "status":
        return status(args)
    print("ba %s: not built yet" % verb)
    return 0


def _source_of(path, line):
    """Where a line of this built file comes from: 'helper/src/<module>.py line N', or '' for a line elsewhere.
    Each part of the file starts with a banner comment naming its module (tools/build.py), and the module's own
    lines follow it one for one."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")[:line]
    except OSError:
        return ""
    for n in range(len(lines) - 1, 0, -1):
        m = re.match(r"^# ==== (helper/src/\w+\.py) =", lines[n])
        if m:
            return "%s line %d" % (m.group(1), line - n - 1)
    return ""


def _fault(exc):
    """One line for the screen; the traceback goes to a file, with each line of this file placed in its module."""
    detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    where_in_source = []
    for frame in traceback.extract_tb(exc.__traceback__):
        if os.path.abspath(frame.filename) == os.path.abspath(__file__) and _source_of(frame.filename, frame.lineno):
            where_in_source.append("  %s: in %s" % (_source_of(frame.filename, frame.lineno), frame.name))
    if where_in_source:
        detail += "\nIn the source modules:\n" + "\n".join(where_in_source) + "\n"
    try:
        fd, path = tempfile.mkstemp(prefix="ba-fault-", suffix=".txt")
        with os.fdopen(fd, "w") as f:
            f.write(detail)
        where = "The detail is in %s." % path
    except OSError:
        where = "The detail could not be saved."
    print("ba hit a fault in the tool itself (%s), not in your records. %s To carry on by hand, read and edit "
          "work.md and the files in records/ directly; a backup from --fix, if one was made, is in backup/. "
          "Tell the maintainer." % (type(exc).__name__, where), file=sys.stderr)
    return 1


def main(argv=None):
    global BA, CHECK, BUNDLE, FOLDER
    name = sys.argv[0] if sys.argv and sys.argv[0] else "ba.py"
    BA = "python3 %s" % shlex.quote(name)
    CHECK, BUNDLE, FOLDER = BA + " check", BA + " bundle signoff", ""
    parser = argparse.ArgumentParser(
        prog="ba",
        description="BA skills helper. Verbs: %s." % ", ".join(VERBS),
        epilog="Example: " + VERBS["check"][1],
    )
    sub = parser.add_subparsers(dest="verb", metavar="verb")
    for verb, (summary, example) in VERBS.items():
        p = sub.add_parser(
            verb,
            help=summary,
            description=summary,
            epilog="Example: " + example if verb != "bundle" else
            "Examples, one for each brief:\n" + "\n".join("  " + example.replace("bundle signoff", "bundle " + face)
                                                          for face in ("signoff", "scope", "delivery", "handover <feature>")),
            formatter_class=argparse.RawDescriptionHelpFormatter if verb == "bundle" else argparse.HelpFormatter,
        )
        if verb == "check":
            p.add_argument("folder", nargs="?",
                           help="the workspace folder (default: this folder, or the nearest one above holding work.md)")
            p.add_argument("--shape", nargs="?", const="", metavar="KIND",
                           help="print a filled-in record of that kind to copy: work, requirement, "
                                "question, flow or feature; or all, for all five. With no kind, list the kinds")
            p.add_argument("--fix", action="store_true",
                           help="assign IDs to records that have a handle or none, and rewrite those handles in "
                                "About lines. Writes a backup to backup/ first and changes nothing else")
            p.add_argument("--house", metavar="FOLDER",
                           help="the house the briefs in faces/ were made with, if not the Work's House line")
            p.add_argument("--adopt", metavar="HOUSE",
                           help="check a house, a folder or a pack, before it is used: what it holds, what its templates "
                                "cover and where its briefs go. Needs no workspace and writes nothing")
        if verb == "status":
            p.add_argument("folder", nargs="?",
                           help="the workspace folder (default: this folder, or the nearest one above holding work.md)")
            p.add_argument("--chasers", action="store_true",
                           help="print one message for each person who owes an answer or a sign-off, and the items nobody "
                                "owns. Nothing is sent and nothing is written")
        if verb == "baseline":
            p.add_argument("name", nargs="?", help="the name to freeze the records under, for example v1. "
                           "With no name, list the baselines and what changed since the latest")
            p.add_argument("folder", nargs="?",
                           help="the workspace folder (default: this folder, or the nearest one above holding work.md)")
            p.add_argument("--waive", metavar="REASON",
                           help="freeze although the records have findings, and record this reason with the baseline "
                                "and on every brief made from it")
        if verb == "bundle":
            p.add_argument("face", nargs="?", help="the brief to make: signoff, scope, delivery, or handover")
            p.add_argument("more", nargs="*", metavar="feature folder",
                           help="for handover, the Feature (its ID, handle or name; with none given the Features are "
                                "listed) and then the workspace folder; for the others, the workspace folder. The default "
                                "folder is this one, or the nearest one above holding work.md")
            p.add_argument("--form", metavar="FORM",
                           help="which form of the brief: moscow (a priority table) or process-map (the flow first, "
                                "each step described). Default: the Work's 'Sign-off form' line, else moscow")
            p.add_argument("--house", metavar="FOLDER",
                           help="a folder of house words and templates, for this run only. Default: the Work's "
                                "House line, else the shipped house")
            p.add_argument("--baseline", metavar="NAME",
                           help="make the brief from the baseline of this name, not from the working records; "
                                "the stamp names the baseline")
            p.add_argument("--outbox", action="store_true",
                           help="also write the copy to send and a note to outbox/, and print the note: where the "
                                "brief goes and what to record once it is sent")
    args = parser.parse_args(argv)
    if not args.verb:
        parser.print_help()
        return 0
    if args.verb == "bundle":
        more = list(args.more)
        args.feature = args.folder = None
        made = FACES.get(args.face) or {}
        if made.get("for") and not (len(more) == 1 and os.path.isfile(os.path.join(more[0], "work.md"))):
            args.feature = more.pop(0) if more else None  # a lone word that is a folder holding work.md is the folder
        args.folder = more[0] if more else None
    if args.verb in ("check", "bundle", "baseline", "status") and args.folder:
        FOLDER = " " + shlex.quote(args.folder)
    if args.verb == "bundle":
        FOLDER = FOLDER or ""
    try:
        return run(args.verb, args)
    except Unreadable as e:
        print("ba could not read %s: it is not saved as UTF-8 text. Nothing was changed. "
              "Save that file as UTF-8 and run the command again." % e.args[0], file=sys.stderr)
        return 2
    except OSError as e:
        print("ba could not read or write %s (%s). That is the folder or the file, not your records and not a "
              "fault in ba. Check the file is there and can be written, then run the command again."
              % (e.filename or "a file", e.strerror or type(e).__name__), file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 - anything unexpected is the tool's fault, said plainly
        return _fault(e)


if __name__ == "__main__":
    sys.exit(main())
