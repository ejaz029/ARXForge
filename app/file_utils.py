# import os
# import xml.etree.ElementTree as ET

# # def load_arxml_file(file_path):
# #     """Reads and parses an ARXML file."""
# #     if not os.path.exists(file_path):
# #         raise FileNotFoundError(f"⚠️ Error: File '{file_path}' not found!")
    
# #     try:
# #         tree = ET.parse(file_path)
# #         root = tree.getroot()
# #         return root
# #     except ET.ParseError as e:
# #         raise ValueError(f"⚠️ Error parsing ARXML file: {str(e)}")
# def load_arxml_file(folder_path):
#     """Loads and parses all ARXML files in the given folder."""
#     arxml_data = []
#     failed_files = []

#     for file_name in os.listdir(folder_path):
#         if file_name.endswith(".arxml"):
#             file_path = os.path.join(folder_path, file_name)
#             try:
#                 root = load_arxml_file(file_path)
#                 arxml_data.append((file_name, root))
#             except (FileNotFoundError, ValueError) as e:
#                 failed_files.append((file_name, str(e)))

#     return arxml_data, failed_files

# def extract_element_values(root, tag_name):
#     """Extracts values of all elements with a specific tag."""
#     return [elem.text for elem in root.findall(f".//{tag_name}") if elem.text]

# def validate_required_elements(root, required_tags):
#     """Checks if required tags are present in the ARXML file."""
#     missing_tags = [tag for tag in required_tags if not root.findall(f".//{tag}")]
#     return missing_tags

# def save_arxml_file(root, output_path):
#     """Saves the modified ARXML file."""
#     tree = ET.ElementTree(root)
#     tree.write(output_path, encoding="utf-8", xml_declaration=True)

import os
import xml.etree.ElementTree as ET

ARXML_EXTENSIONS = (".arxml", ".xml")

# Max upload size (bytes) for industry safety; ~50 MB
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def safe_upload_filename(filename):
    """Return a safe basename for uploads (prevents path traversal). Only .arxml allowed."""
    if not filename or not is_arxml_only(filename):
        return None
    base = os.path.basename(filename.strip())
    if not base or ".." in base or os.path.sep in base:
        return None
    return base


def is_arxml_only(filename):
    """Return True if filename ends with .arxml only (case-insensitive). Use for upload validation."""
    if not filename:
        return False
    return filename.lower().endswith(".arxml")


def is_arxml_or_xml(filename):
    """Return True if filename ends with .arxml or .xml (case-insensitive)."""
    if not filename:
        return False
    lower = filename.lower()
    return lower.endswith(".arxml") or lower.endswith(".xml")


def load_arxml_file(file_path):
    """Reads and parses a single ARXML file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"⚠️ Error: File '{file_path}' not found!")

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        return root
    except ET.ParseError as e:
        raise ValueError(f"⚠️ Error parsing ARXML file: {str(e)}")

def load_arxml_folder(folder_path):
    """Loads and parses all ARXML files in the given folder."""
    arxml_data = []
    failed_files = []

    for file_name in os.listdir(folder_path):
        if is_arxml_only(file_name):
            file_path = os.path.join(folder_path, file_name)
            try:
                root = load_arxml_file(file_path)
                arxml_data.append((file_name, root))
            except (FileNotFoundError, ValueError) as e:
                failed_files.append((file_name, str(e)))

    return arxml_data, failed_files

def extract_element_values(root, tag_name):
    return [elem.text for elem in root.findall(f".//{tag_name}") if elem.text]

def validate_required_elements(root, required_tags):
    missing_tags = [tag for tag in required_tags if not root.findall(f".//{tag}")]
    return missing_tags

def save_arxml_file(root, output_path):
    tree = ET.ElementTree(root)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
