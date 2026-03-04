# from langchain_community.embeddings import HuggingFaceEmbeddings
# from langchain_community.vectorstores import FAISS
# from langchain_community.document_loaders import TextLoader
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain.chains import RetrievalQA

# # ✅ Import only get_llm from the correct config
# from config.llm_config import get_llm

# import xml.etree.ElementTree as ET

# class RAGValidator:
#     def __init__(self, arxml_path):
#         self.arxml_path = arxml_path
#         self.vector_db = None
#         self.qa_chain = None

#     def load_arxml(self):
#         try:
#             tree = ET.parse(self.arxml_path)
#             root = tree.getroot()
#             return ET.tostring(root, encoding="utf-8").decode()
#         except Exception as e:
#             return f"⚠️ Error parsing ARXML: {str(e)}"

#     def build_vector_db(self, arxml_text):
#         text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
#         docs = text_splitter.split_text(arxml_text)

#         embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
#         self.vector_db = FAISS.from_texts(docs, embeddings)

#     def setup_rag_pipeline(self):
#         retriever = self.vector_db.as_retriever()
#         llm = get_llm()  # ✅ Correct LLM getter
#         self.qa_chain = RetrievalQA.from_chain_type(llm, retriever=retriever)

#     def validate_arxml(self):
#         arxml_text = self.load_arxml()
#         if "Error" in arxml_text:
#             return arxml_text

#         self.build_vector_db(arxml_text)
#         self.setup_rag_pipeline()

#         prompt = (
#             "Analyze this ARXML data for inconsistencies, missing elements, UUID uniqueness issues, "
#             "and any potential errors based on AUTOSAR standards. Provide a structured response."
#         )
#         return self.qa_chain.run(prompt)




# import os
# import re
# import xml.etree.ElementTree as ET
# from langchain_community.embeddings import HuggingFaceEmbeddings
# from langchain_community.vectorstores import FAISS
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain.chains import RetrievalQA
# from config.llm_config import get_llm
# from validators.extract_ports import extract_ports_from_arxml

# def find_file_from_query(user_query, file_list):
#     """Try to extract a filename (like 'G') from the query and match it with actual file names."""
#     for file in file_list:
#         base = file.lower().replace(".arxml", "")
#         if base in user_query.lower() or f"{base}.arxml" in user_query.lower():
#             return file
#     return None

# def check_duplicate_uuids(arxml_data):
#     """Scan across all files for duplicate UUIDs."""
#     uuid_map = {}
#     duplicates = []

#     for filename, xml_str in arxml_data.items():
#         try:
#             root = ET.fromstring(xml_str)
#             for elem in root.iter():
#                 uuid = elem.attrib.get("UUID")
#                 if uuid:
#                     if uuid in uuid_map:
#                         duplicates.append((uuid, uuid_map[uuid], filename))
#                     else:
#                         uuid_map[uuid] = filename
#         except Exception:
#             continue

#     return duplicates

# def process_query_with_rag(user_query, upload_folder):
#     try:
#         # ✅ Step 1: Load ARXML files
#         arxml_data = {}
#         loaded_files = []

#         for f in os.listdir(upload_folder):
#             if f.endswith(".arxml"):
#                 try:
#                     file_path = os.path.join(upload_folder, f)
#                     tree = ET.parse(file_path)
#                     root = tree.getroot()
#                     xml_str = ET.tostring(root, encoding="utf-8").decode()
#                     arxml_data[f] = xml_str
#                     loaded_files.append(f)
#                 except Exception as e:
#                     arxml_data[f] = f"⚠️ Failed to parse {f}: {e}"

#         if not arxml_data:
#             return "❌ No ARXML files found to analyze."

#         # ✅ Step 2: Detect if specific file is mentioned
#         target_file = find_file_from_query(user_query, loaded_files)

#         # ✅ Step 3: Handle custom port report (works for any mentioned file)
#         if "report of all ports" in user_query.lower() and target_file:
#             file_path = os.path.join(upload_folder, target_file)
#             if not os.path.exists(file_path):
#                 return f"❌ {target_file} not found in uploads folder."

#             ports = extract_ports_from_arxml(file_path)
#             if not ports or "error" in ports[0]:
#                 return f"❌ Error extracting ports: {ports[0].get('error', 'Unknown issue')}"

#             p_ports = [p for p in ports if p['port_type'] == "P-PORT"]
#             r_ports = [p for p in ports if p['port_type'] == "R-PORT"]

#             report_lines = [
#                 f"📄 {target_file} – Port Summary Report:\n",
#                 f"🔷 Total Ports Found: {len(ports)}",
#                 f"   🔹 P-PORTs: {len(p_ports)}",
#                 f"   🔹 R-PORTs: {len(r_ports)}\n",
#                 f"🔌 P-PORTs (Provided Interfaces):"
#             ]

#             for i, p in enumerate(p_ports, 1):
#                 report_lines.append(f"{i}. Name: {p['name']}\n   Interface: {p['interface']}")

#             report_lines.append(f"\n🔌 R-PORTs (Required Interfaces):")
#             for i, p in enumerate(r_ports, 1):
#                 report_lines.append(f"{i}. Name: {p['name']}\n   Interface: {p['interface']}")

#             return "\n".join(report_lines)

#         # ✅ Step 4: Handle UUID duplication queries
#         if "duplicate uuid" in user_query.lower():
#             duplicates = check_duplicate_uuids(arxml_data)

#             if not duplicates:
#                 return f"📂 Files Loaded: {', '.join(loaded_files)}\n\n✅ No duplicate UUIDs found across files."

#             dup_text = "\n".join(
#                 [f"❌ Duplicate UUID '{uuid}' found in both '{f1}' and '{f2}'." for uuid, f1, f2 in duplicates]
#             )
#             return f"📂 Files Loaded: {', '.join(loaded_files)}\n\n📊 {dup_text}"
        
#         # ✅ Step 5: Prepare documents for RAG (Exclude failed files)
#         if target_file:
#             context_text = arxml_data.get(target_file, "")
#             if context_text.startswith("⚠️"):
#                 return f"❌ Cannot process {target_file}: {context_text}"
#             arxml_texts = [f"--- {target_file} ---\n{context_text}"]
#         else:
#             # Only include files that did not fail parsing
#             arxml_texts = [
#                 f"--- {f} ---\n{txt}" 
#                 for f, txt in arxml_data.items() 
#                 if not txt.startswith("⚠️")
#             ]
            

#         if not arxml_texts:
#             return "❌ All ARXML files failed to parse. Cannot continue."

#         combined_text = "\n\n".join(arxml_texts)


#         # if target_file:
#         #     context_text = arxml_data[target_file]
#         #     arxml_texts = [f"--- {target_file} ---\n{context_text}"]
#         # else:
#         #     arxml_texts = [f"--- {f} ---\n{txt}" for f, txt in arxml_data.items()]

#         # combined_text = "\n\n".join(arxml_texts)

#         text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
#         docs = text_splitter.split_text(combined_text)

#         embeddings = HuggingFaceEmbeddings(
#             model_name="sentence-transformers/all-MiniLM-L6-v2",
#             model_kwargs={"device": "cpu"}  # ⛔ Avoid CUDA meta tensor error
#         )
#         vector_db = FAISS.from_texts(docs, embeddings)
#         retriever = vector_db.as_retriever()

#         # ✅ Step 6: Run LLM Retrieval Q&A
#         llm = get_llm()
#         qa_chain = RetrievalQA.from_chain_type(llm, retriever=retriever)

#         prompt = (
#             f"The user wants to compare ARXML files: {', '.join(loaded_files)}.\n\n"
#             f"Query: {user_query}"
#         )

#         result = qa_chain.run(prompt)
#         return f"📂 Files Loaded: {', '.join(loaded_files)}\n\n📊 Answer: {result}"

#     except Exception as e:
#         return f"❌ Error during RAG validation: {e}"

# # Optional CLI test
# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) < 3:
#         print("Usage: python ai\\rag_validation.py <upload_folder> <query>")
#     else:
#         upload_folder = sys.argv[1]
#         user_query = " ".join(sys.argv[2:])
#         result = process_query_with_rag(user_query, upload_folder)
#         print(result)


import os
import json
import time
import re
import warnings
import logging
import xml.etree.ElementTree as ET

# Suppress TensorFlow logging
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger('tensorflow').setLevel(logging.ERROR)
logging.getLogger('tf_keras').setLevel(logging.ERROR)

# Suppress deprecation warnings for HuggingFaceEmbeddings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="tensorflow")
warnings.filterwarnings("ignore", message=".*tf.losses.*deprecated.*")
warnings.filterwarnings("ignore", message=".*sparse_softmax_cross_entropy.*deprecated.*")

# Use langchain_huggingface for HuggingFaceEmbeddings (non-deprecated)
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    # Suppress the deprecation warning if it still appears
    warnings.filterwarnings("ignore", message=".*HuggingFaceEmbeddings.*deprecated.*")
except ImportError:
    # Fallback for older versions
    from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from config.llm_config import get_llm
from config.device_utils import get_device, get_device_name
from validators.extract_ports import extract_ports_from_arxml
from ai.arxml_extractor import extract_arxml_data
from app.file_utils import is_arxml_only


def _file_base(name):
    """Strip .arxml or .xml for matching and display."""
    if not name:
        return ""
    n = name.lower()
    if n.endswith(".arxml"):
        return n[:-6]
    if n.endswith(".xml"):
        return n[:-4]
    return n


def find_file_from_query(user_query, file_list):
    q = (user_query or "").lower()
    for file in file_list:
        base = _file_base(file)
        if not base:
            continue
        if base in q or f"{base}.arxml" in q or f"{base}.xml" in q:
            return file
    return None

def check_duplicate_uuids(arxml_data):
    uuid_map = {}
    duplicates = []
    for filename, xml_str in arxml_data.items():
        try:
            root = ET.fromstring(xml_str)
            for elem in root.iter():
                uuid = elem.attrib.get("UUID")
                if uuid:
                    if uuid in uuid_map:
                        duplicates.append((uuid, uuid_map[uuid], filename))
                    else:
                        uuid_map[uuid] = filename
        except Exception:
            continue
    return duplicates

def _is_complex_query(user_query: str) -> bool:
    """
    Determines if a query requires agent capabilities (multi-step, complex validation).
    Uses intent routing to make the decision.
    
    Args:
        user_query: User's query string
        
    Returns:
        True if query should use agent, False for simple RAG
    """
    try:
        from ai.intent_router import classify_intent, should_use_rag
        
        intent = classify_intent(user_query)
        # Use agent for extraction, validation, analysis, comparison
        # Use RAG for questions and unknown intents
        use_rag = should_use_rag(intent)
        return not use_rag  # Agent if not using RAG
    except Exception:
        # Fallback to original logic when intent_router fails
        query_lower = user_query.lower()
        complex_keywords = [
            "validate all", "run all checks", "comprehensive",
            "complete analysis", "full validation", "check everything",
            "analyze and validate", "multi-step", "compare", "difference between",
            "critical", "issues", "problems", "what's wrong"
        ]
        if any(keyword in query_lower for keyword in complex_keywords):
            return True
        validation_count = sum([
            "validate" in query_lower, "check" in query_lower,
            "analyze" in query_lower, "extract" in query_lower
        ])
        return validation_count >= 2 or query_lower.count("and") >= 2


def _load_arxml_context(upload_folder, selected_file, user_query):
    """Load ARXML files and resolve target_file. Returns (arxml_data, loaded_files, target_file) or (None, None, None) on error with error message as first element."""
    if not os.path.exists(upload_folder):
        return (f"❌ Upload folder '{upload_folder}' does not exist.", None, None)
    if not os.path.isdir(upload_folder):
        return (f"❌ '{upload_folder}' is not a valid directory.", None, None)
    arxml_data = {}
    loaded_files = []
    try:
        files = os.listdir(upload_folder)
    except PermissionError:
        return ("❌ Permission denied: Cannot access '{upload_folder}'.", None, None)
    except Exception as e:
        return (f"❌ Error accessing folder: {str(e)}", None, None)
    for f in files:
        if is_arxml_only(f):
            try:
                file_path = os.path.join(upload_folder, f)
                tree = ET.parse(file_path)
                root = tree.getroot()
                xml_str = ET.tostring(root, encoding="utf-8").decode()
                arxml_data[f] = xml_str
                loaded_files.append(f)
            except ET.ParseError as e:
                arxml_data[f] = f"⚠️ Failed to parse {f}: XML parsing error - {str(e)}"
            except Exception as e:
                arxml_data[f] = f"⚠️ Failed to parse {f}: {str(e)}"
    if not arxml_data:
        return ("❌ No ARXML files found to analyze.", None, None)
    if selected_file:
        target_file = None
        for f in loaded_files:
            if f == selected_file or f.lower() == selected_file.lower():
                target_file = f
                break
        if not target_file:
            target_file = selected_file
    else:
        target_file = find_file_from_query(user_query, loaded_files)
    return (arxml_data, loaded_files, target_file)


def _run_rag_qa(user_query, arxml_data, loaded_files, target_file):
    """Run RAG-based QA over loaded ARXML context. Used by process_rag_only."""
    if target_file:
        context_text = arxml_data.get(target_file, "")
        if context_text.startswith("⚠️"):
            return f"❌ Cannot process {target_file}: {context_text}"
        arxml_texts = [f"--- {target_file} ---\n{context_text}"]
    else:
        arxml_texts = [
            f"--- {f} ---\n{txt}"
            for f, txt in arxml_data.items()
            if not txt.startswith("⚠️")
        ]
    if not arxml_texts:
        return "❌ All ARXML files failed to parse. Cannot continue."
    combined_text = "\n\n".join(arxml_texts)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.split_text(combined_text)
    if not docs:
        return "❌ No valid text content extracted from ARXML files."
    try:
        device = get_device()
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": device}
        )
        vector_db = FAISS.from_texts(docs, embeddings)
        retriever = vector_db.as_retriever()
        llm = get_llm()
        qa_chain = RetrievalQA.from_chain_type(llm, retriever=retriever)
        if target_file:
            other_files = [f for f in loaded_files if f != target_file]
            prompt = (
                f"Context: You are analyzing a SINGLE ARXML file named '{target_file}'.\n\n"
                f"CRITICAL INSTRUCTIONS:\n"
                f"- ONLY analyze and respond about '{target_file}'\n"
                f"- DO NOT mention, reference, or compare with other files: {', '.join(other_files[:5])}\n"
                f"- DO NOT list multiple files\n"
                f"- If the answer is not found in '{target_file}', say so clearly\n\n"
                f"User Query: {user_query}\n\n"
                f"Remember: Only answer about '{target_file}'."
            )
        else:
            prompt = (
                f"The user wants to compare ARXML files: {', '.join(loaded_files)}.\n\n"
                f"Query: {user_query}"
            )
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*Chain.run.*deprecated.*")
            warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain.chains")
            result = qa_chain.invoke({"query": prompt})
        answer = result.get("result", str(result)) if isinstance(result, dict) else str(result)
        if target_file:
            other_files = [f for f in loaded_files if f != target_file]
            for other_file in other_files:
                base = _file_base(other_file)
                answer = answer.replace(other_file, "").replace(base, "")
            answer = re.sub(r'📂\s*Files\s+Loaded[^:]*:\s*[^\n]*', '', answer, flags=re.IGNORECASE)
            answer = re.sub(r'Files\s+Loaded[^:]*:\s*[^\n]*', '', answer, flags=re.IGNORECASE)
            for other_file in other_files:
                answer = re.sub(rf'\b{re.escape(other_file)}\b[,\s]*', '', answer)
            answer = " ".join(answer.split())
            return f"📄 {target_file}\n\n📊 Answer: {answer}"
        return f"📂 Files Loaded: {', '.join(loaded_files)}\n\n📊 Answer: {answer}"
    except Exception as e:
        return f"❌ Error during RAG processing: {str(e)}\n\nPlease check your GROQ_API_KEY and ensure all dependencies are installed."


def process_rag_only(user_query, upload_folder, selected_file=None):
    """
    RAG-only path: no agent branch. Used when intent is question/unknown or when
    the agent's RAG node invokes it. Loads ARXML context, optional special handlers
    for question-style requests, then RAG QA.
    """
    try:
        out = _load_arxml_context(upload_folder, selected_file, user_query)
        if isinstance(out[0], str) and out[0].startswith("❌"):
            return out[0]
        arxml_data, loaded_files, target_file = out

        # Optional special handlers for RAG path (question-style requests)
        if ("software component" in user_query.lower() or "software components" in user_query.lower()) and target_file:
            file_path = os.path.join(upload_folder, target_file)
            data = extract_arxml_data(file_path)
            if "error" in data:
                return f"❌ Error extracting software components: {data['error']}"
            components = data.get("swc_components", [])
            if components:
                return f"📄 {target_file} – Software Components:\n" + "\n".join(f"- {c}" for c in components)

        if "ecu instance" in user_query.lower() and target_file:
            file_path = os.path.join(upload_folder, target_file)
            ecu_instances = []
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                for ecu in root.findall(".//ECU-INSTANCE"):
                    name = ecu.findtext("SHORT-NAME")
                    uuid = ecu.attrib.get("UUID", "N/A")
                    ecu_instances.append((name, uuid))
            except Exception as e:
                return f"❌ Error extracting ECU instances: {str(e)}"
            if not ecu_instances:
                return f"ℹ️ No ECU instances found in {target_file}."
            return (
                f"📄 {target_file} – ECU Instances:\n" +
                "\n".join(f"- {name} (UUID: {uuid})" for name, uuid in ecu_instances)
            )

        if "report of all ports" in user_query.lower() and target_file:
            file_path = os.path.join(upload_folder, target_file)
            if not os.path.exists(file_path):
                return f"❌ {target_file} not found in uploads folder."
            ports = extract_ports_from_arxml(file_path)
            if not ports or "error" in str(ports[0]).lower():
                return f"❌ Error extracting ports: {ports[0].get('error', 'Unknown issue') if isinstance(ports[0], dict) else 'Unknown'}"
            p_ports = [p for p in ports if p.get('port_type') == "P-PORT"]
            r_ports = [p for p in ports if p.get('port_type') == "R-PORT"]
            report_lines = [
                f"📄 {target_file} – Port Summary Report:",
                f"🔷 Total Ports Found: {len(ports)}",
                f"   🔹 P-PORTs: {len(p_ports)}",
                f"   🔹 R-PORTs: {len(r_ports)}",
                "\n🔌 P-PORTs (Provided Interfaces):"
            ]
            for i, p in enumerate(p_ports, 1):
                report_lines.append(f"{i}. Name: {p['name']}\n   Interface: {p['interface']}")
            report_lines.append("\n🔌 R-PORTs (Required Interfaces):")
            for i, p in enumerate(r_ports, 1):
                report_lines.append(f"{i}. Name: {p['name']}\n   Interface: {p['interface']}")
            return "\n".join(report_lines)

        if "duplicate uuid" in user_query.lower():
            if target_file:
                xml_str = arxml_data.get(target_file, "")
                if not xml_str or xml_str.startswith("⚠️"):
                    return f"❌ Cannot process {target_file}: {xml_str if xml_str.startswith('⚠️') else 'File not found'}"
                uuid_map = {}
                duplicates = []
                try:
                    root = ET.fromstring(xml_str)
                    for elem in root.iter():
                        uuid = elem.attrib.get("UUID")
                        if uuid:
                            if uuid in uuid_map:
                                duplicates.append(uuid)
                            else:
                                uuid_map[uuid] = True
                    unique_duplicates = list(set(duplicates))
                    if not unique_duplicates:
                        return f"📄 {target_file}\n\n✅ No duplicate UUIDs found within this file."
                    dup_text = "\n".join(
                        [f"❌ Duplicate UUID '{uuid}' found multiple times in '{target_file}'." for uuid in unique_duplicates]
                    )
                    return f"📄 {target_file}\n\n📊 {dup_text}"
                except Exception as e:
                    return f"❌ Error parsing {target_file}: {str(e)}"
            else:
                dups = check_duplicate_uuids(arxml_data)
                if not dups:
                    return f"📂 Files Loaded: {', '.join(loaded_files)}\n\n✅ No duplicate UUIDs found across files."
                dup_text = "\n".join(
                    [f"❌ Duplicate UUID '{uuid}' found in both '{f1}' and '{f2}'." for uuid, f1, f2 in dups]
                )
                return f"📂 Files Loaded: {', '.join(loaded_files)}\n\n📊 {dup_text}"

        return _run_rag_qa(user_query, arxml_data, loaded_files, target_file)
    except Exception as e:
        return f"❌ Error during RAG validation: {e}"


def process_query_with_rag(user_query, upload_folder, selected_file=None):
    """
    Single entry point: agent for extraction/validation/analysis/comparison,
    RAG only for question/unknown. No duplicate branches for agent-handled intents.
    """
    try:
        use_agent = _is_complex_query(user_query)
        if use_agent:
            try:
                from ai.arxml_agent import run_agent_query
                thread_id = _file_base(selected_file) or "default"
                return run_agent_query(
                    user_query,
                    selected_file=selected_file,
                    upload_folder=upload_folder,
                    thread_id=thread_id
                )
            except ImportError:
                pass
            except Exception as e:
                logging.getLogger(__name__).warning("Agent execution failed, falling back to RAG: %s", e)
        return process_rag_only(user_query, upload_folder, selected_file)
    except Exception as e:
        return f"❌ Error during RAG validation: {e}"


def process_query_structured(user_query, upload_folder, selected_file=None):
    """
    Same as process_query_with_rag but returns a structured dict for dashboard UI.
    Returns: {"command", "plan", "tool_results", "summary", "steps", "advisory"}
    """
    command = user_query
    empty = {"command": command, "plan": [], "tool_results": [], "summary": "", "steps": [], "advisory": False}
    q = (user_query or "").strip().lower()
    if "are you able" in q or "can you" in q:
        return {
            **empty,
            "summary": "Yes — I can extract, validate, compare, and analyze ARXML files. Try: Extract ports",
            "steps": [],
            "advisory": True,
        }
    try:
        # Force agent path for "critical issues" so validators always run
        critical_issues_phrases = [
            "critical issue", "critical issues", "most critical", "issues in this file",
            "problems in this file"
        ]
        use_agent = any(phrase in q for phrase in critical_issues_phrases) or _is_complex_query(user_query)
        if use_agent:
            try:
                from ai.arxml_agent import run_agent_query_structured
                thread_id = _file_base(selected_file) or "default"
                return run_agent_query_structured(
                    user_query,
                    selected_file=selected_file,
                    upload_folder=upload_folder,
                    thread_id=thread_id,
                )
            except ImportError:
                pass
            except Exception as e:
                try:
                    from ai.intent_router import classify_intent
                    intent = classify_intent(user_query)
                except Exception:
                    intent = "unknown"
                logging.getLogger(__name__).warning(
                    "Agent execution failed, falling back to RAG; intent=%s; reason=%s",
                    intent, e
                )
        summary = process_rag_only(user_query, upload_folder, selected_file)
        return {**empty, "summary": summary, "steps": ["RAG"], "advisory": True}
    except Exception as e:
        return {**empty, "summary": f"❌ Error during RAG validation: {e}"}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python ai\\rag_validation.py <upload_folder> <query>")
    else:
        upload_folder = sys.argv[1]
        user_query = " ".join(sys.argv[2:])
        result = process_query_with_rag(user_query, upload_folder)
        print(result)
