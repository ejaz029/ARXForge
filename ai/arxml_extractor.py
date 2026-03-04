import xml.etree.ElementTree as ET


def _local_tag(elem):
    """Return local tag name without namespace."""
    if elem is None or not elem.tag:
        return ""
    return elem.tag.split("}", 1)[1] if "}" in elem.tag else elem.tag


def _child_text(elem, local_name, default=""):
    """Get text of first child with given local tag name (any namespace)."""
    if elem is None:
        return default
    for child in elem:
        if _local_tag(child) == local_name and child.text:
            return child.text.strip()
    return default


def _child_ref(elem, local_name, default=""):
    """Get text of first descendant with given local tag name (any namespace)."""
    if elem is None:
        return default
    for child in elem.iter():
        if _local_tag(child) == local_name and child.text:
            return child.text.strip()
    return default


def extract_arxml_data(file_path):
    """
    Extracts relevant data from an ARXML file for AI-based validation.
    Uses local-tag matching so namespaced AUTOSAR ARXML is supported.
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        ns = {"ns": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}

        extracted_data = {
            "swc_components": [],
            "ports": [],
            "pdus": [],
            "signals": [],
            "diagnostics": [],
            "base_types": [],
            "implementation_data_types": []
        }

        for elem in root.iter():
            tag = _local_tag(elem)
            if tag == "APPLICATION-SOFTWARE-COMPONENT-TYPE":
                name = _child_text(elem, "SHORT-NAME")
                if name:
                    extracted_data["swc_components"].append(f"{name} [Application]")
            elif tag == "COMPOSITION-SW-COMPONENT-TYPE":
                name = _child_text(elem, "SHORT-NAME")
                if name:
                    extracted_data["swc_components"].append(f"{name} [Composition]")
            elif tag == "COMPONENT-PROTOTYPE":
                name = _child_text(elem, "SHORT-NAME")
                if name:
                    extracted_data["swc_components"].append(f"{name} [Prototype]")
            elif tag == "P-PORT-PROTOTYPE":
                interface_elem = (
                    elem.find("ns:PROVIDED-INTERFACE-TREF", ns) if ns
                    else elem.find("{*}PROVIDED-INTERFACE-TREF") or elem.find("PROVIDED-INTERFACE-TREF")
                )
                interface_text = interface_elem.text if interface_elem is not None else ""
                extracted_data["ports"].append({
                    "name": _child_text(elem, "SHORT-NAME"),
                    "interface": interface_text.strip() if interface_text else "",
                    "data_type": ""
                })
            elif tag == "R-PORT-PROTOTYPE":
                interface_elem = (
                    elem.find("ns:REQUIRED-INTERFACE-TREF", ns) if ns
                    else elem.find("{*}REQUIRED-INTERFACE-TREF") or elem.find("REQUIRED-INTERFACE-TREF")
                )
                interface_text = interface_elem.text if interface_elem is not None else ""
                extracted_data["ports"].append({
                    "name": _child_text(elem, "SHORT-NAME"),
                    "interface": interface_text.strip() if interface_text else "",
                    "data_type": ""
                })
            elif tag == "PORT":
                extracted_data["ports"].append({
                    "name": _child_text(elem, "SHORT-NAME"),
                    "interface": _child_text(elem, "PORT-INTERFACE"),
                    "data_type": _child_text(elem, "DATA-TYPE")
                })
            elif tag == "PDU":
                name = _child_text(elem, "SHORT-NAME")
                if name:
                    extracted_data["pdus"].append(name)
            elif tag == "SIGNAL":
                extracted_data["signals"].append({
                    "name": _child_text(elem, "SHORT-NAME"),
                    "sender": _child_text(elem, "SENDER"),
                    "receiver": _child_text(elem, "RECEIVER")
                })
            elif tag == "DEM-EVENT":
                extracted_data["diagnostics"].append({
                    "event_name": _child_text(elem, "SHORT-NAME"),
                    "dtc": _child_text(elem, "DTC-VALUE")
                })
            elif tag == "SW-BASE-TYPE":
                name = _child_text(elem, "SHORT-NAME")
                if name:
                    extracted_data["base_types"].append({
                        "name": name,
                        "category": _child_text(elem, "CATEGORY"),
                        "base_type_size": _child_text(elem, "BASE-TYPE-SIZE"),
                        "base_type_encoding": _child_text(elem, "BASE-TYPE-ENCODING"),
                        "native_declaration": _child_text(elem, "NATIVE-DECLARATION")
                    })
            elif tag == "IMPLEMENTATION-DATA-TYPE":
                name = _child_text(elem, "SHORT-NAME")
                if name:
                    base_ref = _child_ref(elem, "BASE-TYPE-REF")
                    extracted_data["implementation_data_types"].append({
                        "name": name,
                        "category": _child_text(elem, "CATEGORY"),
                        "base_type_ref": base_ref
                    })

        return extracted_data
    
    except ET.ParseError:
        return {"error": "Invalid XML format. Unable to parse ARXML file."}
    except Exception as e:
        return {"error": str(e)}

# Example Usage
if __name__ == "__main__":
    file_path = "example.arxml"
    extracted_info = extract_arxml_data(file_path)
    print(extracted_info)
