"""
Compare two ARXML files and return structured counts and differences.
Deterministic, no LLM. Used by the Compare ARXML UI.
"""
import os
import xml.etree.ElementTree as ET
from typing import Any, Tuple

# Element types we index for hierarchy diff (Added / Removed / Modified / Renamed)
HIERARCHY_SIGNIFICANT_TAGS = frozenset({
    "AR-PACKAGE",
    "APPLICATION-SOFTWARE-COMPONENT-TYPE",
    "COMPOSITION-SW-COMPONENT-TYPE",
    "COMPONENT-PROTOTYPE",
    "P-PORT-PROTOTYPE",
    "R-PORT-PROTOTYPE",
    "IMPLEMENTATION-DATA-TYPE",
    "APPLICATION-PRIMITIVE-DATA-TYPE",
    "SENDER-RECEIVER-INTERFACE",
    "CLIENT-SERVER-INTERFACE",
    "VARIABLE-DATA-PROTOTYPE",
})
MAX_HIERARCHY_ENTRIES = 100
# Max entries per tag type to avoid huge reports (None = no cap)
MAX_ENTRIES_PER_TAG = 50

# Category map for enterprise report: tag -> architecture | interfaces | data_model | signals | metadata
TAG_TO_CATEGORY: dict[str, str] = {
    "AR-PACKAGE": "architecture",
    "APPLICATION-SOFTWARE-COMPONENT-TYPE": "architecture",
    "COMPOSITION-SW-COMPONENT-TYPE": "architecture",
    "COMPONENT-PROTOTYPE": "architecture",
    "P-PORT-PROTOTYPE": "interfaces",
    "R-PORT-PROTOTYPE": "interfaces",
    "SENDER-RECEIVER-INTERFACE": "interfaces",
    "CLIENT-SERVER-INTERFACE": "interfaces",
    "IMPLEMENTATION-DATA-TYPE": "data_model",
    "APPLICATION-PRIMITIVE-DATA-TYPE": "data_model",
    "VARIABLE-DATA-PROTOTYPE": "data_model",
}
CATEGORY_ORDER = ("architecture", "interfaces", "data_model", "signals", "metadata")

# Tags treated as interface/port for severity: removed=HIGH, renamed=MEDIUM, moved=LOW
INTERFACE_OR_PORT_TAGS = frozenset({
    "SENDER-RECEIVER-INTERFACE",
    "CLIENT-SERVER-INTERFACE",
    "P-PORT-PROTOTYPE",
    "R-PORT-PROTOTYPE",
})


def _tag_local(elem: ET.Element) -> str:
    """Return local tag name without namespace."""
    if elem.tag and "}" in elem.tag:
        return elem.tag.split("}", 1)[1]
    return elem.tag or ""


def _child_text_local(elem: ET.Element, local_name: str, default: str = "") -> str:
    """Get text of first child with given local tag name (namespace-agnostic)."""
    if elem is None:
        return default
    for child in elem:
        if _tag_local(child) == local_name and child.text:
            return child.text.strip()
    return default


def _get_attr_local(elem: ET.Element, attr_name: str) -> str:
    """Return attribute value by local name (namespace-agnostic)."""
    v = elem.attrib.get(attr_name)
    if v:
        return v
    for key in elem.attrib:
        local = key.split("}")[-1] if "}" in key else key
        if local == attr_name:
            return elem.attrib[key]
    return ""


def _get_all_attribs_local(elem: ET.Element) -> dict[str, str]:
    """Build dict of local attribute name -> value (namespace-agnostic). First key wins per local name."""
    out: dict[str, str] = {}
    for key in elem.attrib:
        local = key.split("}")[-1] if "}" in key else key
        if local not in out:
            out[local] = elem.attrib[key]
    return out


def _get_uuid(elem: ET.Element) -> str | None:
    """Get UUID attribute from element (handles namespaced UUID)."""
    u = _get_attr_local(elem, "UUID")
    return u if u else None


def _count_tags(root: ET.Element) -> dict[str, int]:
    """Count all element tags in the tree."""
    counts: dict[str, int] = {}
    for elem in root.iter():
        tag = _tag_local(elem)
        if tag:
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def _collect_short_names(root: ET.Element, path: str) -> set[str]:
    """Collect SHORT-NAME text values under elements matching path (local name). Namespace-agnostic."""
    names: set[str] = set()
    for elem in root.iter():
        if _tag_local(elem) == path:
            name = _child_text_local(elem, "SHORT-NAME")
            if name:
                names.add(name)
    return names


def _collect_uuids(root: ET.Element) -> set[str]:
    """Collect all UUID attribute values (namespace-agnostic)."""
    uuids: set[str] = set()
    for elem in root.iter():
        u = _get_uuid(elem)
        if u:
            uuids.add(u)
    return uuids


def _normalize_path(path: str) -> str:
    """Normalize path for comparison (leading slash, no trailing slash)."""
    if not path or not path.strip():
        return ""
    p = path.strip().strip("/")
    return "/" + p if p else ""


# Richer signature: (uuid, num_children, attribs_sig, child_tags_sig, interface_ref)
_Sig = Tuple[str, int, Tuple[Tuple[str, str], ...], Tuple[str, ...], str]


def _elem_signature(elem: ET.Element) -> _Sig:
    """Return (uuid, num_children, attribs_sig, child_tags_sig, interface_ref) for modified detection."""
    uuid_val = _get_uuid(elem) or ""
    children = list(elem)
    num_children = len(children)
    attrs = _get_all_attribs_local(elem)
    attribs_sig = tuple(sorted(attrs.items()))
    child_tags_sig = tuple(sorted(_tag_local(c) for c in children))
    interface_ref = (
        _child_text_local(elem, "PROVIDED-INTERFACE-TREF")
        or _child_text_local(elem, "REQUIRED-INTERFACE-TREF")
        or ""
    )
    return (uuid_val, num_children, attribs_sig, child_tags_sig, interface_ref)


def _modified_summary(sig_a: _Sig, sig_b: _Sig) -> str:
    """Build human-readable summary of what changed between two element signatures."""
    reasons: list[str] = []
    if sig_a[0] != sig_b[0]:
        reasons.append("UUID changed")
    if sig_a[2] != sig_b[2]:
        reasons.append("attributes changed")
    if sig_a[3] != sig_b[3]:
        reasons.append("child structure changed")
    if sig_a[4] != sig_b[4]:
        reasons.append("interface reference changed")
    return "; ".join(reasons) if reasons else "content changed"


def _is_likely_rename(short_name_a: str, short_name_b: str) -> bool:
    """
    Heuristic: treat as rename if one name is the other plus a suffix (e.g. _test_for_students),
    or one is a substring of the other. Prefer exact suffix match to avoid false positives.
    """
    if not short_name_a or not short_name_b or short_name_a == short_name_b:
        return False
    # Common pattern: BaseName -> BaseName_test_for_students or BaseName_test
    if short_name_b == short_name_a + "_test_for_students" or short_name_b.startswith(short_name_a + "_"):
        return True
    if short_name_a == short_name_b + "_test_for_students" or short_name_a.startswith(short_name_b + "_"):
        return True
    # One contains the other (e.g. Message4 vs Message4_test_for_students)
    if short_name_a in short_name_b or short_name_b in short_name_a:
        return True
    return False


def _build_hierarchy_index(
    root: ET.Element,
    significant_tags: frozenset[str],
) -> dict[str, Tuple[str, str, _Sig]]:
    """Build path -> (tag, short_name, signature) for significant elements. Path is normalized."""
    index: dict[str, Tuple[str, str, _Sig]] = {}

    def visit(elem: ET.Element, parent_path: str) -> None:
        tag = _tag_local(elem)
        short_name = _child_text_local(elem, "SHORT-NAME")
        if short_name:
            current = f"{parent_path}/{short_name}" if parent_path else "/" + short_name
            current = _normalize_path(current)
        else:
            current = parent_path
        if tag in significant_tags and short_name:
            current = _normalize_path(current)
            sig = _elem_signature(elem)
            index[current] = (tag, short_name, sig)
        for child in elem:
            visit(child, current)

    visit(root, "")
    return index


def _build_dependency_map(
    index: dict[str, Tuple[str, str, _Sig]],
) -> dict[str, list[str]]:
    """
    For each port/interface short_name in the hierarchy index, list parent paths (owning component).
    Used for change traceability: which SWCs/compositions are affected by a changed port/interface.
    """
    out: dict[str, list[str]] = {}
    for path, (tag, short_name, _) in index.items():
        if tag not in INTERFACE_OR_PORT_TAGS:
            continue
        parent = _normalize_path(path)
        if parent and parent != "/":
            head, _, _ = parent.rpartition("/")
            parent_path = head or "/"
        else:
            parent_path = "/"
        out.setdefault(short_name, []).append(parent_path)
    return out


def _path_to_swc_display_name(path: str, index: dict[str, Tuple[str, str, _Sig]]) -> str:
    """
    Return a display name for the component at path: prefer COMPONENT-PROTOTYPE SHORT-NAME
    from index, else last path segment.
    """
    if not path or path == "/":
        return ""
    path_norm = _normalize_path(path)
    if path_norm in index:
        tag = index[path_norm][0]
        short_name = index[path_norm][1]
        if tag == "COMPONENT-PROTOTYPE":
            return short_name
    # Fallback: last segment
    segment = path_norm.strip("/").split("/")[-1] if path_norm else ""
    return segment or ""


def _affected_components_to_swc_names(
    affected_paths: list[str],
    index: dict[str, Tuple[str, str, _Sig]],
) -> list[str]:
    """Convert affected_components paths to deduplicated, ordered list of SWC display names."""
    names: list[str] = []
    seen: set[str] = set()
    for p in affected_paths:
        name = _path_to_swc_display_name(p, index)
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _extract_port_short_name_from_ref(elem: ET.Element) -> str | None:
    """From a PROVIDER-IREF or REQUESTER-IREF element, extract the port prototype short name (last segment of ref)."""
    if elem is None:
        return None
    # Direct text content (path)
    text = (elem.text or "").strip()
    if not text:
        for child in elem:
            if _tag_local(child) in (
                "TARGET-P-PORT-REF",
                "TARGET-R-PORT-REF",
                "TARGET-P-PORT-PROTOTYPE-REF",
                "TARGET-R-PORT-PROTOTYPE-REF",
            ):
                text = (child.text or "").strip()
                break
            t = (child.text or "").strip()
            if t:
                text = t
                break
    if not text:
        return None
    # Last segment of path
    segment = text.split("/")[-1].strip() if "/" in text else text
    return segment or None


def _build_connector_map(root: ET.Element) -> dict[str, int]:
    """
    Count ASSEMBLY-SW-CONNECTOR references per port short name.
    Returns port_short_name -> number of connectors that reference it.
    """
    port_counts: dict[str, int] = {}
    for elem in root.iter():
        if _tag_local(elem) != "ASSEMBLY-SW-CONNECTOR":
            continue
        for child in elem:
            tag = _tag_local(child)
            if tag in ("PROVIDER-IREF", "REQUESTER-IREF"):
                name = _extract_port_short_name_from_ref(child)
                if name:
                    port_counts[name] = port_counts.get(name, 0) + 1
    return port_counts


def _classify_impact_severity(rte_mappings: dict[str, int]) -> str:
    """Classify impact severity from RTE connector counts: 0=LOW, 1-3=MEDIUM, >3=HIGH."""
    total = (rte_mappings.get("file_a") or 0) + (rte_mappings.get("file_b") or 0)
    if total == 0:
        return "LOW"
    if total <= 3:
        return "MEDIUM"
    return "HIGH"


def _impact_score(
    connectors: int,
    affected_swc_count: int,
    interface_changes: int,
) -> int:
    """
    Compute 0-10 impact score: connectors*2 + affected_swcs*2 + interface_changes*1, capped at 10.
    """
    raw = (connectors * 2) + (affected_swc_count * 2) + (interface_changes * 1)
    return min(10, max(0, raw))


def _build_interface_signals_map(root: ET.Element) -> dict[str, list[str]]:
    """
    For each SENDER-RECEIVER-INTERFACE and CLIENT-SERVER-INTERFACE, collect SHORT-NAME of
    VARIABLE-DATA-PROTOTYPE children. Returns interface_short_name -> [signal short names].
    """
    out: dict[str, list[str]] = {}
    for elem in root.iter():
        tag = _tag_local(elem)
        if tag not in ("SENDER-RECEIVER-INTERFACE", "CLIENT-SERVER-INTERFACE"):
            continue
        iface_name = _child_text_local(elem, "SHORT-NAME")
        if not iface_name:
            continue
        signals: list[str] = []
        for child in elem:
            if _tag_local(child) == "VARIABLE-DATA-PROTOTYPE":
                sn = _child_text_local(child, "SHORT-NAME")
                if sn:
                    signals.append(sn)
        out[iface_name] = signals
    return out


def _build_port_to_interface_map(root: ET.Element) -> dict[str, str]:
    """
    For each P-PORT-PROTOTYPE and R-PORT-PROTOTYPE, map port short name to interface short name
    (last segment of PROVIDED-INTERFACE-TREF / REQUIRED-INTERFACE-TREF).
    """
    out: dict[str, str] = {}
    for elem in root.iter():
        tag = _tag_local(elem)
        if tag not in ("P-PORT-PROTOTYPE", "R-PORT-PROTOTYPE"):
            continue
        port_name = _child_text_local(elem, "SHORT-NAME")
        if not port_name:
            continue
        ref = (
            _child_text_local(elem, "PROVIDED-INTERFACE-TREF")
            or _child_text_local(elem, "REQUIRED-INTERFACE-TREF")
            or ""
        )
        if not ref:
            continue
        segment = ref.strip("/").split("/")[-1] if "/" in ref else ref.strip()
        if segment:
            out[port_name] = segment
    return out


def _get_affected_signals_and_interfaces(
    item_type: str,
    short_name: str,
    interface_signals: dict[str, list[str]],
    port_to_interface: dict[str, str],
) -> tuple[list[str], list[str]]:
    """
    Return (affected_signals, affected_interfaces) for a changed port or interface.
    """
    affected_signals: list[str] = []
    affected_interfaces: list[str] = []
    if item_type in ("SENDER-RECEIVER-INTERFACE", "CLIENT-SERVER-INTERFACE"):
        affected_interfaces = [short_name] if short_name else []
        affected_signals = list(interface_signals.get(short_name, [])[:20])
    elif item_type in ("P-PORT-PROTOTYPE", "R-PORT-PROTOTYPE"):
        iface = port_to_interface.get(short_name, "")
        if iface:
            affected_interfaces = [iface]
            affected_signals = list(interface_signals.get(iface, [])[:20])
    return (affected_signals, affected_interfaces)


def compare_two_arxml_files(path_a: str, path_b: str) -> dict[str, Any]:
    """
    Compare two ARXML files. Returns a structured dict for the UI.

    Keys: summary, counts_a, counts_b, only_in_a, only_in_b, only_in_b_names,
    port_diff, swc_diff, uuid_diff, error (if parse failed).
    """
    result: dict[str, Any] = {
        "summary": "",
        "counts_a": {},
        "counts_b": {},
        "only_in_a": [],
        "only_in_b": [],
        "port_diff": {},
        "swc_diff": {},
        "uuid_diff": {},
        "hierarchy_diff": {"added": [], "removed": [], "modified": []},
        "error": None,
    }
    if not path_a or not path_b:
        result["error"] = "Both file paths are required."
        return result
    if not os.path.isfile(path_a):
        result["error"] = f"File not found: {path_a}"
        return result
    if not os.path.isfile(path_b):
        result["error"] = f"File not found: {path_b}"
        return result
    if os.path.normpath(path_a) == os.path.normpath(path_b):
        result["error"] = "Please select two different files."
        return result

    try:
        tree_a = ET.parse(path_a)
        root_a = tree_a.getroot()
    except ET.ParseError as e:
        result["error"] = f"Invalid ARXML (File A): {e}"
        return result
    except Exception as e:
        result["error"] = f"Failed to read File A: {e}"
        return result

    try:
        tree_b = ET.parse(path_b)
        root_b = tree_b.getroot()
    except ET.ParseError as e:
        result["error"] = f"Invalid ARXML (File B): {e}"
        return result
    except Exception as e:
        result["error"] = f"Failed to read File B: {e}"
        return result

    name_a = os.path.basename(path_a)
    name_b = os.path.basename(path_b)

    # Tag counts
    result["counts_a"] = _count_tags(root_a)
    result["counts_b"] = _count_tags(root_b)
    all_tags = set(result["counts_a"]) | set(result["counts_b"])
    only_in_a = [t for t in all_tags if result["counts_a"].get(t, 0) > 0 and result["counts_b"].get(t, 0) == 0]
    only_in_b = [t for t in all_tags if result["counts_b"].get(t, 0) > 0 and result["counts_a"].get(t, 0) == 0]
    result["only_in_a"] = sorted(only_in_a)[:30]
    result["only_in_b"] = sorted(only_in_b)[:30]

    # Ports (P-PORT / R-PORT via common patterns)
    ports_a = _collect_short_names(root_a, "P-PORT-PROTOTYPE") | _collect_short_names(root_a, "R-PORT-PROTOTYPE")
    ports_b = _collect_short_names(root_b, "P-PORT-PROTOTYPE") | _collect_short_names(root_b, "R-PORT-PROTOTYPE")
    result["port_diff"] = {
        "only_in_a": sorted(ports_a - ports_b)[:50],
        "only_in_b": sorted(ports_b - ports_a)[:50],
        "count_a": len(ports_a),
        "count_b": len(ports_b),
        # renamed_count will be filled after rename detection
        "renamed_count": 0,
    }

    # SWC (application + composition + component prototype)
    swc_app_a = _collect_short_names(root_a, "APPLICATION-SOFTWARE-COMPONENT-TYPE")
    swc_app_b = _collect_short_names(root_b, "APPLICATION-SOFTWARE-COMPONENT-TYPE")
    swc_comp_a = _collect_short_names(root_a, "COMPOSITION-SW-COMPONENT-TYPE")
    swc_comp_b = _collect_short_names(root_b, "COMPOSITION-SW-COMPONENT-TYPE")
    swc_proto_a = _collect_short_names(root_a, "COMPONENT-PROTOTYPE")
    swc_proto_b = _collect_short_names(root_b, "COMPONENT-PROTOTYPE")
    swc_a = swc_app_a | swc_comp_a | swc_proto_a
    swc_b = swc_app_b | swc_comp_b | swc_proto_b
    result["swc_diff"] = {
        "only_in_a": sorted(swc_a - swc_b)[:50],
        "only_in_b": sorted(swc_b - swc_a)[:50],
        "count_a": len(swc_a),
        "count_b": len(swc_b),
    }

    # UUIDs
    uuids_a = _collect_uuids(root_a)
    uuids_b = _collect_uuids(root_b)
    common_uuids = uuids_a & uuids_b
    result["uuid_diff"] = {
        "count_a": len(uuids_a),
        "count_b": len(uuids_b),
        "common": len(common_uuids),
        "only_in_a": len(uuids_a - uuids_b),
        "only_in_b": len(uuids_b - uuids_a),
    }

    # Hierarchy diff (Added / Removed / Modified); then rename detection
    index_a = _build_hierarchy_index(root_a, HIERARCHY_SIGNIFICANT_TAGS)
    index_b = _build_hierarchy_index(root_b, HIERARCHY_SIGNIFICANT_TAGS)
    paths_a = set(index_a)
    paths_b = set(index_b)
    added_paths = paths_b - paths_a
    removed_paths = paths_a - paths_b
    common_paths = paths_a & paths_b

    # Cap by tag type to avoid huge output
    def _cap_by_tag(paths: set[str], index: dict, limit: int) -> list[str]:
        by_tag: dict[str, list[str]] = {}
        for p in paths:
            tag = index[p][0]
            by_tag.setdefault(tag, []).append(p)
        out: list[str] = []
        for tag in sorted(by_tag):
            out.extend(sorted(by_tag[tag])[: limit if MAX_ENTRIES_PER_TAG else MAX_HIERARCHY_ENTRIES])
        return out[:MAX_HIERARCHY_ENTRIES]

    cap = MAX_ENTRIES_PER_TAG or MAX_HIERARCHY_ENTRIES
    added_paths_sorted = _cap_by_tag(added_paths, index_b, cap)
    removed_paths_sorted = _cap_by_tag(removed_paths, index_a, cap)

    added_list: list[dict[str, Any]] = []
    for p in added_paths_sorted:
        tag, short_name, _ = index_b[p]
        added_list.append({"path": p, "type": tag, "short_name": short_name})
    removed_list: list[dict[str, Any]] = []
    for p in removed_paths_sorted:
        tag, short_name, _ = index_a[p]
        removed_list.append({"path": p, "type": tag, "short_name": short_name})

    # Rename detection: same type, similar short_name -> treat as renamed
    renamed_list: list[dict[str, Any]] = []
    used_added: set[int] = set()
    new_removed: list[dict[str, Any]] = []
    for r in removed_list:
        matched = None
        for i, a in enumerate(added_list):
            if i in used_added:
                continue
            if r["type"] == a["type"] and _is_likely_rename(r["short_name"], a["short_name"]):
                matched = i
                break
        if matched is not None:
            used_added.add(matched)
            renamed_list.append({
                "path_a": r["path"],
                "path_b": added_list[matched]["path"],
                "type": r["type"],
                "short_name_a": r["short_name"],
                "short_name_b": added_list[matched]["short_name"],
            })
        else:
            new_removed.append(r)
    new_added = [a for i, a in enumerate(added_list) if i not in used_added]
    added_list = new_added
    removed_list = new_removed

    modified_list: list[dict[str, Any]] = []
    for p in sorted(common_paths)[:MAX_HIERARCHY_ENTRIES]:
        _, _, sig_a = index_a[p]
        _, _, sig_b = index_b[p]
        if sig_a != sig_b:
            tag, short_name, _ = index_a[p]
            summary = _modified_summary(sig_a, sig_b)
            modified_list.append({
                "path": p,
                "type": tag,
                "short_name": short_name,
                "summary": summary,
            })

    result["hierarchy_diff"] = {
        "added": added_list,
        "removed": removed_list,
        "modified": modified_list,
        "renamed": renamed_list,
    }
    # Port rename count for impact / port stats
    result["port_diff"]["renamed_count"] = sum(
        1 for item in renamed_list if item["type"] in ("P-PORT-PROTOTYPE", "R-PORT-PROTOTYPE")
    )

    # Grouped hierarchy (parent path + leaf short-names) to reduce path noise
    def _parent_path(path: str) -> str:
        path = _normalize_path(path)
        if not path or path == "/":
            return path
        head, _, _ = path.rpartition("/")
        return head or "/"

    grouped: dict[str, list[dict[str, Any]]] = {
        "added": [],
        "removed": [],
        "modified": [],
        "renamed": [],
    }

    # Added / removed: group by (parent_path, type)
    for key, src in (("added", added_list), ("removed", removed_list)):
        buckets: dict[tuple[str, str], list[str]] = {}
        for item in src:
            parent = _parent_path(item["path"])
            bucket_key = (parent, item["type"])
            buckets.setdefault(bucket_key, []).append(item["short_name"])
        for (parent, tag), names in sorted(buckets.items()):
            grouped[key].append(
                {
                    "parent": parent,
                    "type": tag,
                    "short_names": sorted(names),
                }
            )

    # Modified: keep per-child summaries but group under parent
    buckets_mod: dict[tuple[str, str], list[dict[str, str]]] = {}
    for item in modified_list:
        parent = _parent_path(item["path"])
        bucket_key = (parent, item["type"])
        buckets_mod.setdefault(bucket_key, []).append(
            {
                "short_name": item["short_name"],
                "summary": item["summary"],
            }
        )
    for (parent, tag), items in sorted(buckets_mod.items()):
        grouped["modified"].append(
            {
                "parent": parent,
                "type": tag,
                "items": items,
            }
        )

    # Renamed: group by (parent_a, parent_b, type)
    buckets_ren: dict[tuple[str, str, str], list[tuple[str, str]]] = {}
    for item in renamed_list:
        parent_a = _parent_path(item["path_a"])
        parent_b = _parent_path(item["path_b"])
        key = (parent_a, parent_b, item["type"])
        buckets_ren.setdefault(key, []).append(
            (item["short_name_a"], item["short_name_b"])
        )
    for (parent_a, parent_b, tag), pairs in sorted(buckets_ren.items()):
        grouped["renamed"].append(
            {
                "parent_a": parent_a,
                "parent_b": parent_b,
                "type": tag,
                "pairs": [
                    {"from": a, "to": b}
                    for (a, b) in pairs
                ],
            }
        )

    result["hierarchy_diff_grouped"] = grouped

    # Group by category for enterprise report
    def _category(tag: str) -> str:
        return TAG_TO_CATEGORY.get(tag, "metadata")

    changes_by_cat: dict[str, dict[str, list]] = {
        cat: {"added": [], "removed": [], "modified": [], "renamed": []}
        for cat in CATEGORY_ORDER
    }
    for item in result["hierarchy_diff"]["added"]:
        changes_by_cat[_category(item["type"])]["added"].append(item)
    for item in result["hierarchy_diff"]["removed"]:
        changes_by_cat[_category(item["type"])]["removed"].append(item)
    for item in result["hierarchy_diff"]["modified"]:
        changes_by_cat[_category(item["type"])]["modified"].append(item)
    for item in result["hierarchy_diff"]["renamed"]:
        changes_by_cat[_category(item["type"])]["renamed"].append(item)
    # Metadata: tag-only differences (e.g. DummyModifiedMarker)
    meta_added = result.get("only_in_b", [])
    meta_removed = result.get("only_in_a", [])
    if meta_added or meta_removed:
        changes_by_cat["metadata"]["added"] = [{"tag": t} for t in meta_added[:20]]
        changes_by_cat["metadata"]["removed"] = [{"tag": t} for t in meta_removed[:20]]
    result["changes_by_category"] = changes_by_cat

    # Severity classification: removed=HIGH, renamed=MEDIUM, moved=LOW for interfaces/ports
    added_type_name = {(item["type"], item["short_name"]) for item in added_list}
    severity_examples: dict[str, list[str]] = {"HIGH": [], "MEDIUM": [], "LOW": []}
    severity_counts: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

    for item in removed_list:
        tag = item["type"]
        if tag in INTERFACE_OR_PORT_TAGS:
            if (tag, item["short_name"]) in added_type_name:
                severity_counts["LOW"] += 1
                if len(severity_examples["LOW"]) < 5:
                    severity_examples["LOW"].append(f"Interface/port moved: {item['short_name']}")
            else:
                severity_counts["HIGH"] += 1
                if len(severity_examples["HIGH"]) < 5:
                    severity_examples["HIGH"].append(f"Interface/port removed: {item['short_name']}")
        else:
            severity_counts["LOW"] += 1

    for item in renamed_list:
        if item["type"] in INTERFACE_OR_PORT_TAGS:
            severity_counts["MEDIUM"] += 1
            if len(severity_examples["MEDIUM"]) < 5:
                severity_examples["MEDIUM"].append(
                    f"Interface/port renamed: {item['short_name_a']} -> {item['short_name_b']}"
                )
        else:
            severity_counts["LOW"] += 1

    for item in added_list:
        if item["type"] in INTERFACE_OR_PORT_TAGS:
            if (item["type"], item["short_name"]) not in {
                (r["type"], r["short_name"]) for r in removed_list
            }:
                severity_counts["LOW"] += 1
        else:
            severity_counts["LOW"] += 1

    for item in modified_list:
        if item["type"] in INTERFACE_OR_PORT_TAGS:
            severity_counts["MEDIUM"] += 1
            if len(severity_examples["MEDIUM"]) < 8:
                severity_examples["MEDIUM"].append(
                    f"Interface/port modified: {item['short_name']} ({item.get('summary', '')})"
                )
        else:
            severity_counts["LOW"] += 1

    result["severity_stats"] = {
        "counts": severity_counts,
        "examples": severity_examples,
    }

    # Connector maps: port short name -> connector count (once per file)
    connector_map_a = _build_connector_map(root_a)
    connector_map_b = _build_connector_map(root_b)

    # Impact propagation: interface -> signals, port -> interface (per file)
    interface_signals_a = _build_interface_signals_map(root_a)
    interface_signals_b = _build_interface_signals_map(root_b)
    port_to_interface_a = _build_port_to_interface_map(root_a)
    port_to_interface_b = _build_port_to_interface_map(root_b)

    # Dependency impact: for each changed port/interface, list affected component paths and SWC names
    dep_a = _build_dependency_map(index_a)
    dep_b = _build_dependency_map(index_b)
    dependency_impact: list[dict[str, Any]] = []
    for item in removed_list:
        if item["type"] in INTERFACE_OR_PORT_TAGS:
            affected = dep_a.get(item["short_name"], [])[:10]
            rte_mappings = {"file_a": connector_map_a.get(item["short_name"], 0), "file_b": 0}
            total_conn = (rte_mappings.get("file_a") or 0) + (rte_mappings.get("file_b") or 0)
            sigs, ifaces = _get_affected_signals_and_interfaces(
                item["type"], item["short_name"],
                interface_signals_a, port_to_interface_a,
            )
            swc_names = _affected_components_to_swc_names(affected, index_a)
            entry = {
                "element": item["short_name"],
                "change": "removed",
                "affected_components": affected,
                "affected_swc_names": swc_names,
                "rte_mappings": rte_mappings,
                "impact_severity": _classify_impact_severity(rte_mappings),
                "affected_signals": sigs,
                "affected_interfaces": ifaces,
                "connector_summary": f"{total_conn} assembly connector{'s' if total_conn != 1 else ''}",
                "impact_score": _impact_score(total_conn, len(swc_names), 1),
            }
            dependency_impact.append(entry)
    for item in added_list:
        if item["type"] in INTERFACE_OR_PORT_TAGS:
            affected = dep_b.get(item["short_name"], [])[:10]
            rte_mappings = {"file_a": 0, "file_b": connector_map_b.get(item["short_name"], 0)}
            total_conn = (rte_mappings.get("file_a") or 0) + (rte_mappings.get("file_b") or 0)
            sigs, ifaces = _get_affected_signals_and_interfaces(
                item["type"], item["short_name"],
                interface_signals_b, port_to_interface_b,
            )
            swc_names = _affected_components_to_swc_names(affected, index_b)
            entry = {
                "element": item["short_name"],
                "change": "added",
                "affected_components": affected,
                "affected_swc_names": swc_names,
                "rte_mappings": rte_mappings,
                "impact_severity": _classify_impact_severity(rte_mappings),
                "affected_signals": sigs,
                "affected_interfaces": ifaces,
                "connector_summary": f"{total_conn} assembly connector{'s' if total_conn != 1 else ''}",
                "impact_score": _impact_score(total_conn, len(swc_names), 1),
            }
            dependency_impact.append(entry)
    for item in renamed_list:
        if item["type"] in INTERFACE_OR_PORT_TAGS:
            affected_a = dep_a.get(item["short_name_a"], [])
            affected_b = dep_b.get(item["short_name_b"], [])
            affected_merged = list(dict.fromkeys(affected_a + affected_b))[:10]
            rte_mappings = {
                "file_a": connector_map_a.get(item["short_name_a"], 0),
                "file_b": connector_map_b.get(item["short_name_b"], 0),
            }
            total_conn = (rte_mappings.get("file_a") or 0) + (rte_mappings.get("file_b") or 0)
            swc_names_a = _affected_components_to_swc_names(affected_a, index_a)
            swc_names_b = _affected_components_to_swc_names(affected_b, index_b)
            affected_swc_names = list(dict.fromkeys(swc_names_a + swc_names_b))
            sigs_a, ifaces_a = _get_affected_signals_and_interfaces(
                item["type"], item["short_name_a"],
                interface_signals_a, port_to_interface_a,
            )
            sigs_b, ifaces_b = _get_affected_signals_and_interfaces(
                item["type"], item["short_name_b"],
                interface_signals_b, port_to_interface_b,
            )
            affected_signals = list(dict.fromkeys(sigs_a + sigs_b))
            affected_interfaces = list(dict.fromkeys(ifaces_a + ifaces_b))
            entry = {
                "element": f"{item['short_name_a']} -> {item['short_name_b']}",
                "change": "renamed",
                "affected_components": affected_merged,
                "affected_swc_names": affected_swc_names,
                "rte_mappings": rte_mappings,
                "impact_severity": _classify_impact_severity(rte_mappings),
                "affected_signals": affected_signals,
                "affected_interfaces": affected_interfaces,
                "connector_summary": f"{total_conn} assembly connector{'s' if total_conn != 1 else ''}",
                "impact_score": _impact_score(total_conn, len(affected_swc_names), max(1, len(affected_interfaces))),
            }
            dependency_impact.append(entry)
    result["dependency_impact"] = dependency_impact

    # Summary counts + basic impact-style numbers
    total_changes = (
        len(added_list) + len(removed_list) + len(modified_list) + len(renamed_list)
        + len(meta_added) + len(meta_removed)
    )
    # Interfaces/data_model/architecture totals
    # Per-category totals (used in summary + impact counts)
    iface_total = sum(
        len(changes_by_cat["interfaces"][k]) for k in ("added", "removed", "modified", "renamed")
    )
    data_total = sum(
        len(changes_by_cat["data_model"][k]) for k in ("added", "removed", "modified", "renamed")
    )
    arch_total = sum(
        len(changes_by_cat["architecture"][k]) for k in ("added", "removed", "modified", "renamed")
    )
    meta_total = sum(
        len(changes_by_cat["metadata"][k]) for k in ("added", "removed", "modified", "renamed")
    )
    sig_total = sum(
        len(changes_by_cat["signals"][k]) for k in ("added", "removed", "modified", "renamed")
    )

    # Impact-style counts
    interfaces_changed = iface_total
    # Signal counts from grouped diff so they match displayed lists (VARIABLE-DATA-PROTOTYPE = signal-level)
    signals_added = sum(
        len(g.get("short_names", []))
        for g in grouped["added"]
        if g.get("type") == "VARIABLE-DATA-PROTOTYPE"
    )
    signals_removed = sum(
        len(g.get("short_names", []))
        for g in grouped["removed"]
        if g.get("type") == "VARIABLE-DATA-PROTOTYPE"
    )
    packages_renamed = sum(
        1 for item in result["hierarchy_diff"]["renamed"] if item["type"] == "AR-PACKAGE"
    )

    result["summary_counts"] = {
        "total": total_changes,
        "architecture": arch_total,
        "interfaces": interfaces_changed,
        "data_model": data_total,
        "signals": sig_total,
        "metadata": meta_total,
        "signals_added": signals_added,
        "signals_removed": signals_removed,
        "packages_renamed": packages_renamed,
    }

    # Summary line
    total_a = sum(result["counts_a"].values())
    total_b = sum(result["counts_b"].values())
    # Ports: keep raw counts, but net effect may ignore pure renames (computed later for badges/LLM)
    result["summary"] = (
        f"Comparison: {name_a} vs {name_b}. "
        f"Elements: {total_a} vs {total_b}. "
        f"Ports: {result['port_diff']['count_a']} vs {result['port_diff']['count_b']}. "
        f"SWCs: {result['swc_diff']['count_a']} vs {result['swc_diff']['count_b']}. "
        f"UUIDs: {result['uuid_diff']['count_a']} vs {result['uuid_diff']['count_b']}."
    )
    return result


def format_comparison_for_report(result_dict: dict[str, Any], name_a: str, name_b: str) -> str:
    """
    Serialize the comparison result into a single structured text for LLM consumption.
    Used by Layer 2 (optional engineering report). No LLM here; validators stay deterministic.
    """
    if result_dict.get("error"):
        return f"Error: {result_dict['error']}"
    h = result_dict.get("hierarchy_diff") or {}
    hg = result_dict.get("hierarchy_diff_grouped") or {}
    num_added = len(h.get("added") or [])
    num_removed = len(h.get("removed") or [])
    num_modified = len(h.get("modified") or [])
    num_renamed = len(h.get("renamed") or [])
    sc = result_dict.get("summary_counts") or {}
    port_d = result_dict.get("port_diff", {})
    swc_d = result_dict.get("swc_diff", {})
    total_a = sum((result_dict.get("counts_a") or {}).values())
    total_b = sum((result_dict.get("counts_b") or {}).values())
    total_changes = sc.get("total", num_added + num_removed + num_modified + num_renamed)
    # Port rename-aware delta (if all increase is just renames, treat net as 0 for summary)
    ports_a_raw = port_d.get("count_a", 0)
    ports_b_raw = port_d.get("count_b", 0)
    ports_renamed = port_d.get("renamed_count", 0)
    ports_delta_raw = ports_b_raw - ports_a_raw
    if ports_renamed and ports_delta_raw == ports_renamed:
        ports_b_effective = ports_a_raw
    else:
        ports_b_effective = ports_b_raw
    lines: list[str] = [
        f"Structural comparison: {name_a} (File A) vs {name_b} (File B).",
        "",
        "FACTUAL SUMMARY (use these numbers; do not contradict):",
        f"- Total changes: {total_changes}. Architecture: {sc.get('architecture', 0)}, Interfaces: {sc.get('interfaces', 0)}, Data model: {sc.get('data_model', 0)}, Signals/Data: {sc.get('signals', 0)}, Metadata: {sc.get('metadata', 0)}.",
        f"- Added in File B: {num_added}. Removed from File A: {num_removed}. Modified: {num_modified}. Renamed: {num_renamed}.",
        f"- Total XML nodes: {total_a} (A) vs {total_b} (B). Functional AUTOSAR elements (architecture + interfaces + data model) changed: {total_changes}.",
        f"- Ports: {ports_a_raw} (A) vs {ports_b_effective} (B). "
        f"(raw B count = {ports_b_raw}, port renames = {ports_renamed}). "
        f"SWCs: {swc_d.get('count_a', 0)} (A) vs {swc_d.get('count_b', 0)} (B).",
        "- Note: Added/Removed/Modified/Renamed refer to hierarchy elements. Renamed = same-type element with similar name (e.g. suffix change). "
        "Ports: if all increase is explained by renames, the effective B count is kept equal to A.",
        "",
        "IMPACT COUNTS (derived from deterministic diff):",
        f"- Interfaces changed: {sc.get('interfaces', 0)}.",
        f"- Data/Signal elements added: {sc.get('signals_added', 0)}; removed: {sc.get('signals_removed', 0)}.",
        f"- Packages renamed: {sc.get('packages_renamed', 0)}.",
        "",
        "SEVERITY (use for Risk Analysis; do not mark renamed/moved as HIGH):",
    ]
    sev = result_dict.get("severity_stats") or {}
    for level in ("HIGH", "MEDIUM", "LOW"):
        cnt = (sev.get("counts") or {}).get(level, 0)
        ex = (sev.get("examples") or {}).get(level, [])
        if cnt:
            lines.append(f"- Severity {level}: {cnt} item(s). Examples: {'; '.join(ex[:3])}")
    lines.extend([
        "- Rule: Removed interface/port = HIGH. Renamed interface/port = MEDIUM. Moved interface/port (same name, different path) = LOW.",
        "",
        "DEPENDENCY IMPACT (affected components for changed ports/interfaces; use only these names):",
    ])
    for di in (result_dict.get("dependency_impact") or [])[:30]:
        el = di.get("element", "")
        ch = di.get("change", "")
        comps = di.get("affected_components", [])
        comp_str = ", ".join(comps[:5]) if comps else "(none)"
        lines.append(f"- {el} [{ch}] affects: {comp_str}")
    if not result_dict.get("dependency_impact"):
        lines.append("(none)")
    lines.extend([
        "",
        "--- Tags / Ports / SWCs only in File B (informational) ---",
    ])
    only_b = result_dict.get("only_in_b", [])
    if only_b:
        lines.append("Tags: " + ", ".join(only_b))
    port_b = result_dict.get("port_diff", {}).get("only_in_b", [])
    if port_b:
        lines.append("Ports: " + ", ".join(port_b[:30]) + (" ..." if len(port_b) > 30 else ""))
    swc_b = result_dict.get("swc_diff", {}).get("only_in_b", [])
    if swc_b:
        lines.append("SWCs: " + ", ".join(swc_b[:30]) + (" ..." if len(swc_b) > 30 else ""))
    if not only_b and not port_b and not swc_b:
        lines.append("(none)")
    lines.extend(["", "--- Tags / Ports / SWCs only in File A (informational) ---"])
    only_a = result_dict.get("only_in_a", [])
    if only_a:
        lines.append("Tags: " + ", ".join(only_a))
    port_a = result_dict.get("port_diff", {}).get("only_in_a", [])
    if port_a:
        lines.append("Ports: " + ", ".join(port_a[:30]) + (" ..." if len(port_a) > 30 else ""))
    swc_a = result_dict.get("swc_diff", {}).get("only_in_a", [])
    if swc_a:
        lines.append("SWCs: " + ", ".join(swc_a[:30]) + (" ..." if len(swc_a) > 30 else ""))
    if not only_a and not port_a and not swc_a:
        lines.append("(none)")
    lines.extend(["", "--- Count differences ---"])
    counts_a = result_dict.get("counts_a", {})
    counts_b = result_dict.get("counts_b", {})
    total_a = sum(counts_a.values())
    total_b = sum(counts_b.values())
    uuid_d = result_dict.get("uuid_diff", {})
    lines.append(f"Total XML nodes: {total_a} (A) vs {total_b} (B)")
    lines.append(
        f"Ports: {ports_a_raw} (A) vs {ports_b_effective} (B) "
        f"(raw B={ports_b_raw}, renames={ports_renamed})"
    )
    lines.append(f"SWCs: {swc_d.get('count_a', 0)} (A) vs {swc_d.get('count_b', 0)} (B)")
    lines.append(
        f"UUIDs: {uuid_d.get('count_a', 0)} (A) vs {uuid_d.get('count_b', 0)} (B); "
        f"common: {uuid_d.get('common', 0)}; only in A: {uuid_d.get('only_in_a', 0)}; only in B: {uuid_d.get('only_in_b', 0)}"
    )
    # Hierarchy diff (grouped to reduce noise; parents with leaf short-names)
    lines.extend(["", "--- Hierarchy diff (grouped, compact) ---"])
    # Added / Removed grouped
    lines.append("Added (in File B):")
    for g in (hg.get("added") or [])[:MAX_HIERARCHY_ENTRIES]:
        lines.append(
            f"  {g.get('parent', '')}  [{g.get('type', '')}] added: "
            + ", ".join(g.get("short_names", []))
        )
    if not hg.get("added"):
        lines.append("  (none)")
    lines.append("")
    lines.append("Removed (from File A):")
    for g in (hg.get("removed") or [])[:MAX_HIERARCHY_ENTRIES]:
        lines.append(
            f"  {g.get('parent', '')}  [{g.get('type', '')}] removed: "
            + ", ".join(g.get("short_names", []))
        )
    if not hg.get("removed"):
        lines.append("  (none)")
    lines.append("")
    lines.append("Modified:")
    for g in (hg.get("modified") or [])[:MAX_HIERARCHY_ENTRIES]:
        parent = g.get("parent", "")
        tag = g.get("type", "")
        items = g.get("items", [])
        summaries = ", ".join(
            f"{it.get('short_name', '')} ({it.get('summary', '')})" for it in items
        )
        lines.append(f"  {parent}  [{tag}] modified: {summaries}")
    if not hg.get("modified"):
        lines.append("  (none)")
    lines.append("")
    lines.append("Renamed:")
    for g in (hg.get("renamed") or [])[:MAX_HIERARCHY_ENTRIES]:
        parent_b = g.get("parent_b", "")
        tag = g.get("type", "")
        pairs = g.get("pairs", [])
        renames = ", ".join(
            f"{p.get('from', '')} -> {p.get('to', '')}" for p in pairs
        )
        lines.append(f"  {parent_b}  [{tag}] renamed: {renames}")
    if not hg.get("renamed"):
        lines.append("  (none)")

    # Grouped by category for enterprise report (still provided for LLM)
    by_cat = result_dict.get("changes_by_category") or {}
    lines.extend(["", "--- Changes by category ---"])
    for cat in CATEGORY_ORDER:
        cat_data = by_cat.get(cat, {})
        a_list = cat_data.get("added", [])
        r_list = cat_data.get("removed", [])
        m_list = cat_data.get("modified", [])
        rn_list = cat_data.get("renamed", [])
        if not (a_list or r_list or m_list or rn_list):
            continue
        lines.append(f"### {cat.replace('_', ' ').title()}")
        for item in a_list[:30]:
            if "path" in item:
                lines.append(f"  + {item.get('path', '')}  [{item.get('type', '')}] {item.get('short_name', '')}")
            else:
                lines.append(f"  + tag: {item.get('tag', '')}")
        for item in r_list[:30]:
            if "path" in item:
                lines.append(f"  - {item.get('path', '')}  [{item.get('type', '')}] {item.get('short_name', '')}")
            else:
                lines.append(f"  - tag: {item.get('tag', '')}")
        for item in m_list[:30]:
            lines.append(f"  ~ {item.get('path', '')}  [{item.get('type', '')}] {item.get('short_name', '')}  ({item.get('summary', '')})")
        for item in rn_list[:30]:
            lines.append(f"  -> {item.get('short_name_a', '')} -> {item.get('short_name_b', '')}  [{item.get('type', '')}]")
        if len(a_list) > 30 or len(r_list) > 30 or len(m_list) > 30 or len(rn_list) > 30:
            lines.append("  ... and more")
        lines.append("")
    return "\n".join(lines)
