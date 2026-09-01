from pathlib import Path
import sys
import uuid

import streamlit as st


# ============================================================
# PATHA PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

# The finalized backend modules use imports such as:
# from utils import ...
# from pif_writer import ...
#
# Therefore backend/ is added to sys.path.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ============================================================
# EXISTING BACKEND
# ============================================================

try:
    from encoder import encode_txt_to_pif
    from decoder import decode_pif_to_txt

    from storage_manager import (
        handle_upload,
        prepare_download,
        finalize_download,
        cleanup_stale_files,
    )

except Exception as exc:
    st.error("PATHA could not load the backend.")
    st.exception(exc)
    st.stop()


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="PATHA — Data Preservation & Integrity",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "encoded_data": None,
    "encoded_filename": None,
    "encoded_source": None,

    "decode_done": False,
    "decode_text": "",
    "decode_has_errors": False,
    "decode_positions": [],
    "decode_filename": None,
}

for key, default_value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = default_value


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    /* ========================================================
       COLOR SYSTEM
    ======================================================== */

    :root {
        --bg: #0F1420;
        --panel: #1A2036;
        --panel2: #202743;
        --gold: #C9A464;
        --gold-soft: #D9BF89;
        --text: #EDE6D6;
        --muted: #A5A6A2;
        --dim: #777D88;
        --success: #7A9B76;
        --error: #A63D40;
        --line: rgba(237, 230, 214, 0.10);
    }


    /* ========================================================
       GLOBAL
    ======================================================== */

    .stApp {
        background:
            radial-gradient(
                circle at 85% 8%,
                rgba(201, 164, 100, 0.055),
                transparent 31rem
            ),
            radial-gradient(
                circle at 8% 65%,
                rgba(63, 76, 116, 0.10),
                transparent 32rem
            ),
            var(--bg);
    }

    .main .block-container {
        max-width: 1180px;
        padding-top: 1.5rem;
        padding-bottom: 5rem;
    }

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    [data-testid="stHeader"] {
        background: transparent;
    }


    /* ========================================================
       TYPOGRAPHY
       ======================================================== */

    h1,
    h2,
    h3,
    h4 {
        color: var(--gold) !important;
        font-family:
            Georgia,
            "Times New Roman",
            serif !important;
    }

    h1 {
        font-size:
            clamp(3rem, 7vw, 5.4rem) !important;
        line-height: 1.02 !important;
        letter-spacing: -0.045em !important;
    }

    h2 {
        font-size:
            clamp(2.2rem, 5vw, 3.5rem) !important;
        line-height: 1.08 !important;
    }

    h3 {
        font-size: 1.35rem !important;
    }

    p,
    li {
        color: var(--muted) !important;
        line-height: 1.75 !important;
    }

    code,
    pre {
        font-family:
            Consolas,
            "Courier New",
            monospace !important;
    }


    /* ========================================================
       DIVIDERS
    ======================================================== */

    hr {
        border-color: var(--line) !important;
    }


    /* ========================================================
       MAIN ACTION BUTTONS
       
       Generate PIF / Generate TXT-style buttons:
       BLACK TEXT
    ======================================================== */

    .stButton > button,
    .stDownloadButton > button,
    .stLinkButton > a {

        min-height: 45px !important;

        border-radius: 4px !important;

        border: 1px solid var(--gold) !important;

        background: var(--gold) !important;

        color: #11151D !important;

        font-family: monospace !important;

        font-size: 0.68rem !important;

        font-weight: 700 !important;

        letter-spacing: 0.07em !important;

        text-transform: uppercase !important;
    }


    /* Force black text inside action buttons */

    .stButton > button p,
    .stButton > button span,
    .stDownloadButton > button p,
    .stDownloadButton > button span,
    .stLinkButton > a p,
    .stLinkButton > a span {

        color: #11151D !important;
    }


    .stButton > button:hover,
    .stDownloadButton > button:hover,
    .stLinkButton > a:hover {

        background: transparent !important;

        color: var(--gold) !important;
    }


    .stButton > button:hover p,
    .stButton > button:hover span,
    .stDownloadButton > button:hover p,
    .stDownloadButton > button:hover span,
    .stLinkButton > a:hover p,
    .stLinkButton > a:hover span {

        color: var(--gold) !important;
    }


    /* ========================================================
       FILE UPLOAD
    ======================================================== */

    [data-testid="stFileUploader"] {

        background: var(--panel);

        border: 1px dashed
            rgba(201, 164, 100, 0.30);

        border-radius: 8px;

        padding: 0.5rem;
    }


    /* ========================================================
       UPLOAD BUTTON
       
       Keep upload button:
       - same button properties
       - WHITE text
       - centered
    ======================================================== */

    [data-testid="stFileUploader"] button {

        position: relative !important;

        display: flex !important;

        align-items: center !important;

        justify-content: center !important;

        text-align: center !important;

        background: var(--gold) !important;

        border: 1px solid var(--gold) !important;

        color: #FFFFFF !important;

        font-family: monospace !important;

        font-weight: 700 !important;

        letter-spacing: 0.07em !important;

        text-transform: uppercase !important;

        font-size: 0 !important;
    }


    [data-testid="stFileUploader"] button::after {

        content: "Upload" !important;

        color: #FFFFFF !important;

        font-family: monospace !important;

        font-size: 0.68rem !important;

        font-weight: 700 !important;

        letter-spacing: 0.07em !important;

        text-align: center !important;
    }


    [data-testid="stFileUploader"] button svg {

        display: none !important;
    }


    /* ========================================================
       JĀṬĀ PANEL
    ======================================================== */

    .jata-box {

        background:
            linear-gradient(
                145deg,
                rgba(26, 32, 54, 0.98),
                rgba(15, 20, 32, 0.98)
            );

        border:
            1px solid
            rgba(201, 164, 100, 0.20);

        padding: 2rem;

        min-height: 300px;

        display: flex;

        flex-direction: column;

        justify-content: center;

        align-items: center;

        text-align: center;
    }

    .jata-label {

        color: var(--dim);

        font-family: monospace;

        font-size: 0.63rem;

        letter-spacing: 0.12em;

        text-transform: uppercase;

        margin-bottom: 2rem;
    }

    .jata-source {

        color: var(--text);

        font-family: monospace;

        font-size: 1.9rem;
    }

    .jata-arrow {

        color: var(--gold);

        font-size: 2rem;

        margin: 1rem 0;
    }

    .jata-output {

        color: var(--gold-soft);

        font-family: monospace;

        font-size: 1rem;
    }


    /* ========================================================
       SMALL CARDS
    ======================================================== */

    .small-card {

        background: var(--panel);

        border:
            1px solid
            rgba(237, 230, 214, 0.08);

        padding: 1.3rem;

        min-height: 160px;
    }

    .small-card-label {

        color: var(--dim);

        font-family: monospace;

        font-size: 0.62rem;

        letter-spacing: 0.12em;

        text-transform: uppercase;
    }


    /* ========================================================
       FILE INFO
    ======================================================== */

    .file-card {

        background: var(--panel);

        border:
            1px solid
            rgba(237, 230, 214, 0.08);

        padding: 1rem;

        min-height: 82px;
    }

    .file-label {

        color: var(--dim);

        font-family: monospace;

        font-size: 0.58rem;

        letter-spacing: 0.12em;

        text-transform: uppercase;
    }

    .file-value {

        color: var(--text);

        font-family: monospace;

        font-size: 0.75rem;

        margin-top: 0.5rem;

        word-break: break-word;
    }


    /* ========================================================
       RESULT PANELS
    ======================================================== */

    .result-success {

        background:
            rgba(122, 155, 118, 0.07);

        border:
            1px solid
            rgba(122, 155, 118, 0.32);

        padding: 1rem;

        margin-top: 1rem;
    }

    .result-error {

        background:
            rgba(166, 61, 64, 0.07);

        border:
            1px solid
            rgba(166, 61, 64, 0.38);

        padding: 1rem;

        margin-top: 1rem;
    }

    .result-success-title {

        color: #A8C59F;

        font-family: monospace;

        font-size: 0.68rem;

        letter-spacing: 0.10em;

        text-transform: uppercase;
    }

    .result-error-title {

        color: #D98A8D;

        font-family: monospace;

        font-size: 0.68rem;

        letter-spacing: 0.10em;

        text-transform: uppercase;
    }


    /* ========================================================
       POSITION PANEL
    ======================================================== */

    .position-panel {

        background:
            rgba(166, 61, 64, 0.08);

        border-left:
            3px solid
            var(--error);

        padding: 0.9rem 1rem;

        margin-top: 1rem;

        color: #DEA1A3;

        font-family: monospace;

        font-size: 0.76rem;
    }


    /* ========================================================
       FOOTER
    ======================================================== */

    .footer-line {

        margin-top: 6rem;

        padding-top: 2rem;

        border-top:
            1px solid
            var(--line);
    }


    /* ========================================================
       MOBILE
    ======================================================== */

    @media (max-width: 800px) {

        h1 {
            font-size: 3.2rem !important;
        }

        h2 {
            font-size: 2.3rem !important;
        }

    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# NAVBAR
# ============================================================

nav_left, nav_right = st.columns([1, 1])

with nav_left:
    st.markdown(
        "**PATHA**"
    )

with nav_right:
    st.caption(
        "DATA PRESERVATION · INTEGRITY · VERIFICATION"
    )

st.divider()


# ============================================================
# HERO
# ============================================================

hero_left, hero_right = st.columns(
    [1.15, 0.85],
    gap="large",
)

with hero_left:

    st.caption(
        "PĀṬHA-INSPIRED FILE · PROTOTYPE"
    )

    st.title(
        "Preserve Data.\nVerify Every Character."
    )

    st.write(
        "PATHA explores how principles of structured oral "
        "transmission can inspire modern approaches to "
        "data preservation and integrity."
    )

    st.write(
        "The current prototype uses a simplified "
        "Jāṭā-inspired computational pattern for textual data."
    )

    # Start Encoding button intentionally removed.


with hero_right:

    with st.container(border=True):

        st.caption(
            "SIMPLIFIED JĀṬĀ-INSPIRED TRANSFORMATION"
        )

        st.code(
            "A  B\n"
            " ↓\n"
            "A B | B A | A B",
            language="text",
        )

        st.caption(
            "Structured repetition is applied to "
            "overlapping pairs of logical text units."
        )


# ============================================================
# ABOUT
# ============================================================

st.divider()

st.caption("01 · ABOUT")

st.header("What is PATHA?")

st.write(
    "PATHA is a data-preservation and integrity prototype "
    "inspired by structured Indian oral traditions. "
    "The current prototype applies a simplified "
    "Jāṭā-inspired pattern to textual data."
)

st.write("")

about_left, about_right = st.columns(
    2,
    gap="large",
)

with about_left:

    with st.container(border=True):

        st.caption("THE IDEA")

        st.subheader(
            "Structured repetition"
        )

        st.write(
            "Adjacent data units are represented through "
            "structured repetition so that the encoded "
            "representation contains redundant information "
            "that can later be checked."
        )

with about_right:

    with st.container(border=True):

        st.caption("PROTOTYPE GOAL")

        st.subheader(
            "Integrity verification"
        )

        st.write(
            "Demonstrate a complete software pipeline for "
            "textual encoding, reconstruction, and detection "
            "of positions that cannot be verified."
        )


# ============================================================
# HOW IT WORKS
# ============================================================

st.divider()

st.caption("02 · PROCESS")

st.header("How It Works")

st.write(
    "PATHA converts text into logical units, creates "
    "overlapping pairs, applies the simplified Jāṭā-inspired "
    "pattern, and stores the resulting structure in PIF format."
)

st.write("")

step1, step2, step3, step4 = st.columns(4)

with step1:

    with st.container(border=True):

        st.caption("01")

        st.subheader("Upload TXT")

        st.write(
            "Select the UTF-8 text file you want to preserve."
        )

with step2:

    with st.container(border=True):

        st.caption("02")

        st.subheader("Build Units")

        st.write(
            "Represent the text as logical Unicode units "
            "while preserving supported whitespace."
        )

with step3:

    with st.container(border=True):

        st.caption("03")

        st.subheader("Jāṭā Encode")

        st.write(
            "Transform overlapping adjacent pairs using "
            "A B | B A | A B."
        )

with step4:

    with st.container(border=True):

        st.caption("04")

        st.subheader("Verify")

        st.write(
            "Decode the PIF and check its structure for "
            "inconsistencies."
        )

st.write("")

st.subheader(
    "PATHA processing pipeline"
)

st.code(
    "TXT\n"
    "  ↓\n"
    "Logical Units\n"
    "  ↓\n"
    "Overlapping Pairs\n"
    "  ↓\n"
    "Jāṭā Pattern\n"
    "  ↓\n"
    "PIF\n"
    "  ↓\n"
    "Decode / Verify",
    language="text",
)


# ============================================================
# ENCODE
# ============================================================

st.divider()

st.caption("03 · ENCODE")

st.header("Encode Your Data")

st.write(
    "Transform a UTF-8 TXT file into PATHA's PIF format."
)

st.write("")

uploaded_txt = st.file_uploader(
    "Upload TXT file",
    type=["txt"],
    key="encode_upload",
    help="Only .txt files are supported.",
)

if uploaded_txt is not None:

    txt_bytes = uploaded_txt.getvalue()

    file1, file2, file3 = st.columns(3)

    with file1:

        with st.container(border=True):

            st.caption("FILE")

            st.write(
                uploaded_txt.name
            )

    with file2:

        with st.container(border=True):

            st.caption("FORMAT")

            st.write(
                "TXT · UTF-8"
            )

    with file3:

        with st.container(border=True):

            st.caption("SIZE")

            st.write(
                f"{len(txt_bytes):,} bytes"
            )

    st.write("")

    if st.button(
        "Generate PIF",
        key="generate_pif",
        use_container_width=True,
    ):

        operation = None

        with st.spinner("Encoding..."):

            try:

                # =============================================
                # PERSON 1 + EXISTING STORAGE MANAGER
                # =============================================

                operation = handle_upload(
                    txt_bytes,
                    original_filename=uploaded_txt.name,
                )

                # Read PIF before cleanup.
                pif_bytes, download_filename = (
                    prepare_download(operation)
                )

                # Save PIF in Streamlit session memory.
                st.session_state["encoded_data"] = (
                    pif_bytes
                )

                st.session_state["encoded_filename"] = (
                    download_filename
                )

                st.session_state["encoded_source"] = (
                    uploaded_txt.name
                )

                st.success(
                    "✓ PIF generated successfully."
                )

            except ValueError as exc:

                error_message = str(exc)

                if (
                    "reserved sequence"
                    in error_message.lower()
                ):

                    st.error(
                        "This TXT file contains a reserved "
                        "sequence used by the PATHA PIF format."
                    )

                elif "minimum" in error_message.lower():

                    st.error(
                        "The TXT file must contain at least "
                        "2 characters."
                    )

                else:

                    st.error(
                        error_message
                    )

            except FileNotFoundError:

                st.error(
                    "The uploaded TXT file could not be processed."
                )

            except Exception as exc:

                st.error(
                    "Unable to encode this TXT file."
                )

                st.exception(exc)

            finally:

                # PIF bytes are already in Streamlit memory.
                # Backend copies can now be finalized.
                if operation is not None:

                    try:

                        finalize_download(
                            operation
                        )

                    except Exception:

                        pass


# ============================================================
# ENCODE RESULT + PIF DOWNLOAD
# ============================================================

if st.session_state["encoded_data"] is not None:

    with st.container(border=True):

        st.success(
            "PIF generated successfully."
        )

        st.write(
            "Your encoded PIF file is ready."
        )

        st.download_button(
            label="Download PIF",
            data=st.session_state["encoded_data"],
            file_name=st.session_state["encoded_filename"],
            mime="text/plain",
            key="download_pif",
            use_container_width=True,
        )

    st.write("")

    result1, result2, result3 = st.columns(3)

    with result1:

        st.caption("INPUT")

        st.write(
            st.session_state["encoded_source"]
        )

    with result2:

        st.caption("METHOD")

        st.write(
            "JĀṬĀ"
        )

    with result3:

        st.caption("OUTPUT")

        st.write(
            st.session_state["encoded_filename"]
        )


# ============================================================
# DECODE
# ============================================================

st.divider()

st.caption("04 · DECODE & VERIFY")

st.header("Verify & Decode")

st.write(
    "Upload a PIF file to reconstruct the original text "
    "and identify possible integrity errors."
)

st.write("")

uploaded_pif = st.file_uploader(
    "Upload PIF file",
    type=["pif"],
    key="decode_upload",
    help="Only .pif files are supported.",
)

if uploaded_pif is not None:

    pif_bytes = uploaded_pif.getvalue()

    file1, file2, file3 = st.columns(3)

    with file1:

        with st.container(border=True):

            st.caption("FILE")

            st.write(
                uploaded_pif.name
            )

    with file2:

        with st.container(border=True):

            st.caption("FORMAT")

            st.write(
                "PIF"
            )

    with file3:

        with st.container(border=True):

            st.caption("SIZE")

            st.write(
                f"{len(pif_bytes):,} bytes"
            )

    st.write("")

    if st.button(
        "Decode PIF",
        key="decode_pif",
        use_container_width=True,
    ):

        # Clear previous result.
        st.session_state["decode_done"] = False
        st.session_state["decode_text"] = ""
        st.session_state["decode_has_errors"] = False
        st.session_state["decode_positions"] = []
        st.session_state["decode_filename"] = None

        temporary_dir = (
            BACKEND_DIR
            / "storage"
            / "temporary"
        )

        temporary_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        operation_id = uuid.uuid4().hex

        safe_filename = Path(
            uploaded_pif.name
        ).name

        temp_pif = (
            temporary_dir
            / f"streamlit_{operation_id}_{safe_filename}"
        )

        temp_txt = (
            temporary_dir
            / f"streamlit_{operation_id}_decoded.txt"
        )

        try:

            with st.spinner("Decoding..."):

                # =============================================
                # SAVE EXACT UPLOADED PIF
                # =============================================

                temp_pif.write_bytes(
                    pif_bytes
                )

                # =============================================
                # PERSON 2 DECODER
                # =============================================

                result = decode_pif_to_txt(
                    temp_pif,
                    temp_txt,
                )

            # =============================================
            # READ DECODER RESULT
            # =============================================

            positions = sorted(
                {
                    int(error.text_position)
                    for error in (
                        result.errors or []
                    )
                }
            )

            st.session_state["decode_text"] = (
                result.text
            )

            st.session_state["decode_has_errors"] = (
                bool(result.has_errors)
            )

            st.session_state["decode_positions"] = (
                positions
            )

            st.session_state["decode_filename"] = (
                uploaded_pif.name
            )

            st.session_state["decode_done"] = True

        except ValueError:

            st.error(
                "Unable to decode this PIF file. "
                "The file structure or header is invalid."
            )

        except FileNotFoundError:

            st.error(
                "The PIF file could not be found."
            )

        except Exception as exc:

            # During development, expose the actual error.
            st.error(
                "An unexpected error occurred while decoding."
            )

            st.exception(exc)

        finally:

            # =============================================
            # REMOVE TEMPORARY PIF
            # =============================================

            try:

                if temp_pif.exists():
                    temp_pif.unlink()

            except OSError:

                pass

            # =============================================
            # REMOVE TEMPORARY TXT
            # =============================================

            try:

                if temp_txt.exists():
                    temp_txt.unlink()

            except OSError:

                pass


# ============================================================
# DECODE RESULT
# ============================================================

if st.session_state["decode_done"]:

    reconstructed_text = (
        st.session_state["decode_text"]
    )

    has_errors = (
        st.session_state["decode_has_errors"]
    )

    positions = (
        st.session_state["decode_positions"]
    )

    filename = (
        st.session_state["decode_filename"]
    )

    st.divider()


    # ========================================================
    # STATUS
    # ========================================================

    if not has_errors:

        with st.container(border=True):

            st.success(
                "✓ No Errors Detected"
            )

            st.write(
                "The PIF structure was successfully verified."
            )

    else:

        with st.container(border=True):

            st.error(
                "⚠ Integrity Issue Detected"
            )

            st.write(
                "One or more reconstructed positions could "
                "not be verified."
            )


    # ========================================================
    # RECONSTRUCTED TEXT
    # ========================================================

    st.subheader("Reconstructed Text")

    # Exact text returned by decoder.py.
    # The decoder is responsible for inserting '*'.

    st.code(
        reconstructed_text,
        language="text",
    )


    # ========================================================
    # DOWNLOAD RECONSTRUCTED TEXT
    # ========================================================

    reconstructed_filename = (
        f"{Path(filename).stem}_reconstructed.txt"
    )

    st.download_button(
        label="Download Reconstructed TXT",
        data=reconstructed_text.encode("utf-8"),
        file_name=reconstructed_filename,
        mime="text/plain",
        key="download_reconstructed_txt",
        use_container_width=True,
    )


    # ========================================================
    # ERROR INFORMATION
    # ========================================================

    if has_errors:

        st.subheader("Error Information")

        if len(positions) == 1:

            st.warning(
                f"Error detected at position {positions[0]}."
            )

        else:

            positions_text = ", ".join(
                str(position)
                for position in positions
            )

            st.warning(
                f"Errors detected at positions "
                f"{positions_text}."
            )

        st.info(
            "The * marker identifies the position that "
            "could not be verified during reconstruction."
        )

        st.caption(
            "PATHA does not predict or automatically correct "
            "the untrusted character in this prototype."
        )

    else:

        st.success(
            "The reconstructed text contains no detected "
            "integrity errors."
        )


    # ========================================================
    # FILE INFORMATION
    # ========================================================

    st.subheader("File Information")

    info1, info2, info3 = st.columns(3)

    with info1:

        st.caption("FILE")

        st.write(
            filename
        )

    with info2:

        st.caption("METHOD")

        st.write(
            "JĀṬĀ"
        )

    with info3:

        st.caption("STATUS")

        st.write(
            "Error Detected"
            if has_errors
            else "Verified"
        )


# ============================================================
# PROTOTYPE SCOPE
# ============================================================

st.divider()

st.caption(
    "PROTOTYPE SCOPE"
)

st.write(
    "The current PATHA prototype focuses on structured "
    "text encoding, reconstruction, and integrity-error "
    "detection. It does not perform encryption, compression, "
    "character prediction, or automatic correction."
)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "PATHA"
)

st.caption(
    "A Pāṭha-inspired data preservation and integrity prototype."
)

st.caption(
    "Simplified Jāṭā-inspired encoding · UTF-8 text · PIF"
)