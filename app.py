import streamlit as st
import os
import io
import base64
import pandas as pd
import tempfile
import re
import sys
import logging
from PIL import Image
from dotenv import load_dotenv

# Third-party libraries
import pdf2image
import google.generativeai as genai
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# --- Basic Logging Configuration ---
# This setup directs log messages to the terminal (standard output)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# --- Configuration ---
logging.info("Starting Streamlit application...")
# Load environment variables from .env file
load_dotenv()

# Configure the Google Generative AI client
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("Google API key not found. Please set it in your .env file.")
    logging.error("Google API key not found in .env file. Application might not function correctly.")
else:
    genai.configure(api_key=api_key)
    logging.info("Successfully configured Google Generative AI client.")

# --- Core Functions (No changes here) ---

def get_gemini_response(input_text, pdf_content, prompt):
    """
    Calls the Gemini API to generate a response based on the input, PDF content, and prompt.
    """
    try:
        logging.info("Calling the Gemini API...")
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([input_text, pdf_content[0], prompt])
        logging.info("Successfully received response from Gemini API.")
        return response.text
    except Exception as e:
        st.error(f"An error occurred with the Gemini API: {e}")
        logging.error(f"Gemini API call failed: {e}")
        return f"Error: Could not get response from Gemini API. Details: {str(e)}"

def input_pdf_setup(uploaded_file):
    """
    Converts the first page of a PDF file to a format suitable for the Gemini API.
    """
    filename = getattr(uploaded_file, 'name', 'file')
    logging.info(f"Processing PDF file: {filename}")
    if uploaded_file is not None:
        try:
            file_bytes = uploaded_file.read()
            logging.info(f"Converting PDF '{filename}' to image...")
            images = pdf2image.convert_from_bytes(file_bytes)
            if not images:
                st.error("Could not extract any images from the PDF.")
                logging.error(f"pdf2image could not extract any pages from '{filename}'.")
                return None
            first_page = images[0]
            img_byte_arr = io.BytesIO()
            first_page.save(img_byte_arr, format='JPEG')
            img_byte_arr = img_byte_arr.getvalue()
            pdf_parts = [{"mime_type": "image/jpeg", "data": base64.b64encode(img_byte_arr).decode()}]
            logging.info(f"Successfully converted '{filename}' to API-ready format.")
            return pdf_parts
        except Exception as e:
            st.error(f"Failed to process PDF file '{filename}': {e}")
            logging.error(f"Failed to process PDF file '{filename}': {e}")
            return None
    else:
        logging.error("input_pdf_setup was called with no file.")
        raise FileNotFoundError("No file was provided to process.")

def extract_percentage(response_text):
    """
    Extracts the first percentage value found in the response text using regex.
    """
    match = re.search(r'(\d{1,3})\s*%', response_text)
    if match:
        score = int(match.group(1))
        logging.info(f"Extracted percentage score: {score}%")
        return score
    st.warning(f"Could not extract a percentage score from the response. Defaulting to 0.")
    logging.warning(f"Could not extract a percentage score. Response: '{response_text[:100]}...'. Defaulting to 0.")
    return 0

def get_folder_id_from_link(link):
    """
    Extracts the Google Drive folder ID from a shareable link.
    """
    logging.info(f"Attempting to extract folder ID from link: {link}")
    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', link)
    if match:
        folder_id = match.group(1)
        logging.info(f"Successfully extracted folder ID: {folder_id}")
        return folder_id
    logging.warning("Could not extract folder ID from the provided link.")
    return None

def download_pdfs_from_gdrive_folder(folder_id):
    """
    Authenticates with Google Drive and downloads all PDF files from a specified folder.
    """
    try:
        logging.info("Initiating Google Drive authentication...")
        gauth = GoogleAuth()
        gauth.LocalWebserverAuth()
        drive = GoogleDrive(gauth)
        logging.info("Google Drive authentication successful.")
        query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
        logging.info(f"Querying Google Drive for PDF files with: {query}")
        file_list = drive.ListFile({'q': query}).GetList()
        st.info(f"Found {len(file_list)} PDF files in the Google Drive folder.")
        logging.info(f"Found {len(file_list)} PDF files in the Google Drive folder.")
        pdf_files = []
        for i, file in enumerate(file_list):
            logging.info(f"Downloading file {i+1}/{len(file_list)}: {file['title']}")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
                file.GetContentFile(temp.name)
                pdf_files.append((file['title'], temp.name))
        return pdf_files
    except Exception as e:
        st.error(f"An error occurred during Google Drive authentication or file download: {e}")
        logging.error(f"An error occurred during Google Drive authentication or file download: {e}")
        return []

# --- Streamlit App UI ---

st.set_page_config(page_title="APTSO Resume Tracker", layout="wide")
st.header("📄 APTSO - Advanced Profile Tracking System")
st.write("Evaluate resumes against a job description efficiently. You can analyze a single resume, multiple resumes, or an entire Google Drive folder.")

# --- Prompts ---
input_prompt1 = """
You are an experienced Technical Human Resource Manager,your task is to review the provided resume against the job description.
 Please share your professional evaluation on whether the candidate's profile aligns with the role.
Highlight the strengths and weaknesses of the applicant in relation to the specified job requirements.
"""

input_prompt_missing = """
You are an ATS (Applicant Tracking System) expert. Compare the resume with the provided job description and list only the keywords or skills that are present in the job description but missing from the resume. Return only the missing keywords as a comma-separated list.
"""

input_prompt3 = """
You are an skilled ATS (Applicant Tracking System) scanner with a deep understanding of data science and ATS functionality,
your task is to evaluate the resume against the provided job description. give me the percentage of match if the resume matches
the job description. First the output should come as percentage and then keywords missing and last final thoughts.
"""

# --- Main Layout ---
job_description = st.text_area("**1. Paste the Job Description here:**", key="job_desc", height=200)

# --- Analysis Options ---
st.subheader("2. Choose an Evaluation Method")

tab1, tab2, tab3 = st.tabs(["Single Resume", "Multiple Resumes", "Google Drive Folder"])

# --- TAB 1: Single Resume Analysis (UPDATED LOGIC) ---
with tab1:
    st.markdown("##### Upload a single PDF resume for a detailed analysis.")
    uploaded_file_single = st.file_uploader("Upload your resume (PDF)", type=["pdf"], key="single_uploader")

    if uploaded_file_single:
        st.success(f"PDF '{uploaded_file_single.name}' Uploaded Successfully")
        logging.info(f"Single file uploaded: {uploaded_file_single.name}")

        col1, col2, col3 = st.columns(3)
        with col1:
            submit1 = st.button("Resume Overview", use_container_width=True, key="submit_overview")
        with col2:
            submit_missing = st.button("Find Missing Keywords", use_container_width=True, key="submit_missing")
        with col3:
            submit3 = st.button("Calculate ATS Match %", use_container_width=True, key="submit_match")

        # Check for job description first
        if submit1 or submit_missing or submit3:
            if not job_description:
                st.warning("Please paste a job description first.")
                logging.warning("Evaluation attempted without a job description.")
            else:
                pdf_content = input_pdf_setup(uploaded_file_single)
                if pdf_content:
                    prompt_to_use = None
                    analysis_type = ""
                    
                    if submit1:
                        prompt_to_use = input_prompt1
                        analysis_type = "Resume Overview"
                    elif submit_missing:
                        prompt_to_use = input_prompt_missing
                        analysis_type = "Missing Keywords"
                    elif submit3:
                        prompt_to_use = input_prompt3
                        analysis_type = "Percentage Match"
                    
                    with st.spinner(f"Performing '{analysis_type}' analysis..."):
                        logging.info(f"User triggered '{analysis_type}' analysis for '{uploaded_file_single.name}'.")
                        response = get_gemini_response(job_description, pdf_content, prompt_to_use)
                        st.subheader(f"{analysis_type} Result")
                        st.write(response)
                        logging.info(f"Finished '{analysis_type}' analysis.")

# --- TAB 2: Multiple Resume Upload (No changes here) ---
with tab2:
    st.markdown("##### Upload up to 20 PDF resumes to rank them by ATS score.")
    uploaded_files_multi = st.file_uploader(
        "Upload your resumes (PDF)", type=["pdf"], accept_multiple_files=True, key="multi_uploader"
    )

    if uploaded_files_multi:
        logging.info(f"{len(uploaded_files_multi)} files uploaded for batch processing.")
        if len(uploaded_files_multi) > 20:
            st.warning("Please upload no more than 20 resumes. Only the first 20 will be processed.")
            logging.warning(f"User uploaded {len(uploaded_files_multi)} files. Truncating to 20.")
            uploaded_files_multi = uploaded_files_multi[:20]

    if st.button("Evaluate All Uploaded Resumes", key="submit_all_multi"):
        if not uploaded_files_multi:
            st.warning("Please upload at least one resume.")
            logging.warning("Multi-resume evaluation attempted with no files uploaded.")
        elif not job_description:
            st.warning("Please paste a job description first.")
            logging.warning("Multi-resume evaluation attempted without a job description.")
        else:
            total_files = len(uploaded_files_multi)
            logging.info(f"Starting evaluation for {total_files} uploaded resumes.")
            with st.spinner(f"Evaluating {total_files} resumes..."):
                results = []
                progress_bar = st.progress(0, text="Starting...")
                for i, uploaded_file in enumerate(uploaded_files_multi):
                    logging.info(f"Processing file {i+1}/{total_files}: {uploaded_file.name}")
                    progress_bar.progress((i) / total_files, text=f"Processing {uploaded_file.name}...")
                    pdf_content = input_pdf_setup(uploaded_file)
                    if pdf_content:
                        response = get_gemini_response(job_description, pdf_content, input_prompt3)
                        score = extract_percentage(response)
                        results.append({"filename": uploaded_file.name, "score": score, "response": response})
                progress_bar.progress(1.0, text="Evaluation Complete!")
                
                logging.info("All uploaded resumes have been evaluated. Sorting results.")
                results = sorted(results, key=lambda x: x["score"], reverse=True)

                st.subheader("ATS Score Ranking")
                df = pd.DataFrame([{"Resume": r['filename'], "ATS Score (%)": r["score"]} for r in results])
                st.dataframe(df, hide_index=True, use_container_width=True)

                st.subheader("Full Evaluations")
                for res in results:
                    with st.expander(f"**{res['filename']}** — ATS Score: {res['score']}%"):
                        st.write(res["response"])
                logging.info("Displayed all results for multi-upload.")

# --- TAB 3: Google Drive Integration (No changes here) ---
with tab3:
    st.markdown("##### Paste a Google Drive folder link to evaluate all PDF resumes within it.")
    gdrive_link = st.text_input("Google Drive Folder Link (must be shared with 'Anyone with the link')")

    if st.button("Evaluate Resumes from Google Drive", key="submit_gdrive"):
        if not gdrive_link:
            st.warning("Please paste a Google Drive folder link.")
            logging.warning("Google Drive evaluation attempted without a link.")
        elif not job_description:
            st.warning("Please paste a job description first.")
            logging.warning("Google Drive evaluation attempted without a job description.")
        else:
            folder_id = get_folder_id_from_link(gdrive_link)
            if not folder_id:
                st.error("Invalid Google Drive folder link. Please ensure it's a valid folder link.")
            else:
                pdf_files = []
                with st.spinner("Downloading PDFs from Google Drive... This may require browser authentication."):
                    pdf_files = download_pdfs_from_gdrive_folder(folder_id)
                
                if pdf_files:
                    total_files = len(pdf_files)
                    logging.info(f"Starting evaluation for {total_files} resumes from Google Drive.")
                    with st.spinner(f"Evaluating {total_files} resumes..."):
                        results = []
                        progress_bar = st.progress(0, text="Starting...")
                        for i, (filename, filepath) in enumerate(pdf_files):
                            logging.info(f"Processing file {i+1}/{total_files}: {filename}")
                            progress_bar.progress((i) / total_files, text=f"Processing {filename}...")
                            with open(filepath, "rb") as f:
                                class MockUploadedFile:
                                    def __init__(self, name, data):
                                        self.name = name
                                        self._data = data
                                    def read(self):
                                        return self._data
                                
                                mock_file = MockUploadedFile(filename, f.read())
                                pdf_content = input_pdf_setup(mock_file)
                                if pdf_content:
                                    response = get_gemini_response(job_description, pdf_content, input_prompt3)
                                    score = extract_percentage(response)
                                    results.append({"filename": filename, "score": score, "response": response})
                            os.remove(filepath)
                            logging.info(f"Cleaned up temporary file: {filepath}")
                        progress_bar.progress(1.0, text="Evaluation Complete!")

                        logging.info("All Google Drive resumes have been evaluated. Sorting results.")
                        results = sorted(results, key=lambda x: x["score"], reverse=True)
                        st.subheader("ATS Score Ranking")
                        df = pd.DataFrame([{"Resume": r['filename'], "ATS Score (%)": r["score"]} for r in results])
                        st.dataframe(df, hide_index=True, use_container_width=True)

                        st.subheader("Full Evaluations")
                        for res in results:
                            with st.expander(f"**{res['filename']}** — ATS Score: {res['score']}%"):
                                st.write(res["response"])
                        logging.info("Displayed all results for Google Drive.")